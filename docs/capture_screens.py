"""Знімки екранів для docs/UI.md.

Потрібні запущені бекенд і фронтенд та стартові акаунти. Імпорт створює один
демо-рядок `UI-IMP-1` — після зйомки його можна видалити в UI.

    PROSTOCK_WEB_URL=http://127.0.0.1:5173 python3 docs/capture_screens.py
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("PROSTOCK_WEB_URL", "http://127.0.0.1:5173")
EMAIL = os.environ.get("PROSTOCK_ADMIN_EMAIL", "admin@prostock.com")
PASSWORD = os.environ.get("PROSTOCK_ADMIN_PASSWORD", "Admin12345")
OUT = Path(__file__).parent / "screenshots"
CSV = Path(os.environ.get("TMPDIR", "/tmp")) / "prostock_ui_demo_import.csv"

OUT.mkdir(parents=True, exist_ok=True)
CSV.write_text(
    "sku_code;name;category;unit_of_measure;width;length;height;weight;min_stock_level\n"
    "UI-IMP-1;Демо імпорт;UI Демо;шт;0,1;0,2;0,3;1,5;5\n"
    "UI-IMP-BAD;Рядок з помилкою;UI Демо;pcs;oops;1;1;1;\n",
    encoding="utf-8",
)


def login(page, email: str, password: str) -> None:
    page.goto(f"{BASE}/login")
    page.get_by_label("Пошта", exact=True).fill(email)
    page.get_by_label("Пароль", exact=True).fill(password)
    page.get_by_role("button", name="Увійти").click()
    page.wait_for_url(re.compile(r"/($|products)"), timeout=15000)


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()

        desktop = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        page = desktop.new_page()

        page.goto(f"{BASE}/login")
        page.wait_for_timeout(400)
        page.screenshot(path=OUT / "login.png")

        login(page, EMAIL, PASSWORD)
        page.goto(f"{BASE}/products")
        page.wait_for_timeout(900)
        page.screenshot(path=OUT / "products.png")

        page.get_by_role("button", name="Новий товар").click()
        page.wait_for_timeout(300)
        dialog = page.get_by_role("dialog")
        dialog.get_by_label("Артикул (SKU) *").fill("DEMO-001")
        dialog.get_by_label("Назва товару *").fill("Демонстраційний товар")
        dialog.get_by_label("Ширина, м *").fill("0,25")
        page.screenshot(path=OUT / "product-form.png")
        dialog.get_by_role("button", name="Скасувати").click()

        page.get_by_role("button", name="Імпорт").click()
        page.wait_for_timeout(300)
        dialog = page.get_by_role("dialog")
        dialog.locator('input[type="file"]').set_input_files(str(CSV))
        dialog.get_by_role("button", name="Імпортувати").click()
        dialog.get_by_text("Результат імпорту").wait_for(timeout=20000)
        page.wait_for_timeout(300)
        page.screenshot(path=OUT / "import-report.png")
        dialog.get_by_role("button", name="Готово").click()
        desktop.close()

        mobile = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
        mobile_page = mobile.new_page()
        login(mobile_page, EMAIL, PASSWORD)
        mobile_page.goto(f"{BASE}/products")
        mobile_page.wait_for_timeout(900)
        mobile_page.screenshot(path=OUT / "products-mobile.png")
        mobile.close()

        readonly = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        readonly_page = readonly.new_page()
        login(readonly_page, "worker@prostock.com", "Worker12345")
        readonly_page.goto(f"{BASE}/products")
        readonly_page.wait_for_timeout(900)
        readonly_page.screenshot(path=OUT / "products-readonly.png")
        readonly.close()

        browser.close()

    print("Готово:", ", ".join(sorted(path.name for path in OUT.glob("*.png"))))


if __name__ == "__main__":
    main()
