
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.units import percent, volume_m3
from app.stock.models import StockItem
from app.warehouses.models import Rack, Shelf

ZERO = Decimal("0")

@dataclass(frozen=True)
class ShelfFill:
    

    shelf_id: int
    total_volume_m3: Decimal
    used_volume_m3: Decimal
    total_max_weight_kg: Decimal
    used_weight_kg: Decimal
    items_count: int = 0

    @property
    def free_volume_m3(self) -> Decimal:
        return max(ZERO, self.total_volume_m3 - self.used_volume_m3)

    @property
    def free_weight_kg(self) -> Decimal:
        return max(ZERO, self.total_max_weight_kg - self.used_weight_kg)

    @property
    def volume_fill_percent(self) -> float:
        return percent(self.used_volume_m3, self.total_volume_m3)

    @property
    def weight_fill_percent(self) -> float:
        return percent(self.used_weight_kg, self.total_max_weight_kg)

    @property
    def is_overloaded(self) -> bool:
        
        return (
            self.used_volume_m3 > self.total_volume_m3
            or self.used_weight_kg > self.total_max_weight_kg
        )

@dataclass(frozen=True)
class RackFill:
    

    rack_id: int
    total_volume_m3: Decimal
    used_volume_m3: Decimal
    total_max_weight_kg: Decimal
    used_weight_kg: Decimal
    shelves_count: int = 0
    shelves_used: int = 0
    shelves: dict[int, ShelfFill] = field(default_factory=dict)

    @property
    def free_volume_m3(self) -> Decimal:
        return max(ZERO, self.total_volume_m3 - self.used_volume_m3)

    @property
    def free_weight_kg(self) -> Decimal:
        return max(ZERO, self.total_max_weight_kg - self.used_weight_kg)

    @property
    def volume_fill_percent(self) -> float:
        return percent(self.used_volume_m3, self.total_volume_m3)

    @property
    def weight_fill_percent(self) -> float:
        return percent(self.used_weight_kg, self.total_max_weight_kg)

    @property
    def is_overloaded(self) -> bool:
        return (
            self.used_volume_m3 > self.total_volume_m3
            or self.used_weight_kg > self.total_max_weight_kg
        )

def empty_shelf_fill(shelf: Shelf) -> ShelfFill:
    
    return ShelfFill(
        shelf_id=shelf.id,
        total_volume_m3=volume_m3(shelf.width, shelf.length, shelf.height),
        used_volume_m3=ZERO,
        total_max_weight_kg=Decimal(str(shelf.max_weight)),
        used_weight_kg=ZERO,
        items_count=0,
    )

async def get_shelf_fills(
    session: AsyncSession,
    warehouse_id: int,
) -> dict[int, ShelfFill]:
    
    shelves = (
        await session.scalars(
            select(Shelf)
            .join(Rack, Shelf.rack_id == Rack.id)
            .where(Rack.warehouse_id == warehouse_id)
            .order_by(Shelf.id)
        )
    ).all()

    result: dict[int, ShelfFill] = {
        shelf.id: empty_shelf_fill(shelf) for shelf in shelves
    }
    if not result:
        return result

    rows = (
        await session.execute(
            select(
                StockItem.shelf_id,
                StockItem.quantity,
                StockItem.package_type,
                StockItem.product_id,
            )
            .where(StockItem.warehouse_id == warehouse_id)
        )
    ).all()

    if not rows:
        return result

    from app.products.models import Product

    product_ids = {row.product_id for row in rows}
    products = {
        product.id: product
        for product in (
            await session.scalars(select(Product).where(Product.id.in_(product_ids)))
        ).all()
    }

    used_volume: dict[int, Decimal] = {}
    used_weight: dict[int, Decimal] = {}
    items_count: dict[int, int] = {}

    for shelf_id, quantity, _package_type, product_id in rows:
        product = products.get(product_id)
        if product is None:
            continue
        qty = Decimal(str(quantity))
        used_volume[shelf_id] = used_volume.get(shelf_id, ZERO) + volume_m3(
            product.width, product.length, product.height
        ) * qty
        used_weight[shelf_id] = used_weight.get(shelf_id, ZERO) + (
            Decimal(str(product.weight)) * qty
        )
        items_count[shelf_id] = items_count.get(shelf_id, 0) + 1

    for shelf_id, fill in list(result.items()):
        result[shelf_id] = ShelfFill(
            shelf_id=shelf_id,
            total_volume_m3=fill.total_volume_m3,
            used_volume_m3=used_volume.get(shelf_id, ZERO),
            total_max_weight_kg=fill.total_max_weight_kg,
            used_weight_kg=used_weight.get(shelf_id, ZERO),
            items_count=items_count.get(shelf_id, 0),
        )
    return result

async def get_rack_fills(
    session: AsyncSession,
    warehouse_id: int,
) -> dict[int, RackFill]:
    
    racks = (
        await session.scalars(
            select(Rack)
            .where(Rack.warehouse_id == warehouse_id)
            .options(selectinload(Rack.shelves))
            .order_by(Rack.id)
        )
    ).all()

    shelf_fills = await get_shelf_fills(session, warehouse_id)

    shelf_by_rack: dict[int, list[Shelf]] = {}
    for rack in racks:
        shelf_by_rack[rack.id] = list(rack.shelves)

    result: dict[int, RackFill] = {}
    for rack in racks:
        rack_shelves = shelf_by_rack.get(rack.id, [])
        fills = [shelf_fills[shelf.id] for shelf in rack_shelves if shelf.id in shelf_fills]
        result[rack.id] = RackFill(
            rack_id=rack.id,
            total_volume_m3=sum((f.total_volume_m3 for f in fills), ZERO),
            used_volume_m3=sum((f.used_volume_m3 for f in fills), ZERO),
            total_max_weight_kg=sum((f.total_max_weight_kg for f in fills), ZERO),
            used_weight_kg=sum((f.used_weight_kg for f in fills), ZERO),
            shelves_count=len(rack_shelves),
            shelves_used=sum(1 for f in fills if f.items_count > 0),
            shelves={f.shelf_id: f for f in fills},
        )
    return result

async def get_warehouse_capacity(
    session: AsyncSession,
    warehouse_id: int,
) -> dict[str, Decimal | float]:
    
    rack_fills = await get_rack_fills(session, warehouse_id)
    total_volume = sum((r.total_volume_m3 for r in rack_fills.values()), ZERO)
    used_volume = sum((r.used_volume_m3 for r in rack_fills.values()), ZERO)
    total_weight = sum((r.total_max_weight_kg for r in rack_fills.values()), ZERO)
    used_weight = sum((r.used_weight_kg for r in rack_fills.values()), ZERO)
    return {
        "total_volume_m3": total_volume,
        "used_volume_m3": used_volume,
        "free_volume_m3": max(ZERO, total_volume - used_volume),
        "total_max_weight_kg": total_weight,
        "used_weight_kg": used_weight,
        "free_weight_kg": max(ZERO, total_weight - used_weight),
        "volume_fill_percent": percent(used_volume, total_volume),
        "weight_fill_percent": percent(used_weight, total_weight),
    }
