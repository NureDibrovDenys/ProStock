from __future__ import annotations
from dataclasses import dataclass
from httpx import AsyncClient
from tests.utils import ADMIN, API, auth, login, unique

WAREHOUSES = f"{API}/warehouses"
FORBIDDEN_OR_HIDDEN = (403, 404)

@dataclass
class Setup:
    admin_token: str
    wh_a: int           # склад A (стартовий, id=1)
    wh_b: int           # склад B (створений у тесті)
    rack_a: str         # код стелажа у складі A
    rack_b: str         # код стелажа у складі B
    manager_a: str      # токен менеджера складу A
    manager_b: str      # токен менеджера складу B
    storekeeper_a: str  # токен комірника складу A


def _map_with_rack(rack_code: str) -> dict:
    return {
        "grid": {"cell_size": 1.0, "grid_width": 40, "grid_height": 20},
        "walls": [
            {"vertex_order": 1, "coord_x": 0, "coord_y": 0},
            {"vertex_order": 2, "coord_x": 40, "coord_y": 0},
            {"vertex_order": 3, "coord_x": 40, "coord_y": 20},
            {"vertex_order": 4, "coord_x": 0, "coord_y": 20},
        ],
        "partitions": [],
        "obstacles": [],
        "entry_points": [{"point_name": "Вхід", "point_type": "general_entry", "coord_x": 0, "coord_y": 10}],
        "zones": [],
        "racks": [
            {"rack_code": rack_code, "coord_x": 12, "coord_y": 2, "width": 1.2, "length": 6,
             "rotation_angle": 0, "shelves_count": 4},
        ],
    }

