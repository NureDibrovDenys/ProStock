
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.stock import service


def create_product(product_id=1, width="1", length="1",
                   height="1", weight="10"):
    return SimpleNamespace(
        id=product_id,
        name=f"Product {product_id}",
        sku_code=f"SKU-{product_id}",
        width=Decimal(width),
        length=Decimal(length),
        height=Decimal(height),
        weight=Decimal(weight),
    )


def create_shelf(shelf_id, width="2", length="2",
                 height="2", max_weight="100"):
    return SimpleNamespace(
        id=shelf_id,
        width=Decimal(width),
        length=Decimal(length),
        height=Decimal(height),
        max_weight=Decimal(max_weight),
    )


async def run_placement(monkeypatch, shelves, products, items, used=None):
    session = Mock()
    session.flush = AsyncMock()

    monkeypatch.setattr(
        service, "_active_shelves",
        AsyncMock(return_value=shelves),
    )
    monkeypatch.setattr(
        service, "_used_capacity",
        AsyncMock(return_value=dict(used or {})),
    )
    monkeypatch.setattr(
        service, "get_products",
        AsyncMock(return_value={p.id: p for p in products}),
    )
    monkeypatch.setattr(
        service, "get_stock_items",
        AsyncMock(return_value=[]),
    )

    stock_item = Mock(side_effect=SimpleNamespace)
    movement = Mock(side_effect=SimpleNamespace)

    monkeypatch.setattr(service, "StockItem", stock_item)
    monkeypatch.setattr(service, "StockMovement", movement)

    shortages = await service.place_incoming(
        session, warehouse_id=1, items=items
    )

    placements = [
        call.kwargs for call in movement.call_args_list
    ]

    session.flush.assert_awaited_once()

    return shortages, placements


@pytest.mark.parametrize(
    "width, length, height, expected",
    [
        ("1", "1", "1", True),
        ("3", "1", "1", False),
        ("1", "3", "1", False),
        ("1", "1", "3", False),
        ("2", "2", "2", True),
    ],
)
def test_fits_dimensions(width, length, height, expected):
    product = create_product(
        width=width, length=length, height=height
    )
    shelf = create_shelf(1)

    assert service._fits_dimensions(product, shelf) == expected


@pytest.mark.asyncio
async def test_best_fit_selection(monkeypatch):
    product = create_product()

    shelves = [
        create_shelf(1, width="3"),
        create_shelf(2, width="1"),
        create_shelf(3, width="2"),
    ]

    shortages, placements = await run_placement(
        monkeypatch, shelves, [product],
        [(1, Decimal("1"), "box")],
    )

    assert shortages == []
    assert len(placements) == 1
    assert placements[0]["shelf_id"] == 2


@pytest.mark.asyncio
async def test_weight_limit(monkeypatch):
    product = create_product(weight="10")

    shelves = [
        create_shelf(1, width="1", max_weight="5"),
        create_shelf(2, max_weight="100"),
    ]

    shortages, placements = await run_placement(
        monkeypatch, shelves, [product],
        [(1, Decimal("1"), "box")],
    )

    assert shortages == []
    assert sum(p["quantity"] for p in placements) == Decimal("1")
    assert sum(
        p["quantity"] * product.weight
        for p in placements if p["shelf_id"] == 1
    ) <= Decimal("5")


@pytest.mark.asyncio
async def test_skip_shelf_with_wrong_dimensions(monkeypatch):
    product = create_product(width="1.5")

    shelves = [
        create_shelf(1, width="1"),
        create_shelf(2, width="2"),
    ]

    shortages, placements = await run_placement(
        monkeypatch, shelves, [product],
        [(1, Decimal("1"), "box")],
    )

    assert shortages == []
    assert len(placements) == 1
    assert placements[0]["shelf_id"] == 2


@pytest.mark.asyncio
async def test_dimensions_shortage(monkeypatch):
    product = create_product(width="3")
    shelves = [create_shelf(1)]

    shortages, placements = await run_placement(
        monkeypatch, shelves, [product],
        [(1, Decimal("1"), "box")],
    )

    assert placements == []
    assert len(shortages) == 1
    assert shortages[0].unplaced == Decimal("1")
    assert "габарити" in shortages[0].reason


@pytest.mark.asyncio
async def test_decreasing_volume_order(monkeypatch):
    small = create_product(1)
    large = create_product(2, width="2")

    shortages, placements = await run_placement(
        monkeypatch, [create_shelf(1)], [small, large],
        [
            (1, Decimal("1"), "box"),
            (2, Decimal("1"), "box"),
        ],
    )

    assert shortages == []
    assert [p["product_id"] for p in placements] == [2, 1]


@pytest.mark.asyncio
async def test_decreasing_weight_order(monkeypatch):
    light = create_product(1, weight="5")
    heavy = create_product(2, weight="20")

    shortages, placements = await run_placement(
        monkeypatch, [create_shelf(1)], [light, heavy],
        [
            (1, Decimal("1"), "box"),
            (2, Decimal("1"), "box"),
        ],
    )

    assert shortages == []
    assert [p["product_id"] for p in placements] == [2, 1]


@pytest.mark.asyncio
async def test_used_capacity(monkeypatch):
    product = create_product()

    shelves = [
        create_shelf(1, width="1"),
        create_shelf(2),
    ]

    used = {
        1: (Decimal("4"), Decimal("20")),
    }

    shortages, placements = await run_placement(
        monkeypatch, shelves, [product],
        [(1, Decimal("1"), "box")],
        used=used,
    )

    assert shortages == []
    assert len(placements) == 1
    assert placements[0]["shelf_id"] == 2


@pytest.mark.asyncio
async def test_partial_placement(monkeypatch):
    product = create_product(weight="10")
    shelves = [create_shelf(1, max_weight="20")]

    shortages, placements = await run_placement(
        monkeypatch, shelves, [product],
        [(1, Decimal("5"), "box")],
    )

    assert len(placements) == 1
    assert placements[0]["quantity"] == Decimal("2")

    assert len(shortages) == 1
    assert shortages[0].requested == Decimal("5")
    assert shortages[0].placed == Decimal("2")
    assert shortages[0].unplaced == Decimal("3")
    assert "вантажопідйомності" in shortages[0].reason


@pytest.mark.asyncio
async def test_no_active_shelves(monkeypatch):
    product = create_product()

    shortages, placements = await run_placement(
        monkeypatch, [], [product],
        [(1, Decimal("1"), "box")],
    )

    assert placements == []
    assert len(shortages) == 1
    assert shortages[0].unplaced == Decimal("1")
    assert "активної полиці" in shortages[0].reason
