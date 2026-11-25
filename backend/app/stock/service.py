
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import StockMovementType
from app.core.units import volume_m3
from app.products.models import Product
from app.stock.models import StockItem, StockMovement
from app.warehouses.models import Rack, Shelf

ZERO = Decimal("0")
QUANTITY_STEP = Decimal("0.01")

class StockError(Exception):
    pass

@dataclass(frozen=True)
class Shortage:
    

    product_id: int
    product_name: str
    sku_code: str
    requested: Decimal
    available: Decimal

    @property
    def missing(self) -> Decimal:
        return max(ZERO, self.requested - self.available)

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "sku_code": self.sku_code,
            "requested": str(self.requested),
            "available": str(self.available),
            "shortage": str(self.missing),
        }

@dataclass(frozen=True)
class CapacityShortage:
    

    product_id: int
    product_name: str
    sku_code: str
    requested: Decimal
    placed: Decimal
    reason: str

    @property
    def unplaced(self) -> Decimal:
        return max(ZERO, self.requested - self.placed)

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "sku_code": self.sku_code,
            "requested": str(self.requested),
            "placed": str(self.placed),
            "unplaced": str(self.unplaced),
            "reason": self.reason,
        }

class InsufficientStockError(StockError):
    

    def __init__(self, shortages: list[Shortage]):
        self.shortages = shortages
        super().__init__("Недостатньо залишків на складі")

class InsufficientCapacityError(StockError):
    

    def __init__(self, shortages: list[CapacityShortage]):
        self.shortages = shortages
        super().__init__("Недостатньо місця на полицях складу")

async def get_products(
    session: AsyncSession, product_ids: list[int]
) -> dict[int, Product]:
    if not product_ids:
        return {}
    products = (
        await session.scalars(select(Product).where(Product.id.in_(product_ids)))
    ).all()
    return {product.id: product for product in products}

async def get_available_quantities(
    session: AsyncSession,
    warehouse_id: int,
    product_ids: list[int] | None = None,
    *,
    for_update: bool = False,
) -> dict[int, Decimal]:
    
    stmt = select(
        StockItem.product_id,
        StockItem.quantity,
    ).where(StockItem.warehouse_id == warehouse_id)
    if product_ids is not None:
        if not product_ids:
            return {}
        stmt = stmt.where(StockItem.product_id.in_(product_ids))
    if for_update:
        stmt = stmt.with_for_update()

    rows = (await session.execute(stmt)).all()
    totals: dict[int, Decimal] = {}
    for product_id, quantity in rows:
        totals[product_id] = totals.get(product_id, ZERO) + Decimal(str(quantity))
    return totals

async def get_stock_items(
    session: AsyncSession,
    warehouse_id: int,
    product_id: int | None = None,
    *,
    for_update: bool = False,
) -> list[StockItem]:
    stmt = select(StockItem).where(StockItem.warehouse_id == warehouse_id)
    if product_id is not None:
        stmt = stmt.where(StockItem.product_id == product_id)
    stmt = stmt.order_by(StockItem.shelf_id, StockItem.id)
    if for_update:
        stmt = stmt.with_for_update()
    return list((await session.scalars(stmt)).all())

async def _active_shelves(session: AsyncSession, warehouse_id: int) -> list[Shelf]:
    
    from app.core.enums import ShelfStatus

    shelves = (
        await session.scalars(
            select(Shelf)
            .join(Rack, Shelf.rack_id == Rack.id)
            .where(Rack.warehouse_id == warehouse_id)
            .options(selectinload(Shelf.rack))
            .order_by(Shelf.id)
        )
    ).all()
    return [shelf for shelf in shelves if shelf.status == ShelfStatus.ACTIVE]

async def _used_capacity(
    session: AsyncSession, warehouse_id: int, *, for_update: bool = False
) -> dict[int, tuple[Decimal, Decimal]]:
    
    from app.products.models import Product

    stmt = select(
        StockItem.shelf_id,
        StockItem.quantity,
        StockItem.product_id,
    ).where(StockItem.warehouse_id == warehouse_id)
    if for_update:
        stmt = stmt.with_for_update()
    rows = (await session.execute(stmt)).all()
    if not rows:
        return {}

    product_ids = {row[2] for row in rows}
    products = await get_products(session, list(product_ids))

    used: dict[int, tuple[Decimal, Decimal]] = {}
    for shelf_id, quantity, product_id in rows:
        product = products.get(product_id)
        if product is None:
            continue
        qty = Decimal(str(quantity))
        volume = volume_m3(product.width, product.length, product.height) * qty
        weight = Decimal(str(product.weight)) * qty
        current_volume, current_weight = used.get(shelf_id, (ZERO, ZERO))
        used[shelf_id] = (current_volume + volume, current_weight + weight)
    return used

