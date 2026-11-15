"""Ієрархія стелаж → полиця: цілісність даних і відображення заповненості.

Доповнює test_shelf_fill.py (порожня полиця, сума по стелажу, зведення, мапа,
розподіл по полицях, неактивна полиця) випадками, яких там немає.
"""
from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient

from tests.utils import (
    ADMIN,
    API,
    auth,
    create_category,
    create_product,
    create_supplier,
    create_warehouse_with_racks,
    login,
    unique,
)

INBOUND = f"{API}/inbound-orders"
STOCK = f"{API}/stock"

# 2 м³ і 500 кг на полицю; товар — 0,05 м³ і 10 кг (по об'єму влазить 40 шт.)
SHELF = {"width": "2", "length": "1", "height": "1", "max_weight": "500"}
PRODUCT = {"width": 0.5, "length": 0.5, "height": 0.2, "weight": 10.0, "unit_of_measure": "box"}


async def _fixture(client: AsyncClient, token: str, racks: list[dict]) -> dict:
    warehouse = await create_warehouse_with_racks(racks)
    category_id = await create_category(client, token)
    return {
        **warehouse,
        "product_id": await create_product(client, token, category_id, name="Коробка", **PRODUCT),
        "supplier_id": await create_supplier(client, token),
    }


async def _stock_in(client: AsyncClient, token: str, fixture: dict, quantity: str) -> None:
    created = await client.post(
        INBOUND,
        headers=auth(token),
        json={
            "supplier_id": fixture["supplier_id"],
            "warehouse_id": fixture["warehouse_id"],
            "invoice_number": unique("INV"),
            "expected_delivery_date": "2026-12-01T00:00:00Z",
            "items": [{"product_id": fixture["product_id"], "quantity": quantity, "package_type": "box"}],
        },
    )
    assert created.status_code == 201, created.text
    posted = await client.post(f"{INBOUND}/{created.json()['inbound_order_id']}/post", headers=auth(token))
    assert posted.status_code == 200, posted.text


async def _available(client: AsyncClient, token: str, fixture: dict) -> Decimal:
    response = await client.get(
        STOCK,
        headers=auth(token),
        params={"warehouse_id": fixture["warehouse_id"], "product_ids": fixture["product_id"]},
    )
    rows = response.json()
    return Decimal(rows[0]["available"]) if rows else Decimal("0")


def _rack_url(fixture: dict, rack_code: str) -> str:
    return f"{API}/warehouses/{fixture['warehouse_id']}/racks/{rack_code}"


# ── Цілісність ієрархії ─────────────────────────────────────────────────────


async def test_shelf_with_stock_cannot_be_deleted(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token, [{"code": "A", "shelves": [dict(SHELF, code="A-1")]}])
    await _stock_in(client, token, fixture, "10")
    shelf_id = fixture["racks"][0]["shelf_ids"][0]

    response = await client.delete(f"{_rack_url(fixture, 'A')}/shelves/{shelf_id}", headers=auth(token))
    assert response.status_code == 409, response.text
    assert await _available(client, token, fixture) == Decimal("10")


async def test_empty_shelf_can_be_deleted_and_rack_totals_shrink(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(
        client, token, [{"code": "A", "shelves": [dict(SHELF, code="A-1"), dict(SHELF, code="A-2")]}]
    )
    await _stock_in(client, token, fixture, "10")  # усе ляже на A-1
    empty_shelf = fixture["racks"][0]["shelf_ids"][1]

    response = await client.delete(f"{_rack_url(fixture, 'A')}/shelves/{empty_shelf}", headers=auth(token))
    assert response.status_code == 204, response.text

    rack = (await client.get(_rack_url(fixture, "A"), headers=auth(token))).json()
    assert [s["shelf_code"] for s in rack["shelves"]] == ["A-1"]
    assert Decimal(str(rack["total_volume_m3"])) == Decimal("2")
    assert rack["volume_fill_percent"] == 25.0  # 0,5 м³ із 2 м³ замість 4 м³


async def test_shelf_with_stock_is_reported_as_occupied(client: AsyncClient):
    """Таблиця полиць на фронті показує «1 / 1 палет» за полем is_occupied / occupied."""
    token = await login(client, ADMIN)
    fixture = await _fixture(
        client, token, [{"code": "A", "shelves": [dict(SHELF, code="A-1"), dict(SHELF, code="A-2")]}]
    )
    await _stock_in(client, token, fixture, "10")

    rack = (await client.get(_rack_url(fixture, "A"), headers=auth(token))).json()
    by_code = {s["shelf_code"]: s for s in rack["shelves"]}
    assert by_code["A-1"]["items_count"] > 0
    assert by_code["A-1"]["occupied"] == 1
    assert by_code["A-2"]["occupied"] == 0

    shelves = (await client.get(f"{_rack_url(fixture, 'A')}/shelves", headers=auth(token))).json()
    occupied = {s["shelf_code"]: s["is_occupied"] for s in shelves}
    assert occupied == {"A-1": True, "A-2": False}


async def test_removing_rack_with_stock_from_map_is_rejected(client: AsyncClient):
    """Збереження мапи без стелажа видаляє його полиці каскадом — разом із залишками."""
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token, [{"code": "A", "shelves": [dict(SHELF, code="A-1")]}])
    await _stock_in(client, token, fixture, "10")

    response = await client.put(
        f"{API}/warehouses/{fixture['warehouse_id']}/map", headers=auth(token), json={"racks": []}
    )
    assert response.status_code == 409, response.text
    assert await _available(client, token, fixture) == Decimal("10")
    assert (await client.get(_rack_url(fixture, "A"), headers=auth(token))).status_code == 200


