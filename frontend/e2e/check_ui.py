"""E2E-перевірка веб-панелі ProStock через Playwright."""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

BASE = os.environ.get("PROSTOCK_WEB_URL", "http://127.0.0.1:5173")
SKU = f"E2E-{int(time.time())}"
CSV = Path(os.environ.get("TMPDIR", "/tmp")) / "prostock_e2e_import.csv"

passed = 0
failed = 0


def check(name: str, condition: bool, extra: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name} {extra}")


def login(page: Page, email: str, password: str) -> None:
    page.goto(f"{BASE}/login")
    page.get_by_label("Пошта", exact=True).fill(email)
    page.get_by_label("Пароль", exact=True).fill(password)
    page.get_by_role("button", name="Увійти").click()
    page.wait_for_url(re.compile(r"/($|products)"), timeout=15000)


def main() -> int:
    CSV.write_text(
        "sku_code;name;category;unit_of_measure;width;length;height;weight;min_stock_level\n"
        "E2E-IMP-1;E2E Імпорт 1;E2E Категорія;шт;0,1;0,2;0,3;1,5;2\n"
        "E2E-IMP-BAD;Зламаний рядок;E2E Категорія;pcs;oops;1;1;1;\n",
        encoding="utf-8",
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(accept_downloads=True, viewport={"width": 1440, "height": 950})
        page = context.new_page()
        console_errors: list[str] = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        print("\n[1] Валідація форми входу")
        page.goto(f"{BASE}/login")
        page.get_by_role("button", name="Увійти").click()
        check("порожні поля → помилка email", page.get_by_text("Вкажіть адресу електронної пошти").is_visible())
        check("порожні поля → помилка пароля", page.get_by_text("Введіть пароль").is_visible())

        page.get_by_label("Пошта", exact=True).fill("не-пошта")
        page.get_by_label("Пароль", exact=True).fill("123")
        page.get_by_role("button", name="Увійти").click()
        check("некоректний email → підказка", page.get_by_text("Некоректний формат пошти").is_visible())
        check("короткий пароль → підказка", page.get_by_text("Пароль має містити щонайменше 8 символів").is_visible())

        page.get_by_label("Пошта", exact=True).fill("admin@prostock.com")
        page.get_by_label("Пароль", exact=True).fill("WrongPass123")
        page.get_by_role("button", name="Увійти").click()
        expect(page.get_by_role("alert")).to_contain_text("Невірний email або пароль", timeout=10000)
        check("невірні дані → повідомлення сервера", True)

        print("\n[2] Вхід і захищені маршрути")
        page.get_by_label("Пароль", exact=True).fill("Admin12345")
        page.get_by_role("button", name="Увійти").click()
        page.wait_for_url(re.compile(r"/($|products)"), timeout=15000)
        check("успішний вхід", "/login" not in page.url, page.url)
        expect(page.get_by_role("link", name="Товари")).to_be_visible(timeout=10000)
        check("вкладка Товари видима", True)
        check("ім'я користувача в навбарі", page.get_by_text("Адмін Системи").is_visible())
        check("вкладка Співробітники для адміна", page.get_by_role("link", name="Співробітники").is_visible())

        token_in_storage = page.evaluate(
            "() => ({ local: Object.keys(localStorage), session: Object.keys(sessionStorage) })"
        )
        check(
            "JWT не зберігається у localStorage",
            not any("token" in key.lower() for key in token_in_storage["local"]),
            str(token_in_storage),
        )
        cookies = context.cookies()
        refresh_cookies = [c for c in cookies if c["name"] == "prostock_refresh"]
        check("refresh-cookie є", len(refresh_cookies) == 1)
        if refresh_cookies:
            check("refresh-cookie httpOnly", refresh_cookies[0]["httpOnly"] is True)
            check("refresh-cookie не в localStorage", "prostock_refresh" not in token_in_storage["local"])

        print("\n[3] Таблиця товарів")
        page.get_by_role("link", name="Товари").click()
        page.wait_for_url("**/products")
        expect(page.get_by_text(re.compile("у каталозі"))).to_be_visible(timeout=10000)
        rows_before = page.locator("table tbody tr").count()
        check("таблиця завантажилась", rows_before > 0, str(rows_before))
        expect(page.get_by_role("button", name=re.compile("артикул", re.IGNORECASE))).to_be_visible()
        check("є сортування за артикулом", True)

        page.get_by_label("Пошук товарів").fill("CHEM-001")
        expect(page.locator("table tbody tr")).to_have_count(1, timeout=10000)
        check("пошук працює", page.get_by_text("CHEM-001").is_visible())
        page.get_by_label("Пошук товарів").fill("")
        expect(page.locator("table tbody tr")).not_to_have_count(1, timeout=10000)

        print("\n[4] Створення товару")
        page.get_by_role("button", name="Новий товар").click()
        expect(page.get_by_role("dialog")).to_be_visible()
        check("модальне вікно відкрилось", True)

        page.get_by_role("button", name="Зберегти").click()
        dialog = page.get_by_role("dialog")
        check("валідація SKU", dialog.get_by_role("alert").filter(has_text="Вкажіть артикул").first.is_visible())
        check("валідація категорії", dialog.get_by_role("alert").filter(has_text="Оберіть категорію").first.is_visible())
        check("валідація ширини", dialog.get_by_role("alert").filter(has_text="Вкажіть ширину").first.is_visible())

        dialog.get_by_label("Артикул (SKU) *").fill(SKU)
        dialog.get_by_label("Назва товару *").fill("E2E тестовий товар")
        dialog.get_by_label("Категорія *").select_option(label="Побутова хімія")
        dialog.get_by_label("Ширина, м *").fill("0,25")
        dialog.get_by_label("Довжина, м *").fill("0,35")
        dialog.get_by_label("Висота, м *").fill("0,15")
        dialog.get_by_label("Вага, кг *").fill("1,75")
        dialog.get_by_label("Мінімальний залишок").fill("7")
        dialog.get_by_role("button", name="Зберегти").click()

        expect(page.locator('[role="status"]').filter(has_text="додано до каталогу")).to_be_visible(timeout=10000)
        check("товар створено (банер)", True)
        page.get_by_label("Пошук товарів").fill(SKU)
        expect(page.locator("table tbody tr")).to_have_count(1, timeout=10000)
        check("новий товар у таблиці", page.get_by_text(SKU).is_visible())
        check("категорія у рядку", "Побутова хімія" in page.locator("table tbody tr").first.inner_text())

        print("\n[5] Редагування товару")
        page.get_by_role("button", name=re.compile(f"Редагувати")).first.click()
        dialog = page.get_by_role("dialog")
        dialog.get_by_label("Назва товару *").fill("E2E тестовий товар (оновлено)")
        dialog.get_by_role("button", name="Зберегти").click()
        expect(page.locator('[role="status"]').filter(has_text="оновлено")).to_be_visible(timeout=10000)
        check("редагування збережено", "E2E тестовий товар (оновлено)" in page.locator("table tbody tr").first.inner_text())

        print("\n[6] Імпорт із звітом про помилки")
        page.get_by_role("button", name="Імпорт").click()
        dialog = page.get_by_role("dialog")
        expect(dialog).to_be_visible()
        dialog.locator('input[type="file"]').set_input_files(str(CSV))
        check("файл вибрано", dialog.get_by_text("e2e_import.csv").is_visible())
        dialog.get_by_role("button", name="Імпортувати").click()
        expect(dialog.get_by_text("Результат імпорту")).to_be_visible(timeout=20000)
        check("звіт: блок «Створено»", dialog.get_by_text("Створено", exact=True).is_visible())
        check("звіт: помилки показані", dialog.get_by_text("Рядки з помилками").is_visible())
        error_row = dialog.locator("table tbody tr").first
        error_text = error_row.inner_text()
        check("звіт: номер рядка", error_text.strip().startswith("3"), error_text)
        check("звіт: поле помилки", "width" in error_text, error_text)
        with page.expect_download() as download_info:
            dialog.get_by_role("button", name="Звіт CSV").click()
        download = download_info.value
        check("звіт про помилки завантажується", download.suggested_filename.startswith("import_errors_"))
        dialog.get_by_role("button", name="Готово").click()
        expect(page.locator('[role="status"]').filter(has_text="Імпорт «e2e_import.csv»")).to_be_visible()

        print("\n[7] Експорт")
        with page.expect_download() as csv_info:
            page.get_by_role("button", name="CSV", exact=True).click()
        csv_download = csv_info.value
        csv_path = csv_download.path()
        csv_text = Path(csv_path).read_text(encoding="utf-8-sig")
        check("CSV завантажено", csv_download.suggested_filename.endswith(".csv"))
        check("CSV містить товар", SKU in csv_text)
        check("CSV містить заголовки", "sku_code;name;category" in csv_text)

        with page.expect_download() as xlsx_info:
            page.get_by_role("button", name="Excel", exact=True).click()
        xlsx_download = xlsx_info.value
        xlsx_bytes = Path(xlsx_download.path()).read_bytes()
        check("Excel завантажено", xlsx_download.suggested_filename.endswith(".xlsx"))
        check("Excel валідний zip", xlsx_bytes[:2] == b"PK")

        print("\n[8] Видалення товару")
        page.get_by_label("Пошук товарів").fill(SKU)
        expect(page.locator("table tbody tr")).to_have_count(1, timeout=10000)
        page.get_by_role("button", name=re.compile("Видалити")).first.click()
        dialog = page.get_by_role("dialog")
        expect(dialog).to_contain_text("Дію не можна скасувати")
        dialog.get_by_role("button", name="Видалити").click()
        expect(page.locator('[role="status"]').filter(has_text="видалено")).to_be_visible(timeout=10000)
        check("товар видалено (банер)", True)
        page.get_by_label("Пошук товарів").fill("")
        page.wait_for_timeout(500)

        print("\n[9] Відновлення сесії після перезавантаження")
        page.reload()
        page.wait_for_url("**/products", timeout=15000)
        check("сесія відновлена через refresh-cookie", "/login" not in page.url, page.url)

        print("\n[10] Авто-вихід при втраченій сесії")
        context.clear_cookies()
        page.reload()
        page.wait_for_url("**/login", timeout=15000)
        check("без refresh-cookie → сторінка входу", "/login" in page.url, page.url)

        print("\n[11] RBAC у інтерфейсі (комірник)")
        login(page, "worker@prostock.com", "Worker12345")
        page.goto(f"{BASE}/products")
        expect(page.get_by_text("режим перегляду")).to_be_visible(timeout=10000)
        check("режим перегляду для комірника", True)
        check("немає кнопки «Новий товар»", page.get_by_role("button", name="Новий товар").count() == 0)
        check("немає кнопки «Імпорт»", page.get_by_role("button", name="Імпорт").count() == 0)
        check("немає кнопок редагування", page.get_by_role("button", name=re.compile("Редагувати")).count() == 0)
        check("немає вкладки Співробітники", page.get_by_role("link", name="Співробітники").count() == 0)
        check("експорт доступний", page.get_by_role("button", name="CSV", exact=True).is_visible())

        page.goto(f"{BASE}/employees")
        expect(page.get_by_text("Недостатньо прав")).to_be_visible(timeout=10000)
        check("прямий перехід на /employees заблоковано", True)

        print("\n[12] Вихід")
        page.get_by_role("button", name="Вийти з облікового запису").click()
        page.wait_for_url("**/login", timeout=10000)
        check("вихід → сторінка входу", "/login" in page.url)
        page.reload()
        page.wait_for_url("**/login", timeout=10000)
        check("після виходу сесія не відновлюється", "/login" in page.url)
        check("cookie refresh видалено", len([c for c in context.cookies() if c["name"] == "prostock_refresh"]) == 0)

        real_errors = [e for e in console_errors if "Failed to load resource" not in e and "404" not in e]
        check("немає помилок у консолі", len(real_errors) == 0, str(real_errors[:3]))

        context.close()
        browser.close()

    print(f"\nРЕЗУЛЬТАТ: {passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