def _get_capacity_shortage_reason(
    shelves: list[Shelf],
    used: dict[int, tuple[Decimal, Decimal]],
    unit_volume: Decimal,
    unit_weight: Decimal,
    remaining: Decimal,
) -> str:
    if not shelves:
        return "на складі немає жодної активної полиці"

    total_by_volume = ZERO
    total_by_weight = ZERO

    for shelf in shelves:
        used_volume, used_weight = used.get(shelf.id, (ZERO, ZERO))

        free_volume = max(
            ZERO,
            volume_m3(shelf.width, shelf.length, shelf.height) - used_volume,
        )
        free_weight = max(
            ZERO,
            Decimal(str(shelf.max_weight)) - used_weight,
        )

        if unit_volume > ZERO:
            total_by_volume += (free_volume / unit_volume).quantize(
                QUANTITY_STEP, rounding=ROUND_DOWN
            )

        if unit_weight > ZERO:
            total_by_weight += (free_weight / unit_weight).quantize(
                QUANTITY_STEP, rounding=ROUND_DOWN
            )

    volume_shortage = unit_volume > ZERO and total_by_volume < remaining
    weight_shortage = unit_weight > ZERO and total_by_weight < remaining

    if volume_shortage and weight_shortage:
        return "недостатньо вільного об'єму та вантажопідйомності полиць"

    if volume_shortage:
        return "недостатньо вільного об'єму на полицях"

    if weight_shortage:
        return "недостатньо вантажопідйомності полиць"

    return "недостатньо місця з одночасним урахуванням об'єму та ваги"

async def place_incoming(
    session: AsyncSession,
    warehouse_id: int,
    items: list[tuple[int, Decimal, str]],
    *,
    user_id: int | None = None,
    order_id: int | None = None,
) -> list[CapacityShortage]:
    
    shelves = await _active_shelves(session, warehouse_id)
    used = await _used_capacity(session, warehouse_id, for_update=True)
    products = await get_products(session, [item[0] for item in items])

    existing = {
        (item.shelf_id, item.product_id, item.package_type): item
        for item in await get_stock_items(session, warehouse_id, for_update=True)
    }

    shortages: list[CapacityShortage] = []

    for product_id, quantity, package_type in items:
        product = products.get(product_id)
        if product is None:
            continue
        unit_volume = volume_m3(product.width, product.length, product.height)
        unit_weight = Decimal(str(product.weight))
        remaining = Decimal(str(quantity))
        placed = ZERO

        if unit_volume <= 0 or unit_weight <= 0:
            unit_volume = ZERO

        ordered_shelves = sorted(
            shelves,
            key=lambda shelf: (
                0
                if (shelf.id, product_id, package_type) in existing
                else 1,
                shelf.id,
            ),
        )

        for shelf in ordered_shelves:
            if remaining <= 0:
                break
            used_volume, used_weight = used.get(shelf.id, (ZERO, ZERO))
            free_volume = volume_m3(shelf.width, shelf.length, shelf.height) - used_volume
            free_weight = Decimal(str(shelf.max_weight)) - used_weight
            if free_volume <= 0 or free_weight <= 0:
                continue

            by_volume = free_volume / unit_volume if unit_volume > 0 else Decimal("1e12")
            by_weight = free_weight / unit_weight if unit_weight > 0 else Decimal("1e12")
            capacity = min(by_volume, by_weight, remaining)
            take = capacity.quantize(QUANTITY_STEP, rounding=ROUND_DOWN)
            if take <= 0:
                continue

            key = (shelf.id, product_id, package_type)
            stock_item = existing.get(key)
            if stock_item is None:
                stock_item = StockItem(
                    product_id=product_id,
                    shelf_id=shelf.id,
                    warehouse_id=warehouse_id,
                    quantity=take,
                    package_type=package_type,
                )
                session.add(stock_item)
                existing[key] = stock_item
            else:
                stock_item.quantity = Decimal(str(stock_item.quantity)) + take

            session.add(
                StockMovement(
                    product_id=product_id,
                    shelf_id=shelf.id,
                    warehouse_id=warehouse_id,
                    quantity=take,
                    movement_type=StockMovementType.INBOUND_ORDER,
                    order_id=order_id,
                    created_by_user_id=user_id,
                )
            )

            used[shelf.id] = (
                used_volume + unit_volume * take,
                used_weight + unit_weight * take,
            )
            remaining -= take
            placed += take

        if remaining > 0:
            reason = _get_capacity_shortage_reason(
                shelves,
                used,
                unit_volume,
                unit_weight,
                remaining,
            )
            shortages.append(
                CapacityShortage(
                    product_id=product_id,
                    product_name=product.name,
                    sku_code=product.sku_code,
                    requested=Decimal(str(quantity)),
                    placed=placed,
                    reason=reason,
                )
            )

    await session.flush()
    return shortages

