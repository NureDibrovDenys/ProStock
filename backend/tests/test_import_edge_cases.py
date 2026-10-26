"""Крайові випадки імпорту: ліміти, формати, типи, дублікати."""
from __future__ import annotations

import io

from httpx import AsyncClient
from openpyxl import Workbook

from tests.utils import ADMIN, API, auth, create_category, login, unique

HEADER = "sku_code;name;category;unit_of_measure;width;length;height;weight;min_stock_level\n"


async def test_import_rejects_file_over_size_limit(client: AsyncClient):
    token = await login(client, ADMIN)
    # 5 МБ + запас: перевірка розміру спрацьовує до парсингу
    oversized = b"a" * (5 * 1024 * 1024 + 1024)

    response = await client.post(
        f"{API}/products/import",
        headers=auth(token),
        files={"file": ("huge.csv", oversized, "text/csv")},
    )
    assert response.status_code == 413, response.text
    assert "завеликий" in response.json()["detail"].lower()


async def test_import_rejects_too_many_rows(client: AsyncClient):
    token = await login(client, ADMIN)
    marker = unique("MANY")
    rows = [HEADER]
    for index in range(5001):
        rows.append(f"{marker}-{index};Товар {index};Категорія;шт;0,1;0,1;0,1;0,1;\n")
    content = "".join(rows).encode()

    response = await client.post(
        f"{API}/products/import",
        headers=auth(token),
        files={"file": ("many.csv", content, "text/csv")},
    )
    assert response.status_code == 422, response.text
    assert "Забагато рядків" in response.json()["detail"]


async def test_import_reports_unknown_unit_per_field(client: AsyncClient):
    token = await login(client, ADMIN)
    marker = unique("UNIT")
    content = (
        HEADER
        + f"{marker};Товар;Категорія;літр;0,1;0,1;0,1;0,1;\n"
        + f"{marker}-OK;Товар OK;Категорія;палета;0,1;0,1;0,1;0,1;\n"
    ).encode()

    response = await client.post(
        f"{API}/products/import",
        headers=auth(token),
        files={"file": ("unit.csv", content, "text/csv")},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["created"] == 1
    assert report["failed"] == 1
    error = report["errors"][0]
    assert error["row"] == 2
    assert error["field"] == "unit_of_measure"
    assert "одиниця" in error["message"].lower()


async def test_import_reports_missing_required_values(client: AsyncClient):
    token = await login(client, ADMIN)
    marker = unique("MISS")
    content = (
        HEADER
        + f"{marker};Без розмірів;Категорія;pcs;;0,1;0,1;0,1;\n"
        + f";Без SKU;Категорія;pcs;0,1;0,1;0,1;0,1;\n"
        + f"{marker}-NEG;Від'ємна вага;Категорія;pcs;0,1;0,1;0,1;-2;\n"
    ).encode()

    response = await client.post(
        f"{API}/products/import",
        headers=auth(token),
        files={"file": ("missing.csv", content, "text/csv")},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["created"] == 0
    assert report["failed"] == 3
    fields = {error["field"] for error in report["errors"]}
    assert "width" in fields
    assert "sku_code" in fields
    assert "weight" in fields


async def test_import_reports_duplicate_sku_in_file(client: AsyncClient):
    token = await login(client, ADMIN)
    marker = unique("DUPS")
    content = (
        HEADER
        + f"{marker};Перший;Категорія;pcs;0,1;0,1;0,1;0,1;\n"
        + f"{marker};Другий;Категорія;pcs;0,2;0,2;0,2;0,2;\n"
        + f"{marker};Третій;Категорія;pcs;0,3;0,3;0,3;0,3;\n"
    ).encode()

    response = await client.post(
        f"{API}/products/import",
        headers=auth(token),
        files={"file": ("dups.csv", content, "text/csv")},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["created"] == 1
    assert report["failed"] == 2
    assert all("Дублікат" in error["message"] for error in report["errors"])


async def test_import_rejects_broken_xlsx(client: AsyncClient):
    token = await login(client, ADMIN)

    response = await client.post(
        f"{API}/products/import",
        headers=auth(token),
        files={
            "file": (
                "broken.xlsx",
                b"this-is-not-a-zip-file",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 422, response.text
    assert "Excel" in response.json()["detail"]


async def test_import_xlsx_without_required_headers(client: AsyncClient):
    token = await login(client, ADMIN)
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["sku_code", "name"])
    sheet.append(["X-1", "Товар"])
    buffer = io.BytesIO()
    workbook.save(buffer)

    response = await client.post(
        f"{API}/products/import",
        headers=auth(token),
        files={
            "file": (
                "headers.xlsx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 422, response.text
    assert "бракує обов" in response.json()["detail"]


async def test_import_handles_csv_with_bom_and_crlf(client: AsyncClient):
    token = await login(client, ADMIN)
    marker = unique("BOM")
    content = (
        HEADER.replace("\n", "\r\n")
        + f"{marker};BOM товар;Категорія;шт;0,1;0,1;0,1;0,1;\r\n"
    ).encode("utf-8-sig")

    response = await client.post(
        f"{API}/products/import",
        headers=auth(token),
        files={"file": ("bom.csv", content, "text/csv")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["created"] == 1


async def test_import_updates_existing_sku(client: AsyncClient):
    token = await login(client, ADMIN)
    category_id = await create_category(client, token)
    marker = unique("UPD")
    content = (
        HEADER
        + f"{marker};Початкова назва;Категорія;шт;0,1;0,1;0,1;0,1;\n"
    ).encode()

    first = await client.post(
        f"{API}/products/import",
        headers=auth(token),
        files={"file": ("first.csv", content, "text/csv")},
    )
    assert first.json()["created"] == 1

    updated_content = (
        HEADER + f"{marker};Оновлена назва;Категорія;шт;0,2;0,2;0,2;2,5;\n"
    ).encode()
    second = await client.post(
        f"{API}/products/import",
        headers=auth(token),
        files={"file": ("second.csv", updated_content, "text/csv")},
    )
    assert second.json()["created"] == 0
    assert second.json()["updated"] == 1

    products = await client.get(f"{API}/products", headers=auth(token), params={"search": marker})
    item = products.json()["items"][0]
    assert item["name"] == "Оновлена назва"
    assert float(item["weight"]) == 2.5
    assert item["category_id"] == category_id or item["category_name"] == "Категорія"
