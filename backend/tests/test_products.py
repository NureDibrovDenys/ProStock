"""CRUD товарів, категорій, імпорт та експорт."""
from __future__ import annotations

import io

from httpx import AsyncClient
from openpyxl import Workbook

from tests.utils import ADMIN, API, auth, create_category, login, product_payload, unique


async def test_product_crud(client: AsyncClient):
    token = await login(client, ADMIN)
    category_id = await create_category(client, token)

    created = await client.post(f"{API}/products", headers=auth(token), json=product_payload(category_id))
    assert created.status_code == 201, created.text
    product = created.json()
    assert product["category_name"]
    assert product["unit_of_measure"] == "pcs"

    fetched = await client.get(f"{API}/products/{product['product_id']}", headers=auth(token))
    assert fetched.status_code == 200

    patched = await client.patch(
        f"{API}/products/{product['product_id']}",
        headers=auth(token),
        json={"name": "Оновлена назва", "weight": 1.25, "min_stock_level": None},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Оновлена назва"
    assert float(patched.json()["weight"]) == 1.25
    assert patched.json()["min_stock_level"] is None

    deleted = await client.delete(f"{API}/products/{product['product_id']}", headers=auth(token))
    assert deleted.status_code == 204
    assert (await client.get(f"{API}/products/{product['product_id']}", headers=auth(token))).status_code == 404


async def test_product_validation(client: AsyncClient):
    token = await login(client, ADMIN)
    category_id = await create_category(client, token)

    duplicate_payload = product_payload(category_id)
    first = await client.post(f"{API}/products", headers=auth(token), json=duplicate_payload)
    assert first.status_code == 201
    duplicate = await client.post(f"{API}/products", headers=auth(token), json=duplicate_payload)
    assert duplicate.status_code == 409

    negative = await client.post(
        f"{API}/products",
        headers=auth(token),
        json={**product_payload(category_id), "width": -1},
    )
    assert negative.status_code == 422

    missing_category = await client.post(
        f"{API}/products",
        headers=auth(token),
        json={**product_payload(category_id), "category_id": 999_999},
    )
    assert missing_category.status_code == 422

    bad_sku = await client.post(
        f"{API}/products",
        headers=auth(token),
        json={**product_payload(category_id), "sku_code": 'bad"; DROP'},
    )
    assert bad_sku.status_code == 422

    empty_patch = await client.patch(
        f"{API}/products/{first.json()['product_id']}", headers=auth(token), json={}
    )
    assert empty_patch.status_code == 422

    await client.delete(f"{API}/products/{first.json()['product_id']}", headers=auth(token))


async def test_product_search_filter_sort_and_pagination(client: AsyncClient):
    token = await login(client, ADMIN)
    category_id = await create_category(client, token)
    marker = unique("SEARCH")

    for index in range(3):
        payload = product_payload(category_id, sku=f"{marker}-{index}")
        payload["name"] = f"Товар {index}"
        payload["weight"] = 1 + index
        response = await client.post(f"{API}/products", headers=auth(token), json=payload)
        assert response.status_code == 201

    found = await client.get(f"{API}/products", headers=auth(token), params={"search": marker})
    assert found.json()["total"] == 3

    filtered = await client.get(
        f"{API}/products", headers=auth(token), params={"category_id": category_id, "search": marker}
    )
    assert filtered.json()["total"] == 3

    sorted_desc = await client.get(
        f"{API}/products",
        headers=auth(token),
        params={"search": marker, "sort_by": "weight", "sort_order": "desc"},
    )
    weights = [float(item["weight"]) for item in sorted_desc.json()["items"]]
    assert weights == sorted(weights, reverse=True)

    page = await client.get(
        f"{API}/products", headers=auth(token), params={"search": marker, "page_size": 2, "page": 2}
    )
    assert page.json()["pages"] == 2
    assert len(page.json()["items"]) == 1


async def test_category_crud_and_delete_guard(client: AsyncClient):
    token = await login(client, ADMIN)
    category_id = await create_category(client, token)

    categories = await client.get(f"{API}/categories", headers=auth(token))
    assert categories.status_code == 200
    assert any(item["category_id"] == category_id for item in categories.json())

    updated = await client.patch(
        f"{API}/categories/{category_id}", headers=auth(token), json={"description": "Опис"}
    )
    assert updated.status_code == 200 and updated.json()["description"] == "Опис"

    product = await client.post(f"{API}/products", headers=auth(token), json=product_payload(category_id))
    assert product.status_code == 201

    blocked = await client.delete(f"{API}/categories/{category_id}", headers=auth(token))
    assert blocked.status_code == 409

    await client.delete(f"{API}/products/{product.json()['product_id']}", headers=auth(token))
    assert (await client.delete(f"{API}/categories/{category_id}", headers=auth(token))).status_code == 204


async def test_csv_import_report(client: AsyncClient):
    token = await login(client, ADMIN)
    marker = unique("IMP")
    content = (
        "sku_code;name;category;unit_of_measure;width;length;height;weight;min_stock_level\n"
        f"{marker}-1;Товар 1;Категорія {marker};шт;0,1;0,2;0,3;1,5;4\n"
        f"{marker}-2;Товар 2;Категорія {marker};kg;0,2;0,2;0,2;2;5\n"
        f"{marker}-BAD;Зламаний;Категорія {marker};pcs;abc;1;1;1;\n"
        f"{marker}-1;Дублікат;Категорія {marker};pcs;1;1;1;1;\n"
    ).encode()

    response = await client.post(
        f"{API}/products/import",
        headers=auth(token),
        files={"file": (f"{marker}.csv", content, "text/csv")},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["total"] == 4
    assert report["created"] == 2
    assert report["failed"] == 2
    assert report["categories_created"] == 1
    assert {error["row"] for error in report["errors"]} == {4, 5}
    assert {error["field"] for error in report["errors"]} == {"width", "sku_code"}

    # Повторний імпорт оновлює існуючі товари
    again = await client.post(
        f"{API}/products/import",
        headers=auth(token),
        files={"file": (f"{marker}.csv", content, "text/csv")},
    )
    assert again.json()["updated"] == 2
    assert again.json()["created"] == 0


async def test_xlsx_import(client: AsyncClient):
    token = await login(client, ADMIN)
    marker = unique("XLS")

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["sku_code", "name", "category", "unit_of_measure", "width", "length", "height", "weight", "min_stock_level"])
    sheet.append([marker, "Товар з Excel", f"Excel {marker}", "box", 0.5, 0.5, 0.5, 9.5, 1])
    buffer = io.BytesIO()
    workbook.save(buffer)

    response = await client.post(
        f"{API}/products/import",
        headers=auth(token),
        files={
            "file": (
                f"{marker}.xlsx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["created"] == 1


async def test_import_rejects_bad_files(client: AsyncClient):
    token = await login(client, ADMIN)

    bad_headers = await client.post(
        f"{API}/products/import",
        headers=auth(token),
        files={"file": ("bad.csv", b"foo;bar\n1;2\n", "text/csv")},
    )
    assert bad_headers.status_code == 422

    bad_format = await client.post(
        f"{API}/products/import",
        headers=auth(token),
        files={"file": ("bad.exe", b"binary", "application/octet-stream")},
    )
    assert bad_format.status_code == 422

    empty = await client.post(
        f"{API}/products/import",
        headers=auth(token),
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert empty.status_code == 422


async def test_exports(client: AsyncClient):
    token = await login(client, ADMIN)
    category_id = await create_category(client, token)
    marker = unique("EXP")
    product = await client.post(
        f"{API}/products", headers=auth(token), json=product_payload(category_id, sku=marker)
    )
    assert product.status_code == 201

    csv_response = await client.get(
        f"{API}/products/export", headers=auth(token), params={"format": "csv", "search": marker}
    )
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["content-type"]
    assert "attachment" in csv_response.headers["content-disposition"]
    assert csv_response.content.startswith(b"\xef\xbb\xbf")
    assert marker.encode() in csv_response.content
    assert b"sku_code;name;category" in csv_response.content

    xlsx_response = await client.get(
        f"{API}/products/export", headers=auth(token), params={"format": "xlsx", "search": marker}
    )
    assert xlsx_response.status_code == 200
    assert "spreadsheetml" in xlsx_response.headers["content-type"]
    assert xlsx_response.content[:2] == b"PK"
    assert xlsx_response.headers["x-total-count"] == "1"

    template = await client.get(
        f"{API}/products/import/template", headers=auth(token), params={"format": "xlsx"}
    )
    assert template.status_code == 200
    assert template.content[:2] == b"PK"


async def test_export_respects_filters(client: AsyncClient):
    token = await login(client, ADMIN)
    category_id = await create_category(client, token)
    marker = unique("FLT")
    await client.post(f"{API}/products", headers=auth(token), json=product_payload(category_id, sku=f"{marker}-A"))
    other = await client.post(
        f"{API}/products",
        headers=auth(token),
        json={**product_payload(category_id, sku=f"{marker}-B"), "unit_of_measure": "kg"},
    )
    assert other.status_code == 201

    response = await client.get(
        f"{API}/products/export",
        headers=auth(token),
        params={"format": "csv", "search": marker, "unit_of_measure": "kg"},
    )
    assert response.headers["x-total-count"] == "1"
    assert f"{marker}-B".encode() in response.content
    assert f"{marker}-A".encode() not in response.content