async def _create_manager(client: AsyncClient, admin_token: str, warehouse_id: int) -> str:
    email = f"{unique('mgr')}@prostock.com"
    response = await client.post(
        f"{API}/users",
        headers=auth(admin_token),
        json={
            "first_name": "Марія",
            "last_name": "Менеджер",
            "user_email": email,
            "password": "Manager12345",
            "role": "warehouse_manager",
            "warehouse_id": warehouse_id,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["warehouse_id"] == warehouse_id
    return await login(client, (email, "Manager12345"))

async def _setup(client: AsyncClient) -> Setup:
    admin_token = await login(client, ADMIN)

    created = await client.post(
        WAREHOUSES,
        headers=auth(admin_token),
        json={"name": unique("Склад B"), "address": "м. Львів, вул. Городоцька, 210", "total_area": 800},
    )
    assert created.status_code == 201, created.text
    wh_b = created.json()["warehouse_id"]
    wh_a = 1

    rack_a, rack_b = unique("A"), unique("B")
    for warehouse_id, rack in ((wh_a, rack_a), (wh_b, rack_b)):
        saved = await client.put(
            f"{WAREHOUSES}/{warehouse_id}/map", headers=auth(admin_token), json=_map_with_rack(rack)
        )
        assert saved.status_code == 200, saved.text

    manager_a = await _create_manager(client, admin_token, wh_a)
    manager_b = await _create_manager(client, admin_token, wh_b)

    sk_email = f"{unique('sk')}@prostock.com"
    sk = await client.post(
        f"{API}/managers/storekeepers",
        headers=auth(manager_a),
        json={"first_name": "Іван", "last_name": "Комірник", "user_email": sk_email, "password": "Worker12345"},
    )
    assert sk.status_code == 201, sk.text
    storekeeper_a = await login(client, (sk_email, "Worker12345"))

    return Setup(admin_token, wh_a, wh_b, rack_a, rack_b, manager_a, manager_b, storekeeper_a)


def _shelf_payload() -> dict:
    return {"code": unique("S"), "width": 1.2, "length": 0.8, "height": 0.5, "max_weight": 150}

#список складів
async def test_admin_sees_both_warehouses_manager_cannot_list(client: AsyncClient):
    s = await _setup(client)

    listing = await client.get(WAREHOUSES, headers=auth(s.admin_token))
    assert listing.status_code == 200
    ids = {w["warehouse_id"] for w in listing.json()}
    assert {s.wh_a, s.wh_b} <= ids

    for token in (s.manager_a, s.manager_b, s.storekeeper_a):
        assert (await client.get(WAREHOUSES, headers=auth(token))).status_code == 403

#тест власного складу
async def test_manager_can_use_own_warehouse(client: AsyncClient):
    s = await _setup(client)

    assert (await client.get(f"{WAREHOUSES}/{s.wh_a}", headers=auth(s.manager_a))).status_code == 200
    assert (await client.get(f"{WAREHOUSES}/{s.wh_a}/map", headers=auth(s.manager_a))).status_code == 200

    racks = await client.get(f"{WAREHOUSES}/{s.wh_a}/racks", headers=auth(s.manager_a))
    assert racks.status_code == 200
    assert s.rack_a in {r["rack_code"] for r in racks.json()}
    assert (await client.get(f"{WAREHOUSES}/{s.wh_a}/racks/{s.rack_a}", headers=auth(s.manager_a))).status_code == 200

    shelf = await client.post(
        f"{WAREHOUSES}/{s.wh_a}/racks/{s.rack_a}/shelves", headers=auth(s.manager_a), json=_shelf_payload()
    )
    assert shelf.status_code == 201, shelf.text

#мапа чужого складу
async def test_manager_cannot_open_or_edit_foreign_map(client: AsyncClient):
    s = await _setup(client)

    assert (await client.get(f"{WAREHOUSES}/{s.wh_b}/map", headers=auth(s.manager_a))).status_code == 403
    assert (await client.get(f"{WAREHOUSES}/{s.wh_a}/map", headers=auth(s.manager_b))).status_code == 403
    assert (await client.get(f"{WAREHOUSES}/{s.wh_b}/map", headers=auth(s.storekeeper_a))).status_code == 403

    own = await client.put(f"{WAREHOUSES}/{s.wh_a}/map", headers=auth(s.manager_a), json=_map_with_rack("X-01"))
    assert own.status_code == 403


async def test_manager_cannot_modify_warehouses(client: AsyncClient):
    s = await _setup(client)
    body = {"name": unique("Хакер"), "address": None, "total_area": 1}

    assert (await client.post(WAREHOUSES, headers=auth(s.manager_a), json=body)).status_code == 403
    assert (await client.patch(f"{WAREHOUSES}/{s.wh_a}", headers=auth(s.manager_a), json={"name": "X"})).status_code == 403
    assert (await client.delete(f"{WAREHOUSES}/{s.wh_a}", headers=auth(s.manager_a))).status_code == 403

#перевірка чужого складу
async def test_manager_cannot_read_foreign_warehouse(client: AsyncClient):
    s = await _setup(client)

    response = await client.get(f"{WAREHOUSES}/{s.wh_b}", headers=auth(s.manager_a))
    assert response.status_code in FORBIDDEN_OR_HIDDEN, response.text


async def test_manager_cannot_read_foreign_racks(client: AsyncClient):
    s = await _setup(client)

    racks = await client.get(f"{WAREHOUSES}/{s.wh_b}/racks", headers=auth(s.manager_a))
    assert racks.status_code in FORBIDDEN_OR_HIDDEN, racks.text

    rack = await client.get(f"{WAREHOUSES}/{s.wh_b}/racks/{s.rack_b}", headers=auth(s.manager_a))
    assert rack.status_code in FORBIDDEN_OR_HIDDEN, rack.text


async def test_manager_cannot_create_shelf_in_foreign_warehouse(client: AsyncClient):
    s = await _setup(client)

    response = await client.post(
        f"{WAREHOUSES}/{s.wh_b}/racks/{s.rack_b}/shelves", headers=auth(s.manager_a), json=_shelf_payload()
    )
    assert response.status_code in FORBIDDEN_OR_HIDDEN, response.text


async def test_manager_cannot_change_or_delete_foreign_shelf(client: AsyncClient):
    s = await _setup(client)
    base = f"{WAREHOUSES}/{s.wh_b}/racks/{s.rack_b}/shelves"

    created = await client.post(base, headers=auth(s.manager_b), json=_shelf_payload())
    assert created.status_code == 201, created.text
    shelf_id = created.json()["shelf_id"]

    patched = await client.patch(f"{base}/{shelf_id}", headers=auth(s.manager_a), json={"max_weight": 1})
    assert patched.status_code in FORBIDDEN_OR_HIDDEN, patched.text

    deleted = await client.delete(f"{base}/{shelf_id}", headers=auth(s.manager_a))
    assert deleted.status_code in FORBIDDEN_OR_HIDDEN, deleted.text

    rack = await client.get(f"{WAREHOUSES}/{s.wh_b}/racks/{s.rack_b}", headers=auth(s.manager_b))
    assert shelf_id in {sh["shelf_id"] for sh in rack.json()["shelves"]}

#перевірка прав комірника
async def test_storekeeper_cannot_edit_shelves_and_sees_only_own(client: AsyncClient):
    s = await _setup(client)

    own_rack = await client.get(f"{WAREHOUSES}/{s.wh_a}/racks/{s.rack_a}", headers=auth(s.storekeeper_a))
    assert own_rack.status_code == 200

    create = await client.post(
        f"{WAREHOUSES}/{s.wh_a}/racks/{s.rack_a}/shelves", headers=auth(s.storekeeper_a), json=_shelf_payload()
    )
    assert create.status_code == 403

    foreign = await client.get(f"{WAREHOUSES}/{s.wh_b}/racks/{s.rack_b}", headers=auth(s.storekeeper_a))
    assert foreign.status_code in FORBIDDEN_OR_HIDDEN, foreign.text

#перевірка менеджера без складу і з зняттям прив'язки
async def test_manager_loses_access_after_detach(client: AsyncClient):
    s = await _setup(client)

    me = (await client.get(f"{API}/auth/me", headers=auth(s.manager_b))).json()
    detached = await client.put(
        f"{API}/users/{me['user_id']}/warehouse", headers=auth(s.admin_token), json={"warehouse_id": None}
    )
    assert detached.status_code == 200, detached.text

    assert (await client.get(f"{WAREHOUSES}/{s.wh_b}/map", headers=auth(s.manager_b))).status_code == 403
    response = await client.get(f"{WAREHOUSES}/{s.wh_b}/racks", headers=auth(s.manager_b))
    assert response.status_code in FORBIDDEN_OR_HIDDEN, response.text

#переназначення менеджера на інший склад
async def test_manager_moved_to_other_warehouse_sees_only_new_one(client: AsyncClient):
    s = await _setup(client)

    me = (await client.get(f"{API}/auth/me", headers=auth(s.manager_b))).json()
    moved = await client.put(
        f"{API}/users/{me['user_id']}/warehouse", headers=auth(s.admin_token), json={"warehouse_id": s.wh_a}
    )
    assert moved.status_code == 200, moved.text

    assert (await client.get(f"{WAREHOUSES}/{s.wh_a}/map", headers=auth(s.manager_b))).status_code == 200
    assert (await client.get(f"{WAREHOUSES}/{s.wh_b}/map", headers=auth(s.manager_b))).status_code == 403