async def test_removing_empty_rack_from_map_is_allowed(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token, [{"code": "A", "shelves": [dict(SHELF, code="A-1")]}])

    response = await client.put(
        f"{API}/warehouses/{fixture['warehouse_id']}/map", headers=auth(token), json={"racks": []}
    )
    assert response.status_code == 200, response.text
    assert (await client.get(_rack_url(fixture, "A"), headers=auth(token))).status_code == 404


async def test_shelf_code_is_unique_within_rack_only(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(
        client,
        token,
        [{"code": "A", "shelves": [dict(SHELF, code="1")]}, {"code": "B", "shelves": [dict(SHELF, code="B-1")]}],
    )
    body = {"code": "1", "width": "1", "length": "1", "height": "1", "max_weight": "100"}

    duplicate = await client.post(f"{_rack_url(fixture, 'A')}/shelves", headers=auth(token), json=body)
    assert duplicate.status_code == 409, duplicate.text

    other_rack = await client.post(f"{_rack_url(fixture, 'B')}/shelves", headers=auth(token), json=body)
    assert other_rack.status_code == 201, other_rack.text
    assert other_rack.json()["rack_id"] == fixture["racks"][1]["rack_id"]


async def test_shelf_is_addressed_only_through_its_rack(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(
        client,
        token,
        [{"code": "A", "shelves": [dict(SHELF, code="A-1")]}, {"code": "B", "shelves": [dict(SHELF, code="B-1")]}],
    )
    shelf_id = fixture["racks"][0]["shelf_ids"][0]
    wrong = f"{_rack_url(fixture, 'B')}/shelves/{shelf_id}"

    assert (await client.get(wrong, headers=auth(token))).status_code == 404
    assert (await client.patch(wrong, headers=auth(token), json={"max_weight": "1"})).status_code == 404
    assert (await client.delete(wrong, headers=auth(token))).status_code == 404
    assert (await client.get(f"{_rack_url(fixture, 'A')}/shelves/{shelf_id}", headers=auth(token))).status_code == 200


async def test_shelf_patch_rejects_null_for_required_fields(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token, [{"code": "A", "shelves": [dict(SHELF, code="A-1")]}])
    url = f"{_rack_url(fixture, 'A')}/shelves/{fixture['racks'][0]['shelf_ids'][0]}"

    for field in ("width", "length", "height", "max_weight", "status"):
        response = await client.patch(url, headers=auth(token), json={field: None})
        assert response.status_code == 422, (field, response.text)


# ── Відображення заповненості ───────────────────────────────────────────────


async def test_rack_fill_is_weighted_by_shelf_volume(client: AsyncClient):
    """Полиці різного розміру: заповненість стелажа — частка об'єму, а не середнє відсотків."""
    token = await login(client, ADMIN)
    small = dict(SHELF, code="A-1", width="1", length="0.5", height="0.1")  # 0,05 м³
    fixture = await _fixture(client, token, [{"code": "A", "shelves": [small, dict(SHELF, code="A-2")]}])
    await _stock_in(client, token, fixture, "1")  # 0,05 м³ — рівно заповнює малу полицю

    rack = (await client.get(_rack_url(fixture, "A"), headers=auth(token))).json()
    by_code = {s["shelf_code"]: s for s in rack["shelves"]}
    assert by_code["A-1"]["volume_fill_percent"] == 100.0
    assert by_code["A-2"]["volume_fill_percent"] == 0.0
    # 0,05 із 2,05 м³ ≈ 2,4% (бекенд округлює до 0,1), а не (100 + 0) / 2 = 50%
    assert rack["volume_fill_percent"] == 2.4

    summary = next(r for r in (await client.get(f"{API}/warehouses/{fixture['warehouse_id']}/racks", headers=auth(token))).json() if r["rack_code"] == "A")
    assert summary["fill_percent"] == rack["volume_fill_percent"]


async def test_rack_without_shelves_reports_zero_fill(client: AsyncClient):
    """Стелаж, у якого прибрали всі полиці (так само виглядає щойно намальований на мапі)."""
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token, [{"code": "A", "shelves": [dict(SHELF, code="A-1")]}])
    shelf_id = fixture["racks"][0]["shelf_ids"][0]
    deleted = await client.delete(f"{_rack_url(fixture, 'A')}/shelves/{shelf_id}", headers=auth(token))
    assert deleted.status_code == 204, deleted.text

    rack = await client.get(_rack_url(fixture, "A"), headers=auth(token))
    assert rack.status_code == 200, rack.text
    assert rack.json()["shelves"] == []
    assert rack.json()["volume_fill_percent"] == 0.0

    summary = (await client.get(f"{API}/warehouses/{fixture['warehouse_id']}/racks", headers=auth(token))).json()
    assert summary[0]["fill_percent"] == 0.0
    # shelves_count тут - планова кількість із мапи (fallback, коли записів полиць немає), тож не перевіряємо


async def test_shrinking_loaded_shelf_marks_it_overloaded(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token, [{"code": "A", "shelves": [dict(SHELF, code="A-1")]}])
    await _stock_in(client, token, fixture, "20")  # 1 м³ і 200 кг
    url = f"{_rack_url(fixture, 'A')}/shelves/{fixture['racks'][0]['shelf_ids'][0]}"

    shrunk = await client.patch(url, headers=auth(token), json={"max_weight": "100"})
    assert shrunk.status_code == 200, shrunk.text
    assert shrunk.json()["overloaded"] is True
    assert shrunk.json()["weight_fill_percent"] == 200.0
    assert shrunk.json()["free_weight_kg"] == 0.0

    rack = (await client.get(_rack_url(fixture, "A"), headers=auth(token))).json()
    assert rack["shelves"][0]["overloaded"] is True