async def check_availability(
    session: AsyncSession,
    warehouse_id: int,
    items: list[tuple[int, Decimal, str]],
    *,
    for_update: bool = False,
) -> list[Shortage]:
    
    available = await get_available_quantities(
        session, warehouse_id, [item[0] for item in items], for_update=for_update
    )
    products = await get_products(session, [item[0] for item in items])

    shortages: list[Shortage] = []
    required: dict[int, Decimal] = {}
    for product_id, quantity, _package_type in items:
        required[product_id] = required.get(product_id, ZERO) + Decimal(str(quantity))

    for product_id, needed in required.items():
        have = available.get(product_id, ZERO)
        if have >= needed:
            continue
        product = products.get(product_id)
        shortages.append(
            Shortage(
                product_id=product_id,
                product_name=product.name if product else f"Товар №{product_id}",
                sku_code=product.sku_code if product else "",
                requested=needed,
                available=have,
            )
        )
    return shortages

async def remove_outgoing(
    session: AsyncSession,
    warehouse_id: int,
    items: list[tuple[int, Decimal, str]],
    *,
    user_id: int | None = None,
    order_id: int | None = None,
) -> None:
    
    shortages = await check_availability(
        session, warehouse_id, items, for_update=True
    )
    if shortages:
        raise InsufficientStockError(shortages)

    products = await get_products(session, [item[0] for item in items])
    stock_items = await get_stock_items(session, warehouse_id, for_update=True)

    stock_items.sort(key=lambda item: (item.product_id, item.shelf_id, item.id))
    by_product: dict[int, list[StockItem]] = {}
    for stock_item in stock_items:
        by_product.setdefault(stock_item.product_id, []).append(stock_item)

    for product_id, quantity, _package_type in items:
        remaining = Decimal(str(quantity))
        product = products.get(product_id)
        unit_volume = (
            volume_m3(product.width, product.length, product.height) if product else ZERO
        )
        unit_weight = Decimal(str(product.weight)) if product else ZERO

        for stock_item in by_product.get(product_id, []):
            if remaining <= 0:
                break
            available = Decimal(str(stock_item.quantity))
            if available <= 0:
                continue
            take = min(available, remaining)

            session.add(
                StockMovement(
                    product_id=product_id,
                    shelf_id=stock_item.shelf_id,
                    warehouse_id=warehouse_id,
                    quantity=-take,
                    movement_type=StockMovementType.OUTBOUND_ORDER,
                    order_id=order_id,
                    created_by_user_id=user_id,
                )
            )

            new_quantity = available - take
            if new_quantity <= 0:
                await session.delete(stock_item)
            else:
                stock_item.quantity = new_quantity
            remaining -= take

        if remaining > 0:  # pragma: no cover - перевірка вище мала б відловити це раніше
            raise InsufficientStockError(
                [
                    Shortage(
                        product_id=product_id,
                        product_name=product.name if product else f"Товар №{product_id}",
                        sku_code=product.sku_code if product else "",
                        requested=Decimal(str(quantity)),
                        available=Decimal("0"),
                    )
                ]
            )

    await session.flush()

async def delete_stock_for_warehouse(session: AsyncSession, warehouse_id: int) -> None:
    
    await session.execute(
        delete(StockMovement).where(StockMovement.warehouse_id == warehouse_id)
    )
    await session.execute(
        delete(StockItem).where(StockItem.warehouse_id == warehouse_id)
    )
    await session.commit()
