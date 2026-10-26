"""Авто-вихід, коли refresh-сесія стає недоступною.

Потрібен бекенд із короткоживучим access-токеном, щоб таймер спрацював швидко:

    cd backend
    DB_NAME=prostock ACCESS_TOKEN_EXPIRE_MINUTES=1 \
      uvicorn app.main:app --port 8010

    cd frontend
    VITE_API_TARGET=http://127.0.0.1:8010 npm run dev -- --port 5180

    PROSTOCK_WEB_URL=http://127.0.0.1:5180 python3 frontend/e2e/check_autologout.py
"""
from __future__ import annotations

import os
import re
import sys

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("PROSTOCK_WEB_URL", "http://127.0.0.1:5173")
EMAIL = os.environ.get("PROSTOCK_ADMIN_EMAIL", "admin@prostock.com")
PASSWORD = os.environ.get("PROSTOCK_ADMIN_PASSWORD", "Admin12345")


def main() -> int:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        page.goto(f"{BASE}/login")
        page.get_by_label("Пошта", exact=True).fill(EMAIL)
        page.get_by_label("Пароль", exact=True).fill(PASSWORD)
        page.get_by_role("button", name="Увійти").click()
        page.wait_for_url(re.compile(r"/($|products)"), timeout=15000)
        print("PASS  вхід виконано (access-токен короткоживучий)")

        # Імітуємо втрату refresh-сесії: cookie відкликано/прострочено
        context.clear_cookies()
        print("INFO  refresh-cookie видалено, чекаємо таймер авто-refresh…")

        page.wait_for_url(re.compile(r"/login"), timeout=30000)
        print("PASS  автоматичний вихід на сторінку входу")

        expect(page.get_by_text("Сесія завершилася. Увійдіть знову", exact=False)).to_be_visible(timeout=5000)
        print("PASS  показано повідомлення «Сесія завершилася»")

        expect(page.get_by_label("Пошта", exact=True)).to_be_visible()
        print("PASS  форма входу доступна")

        context.close()
        browser.close()

    print("\nРЕЗУЛЬТАТ: авто-вихід за таймером підтверджено")
    return 0


if __name__ == "__main__":
    sys.exit(main())
