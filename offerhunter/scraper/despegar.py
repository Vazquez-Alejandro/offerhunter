from playwright.sync_api import sync_playwright
import re
import time


def _parse_price(text):
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def _looks_blocked(html_lower: str) -> bool:
    needles = [
        "acceso restringido temporalmente",
        "hemos detectado un comportamiento inusual",
        "comportamiento del navegador",
        "servicio de asistencia al cliente",
        "access denied",
        "forbidden",
        "captcha",
        "recaptcha",
    ]
    return any(x in html_lower for x in needles)


def hunt_despegar_vuelos(url, keyword="", max_price=0):
    presas = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

        page = context.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        print("✈️ Despegar: cargando página...")
        page.goto(url, wait_until="domcontentloaded")
        time.sleep(4)

        try:
            html_lower = page.content().lower()
        except Exception:
            html_lower = ""

        if html_lower and _looks_blocked(html_lower):
            print("🧩 Despegar: acceso restringido / bloqueo detectado.")
            browser.close()
            return [{"source": "despegar", "blocked": True, "url": url}]

        for _ in range(6):
            try:
                page.mouse.wheel(0, 2000)
            except Exception:
                pass
            time.sleep(1)

        try:
            html_lower = page.content().lower()
        except Exception:
            html_lower = ""

        if html_lower and _looks_blocked(html_lower):
            print("🧩 Despegar: acceso restringido / bloqueo detectado después del scroll.")
            browser.close()
            return [{"source": "despegar", "blocked": True, "url": url}]

        candidates = page.locator("text=/\\$\\s*\\d/")
        total = min(candidates.count(), 60)

        seen = set()

        for i in range(total):
            try:
                raw_price = candidates.nth(i).inner_text()
                price = _parse_price(raw_price)

                if not price:
                    continue

                if max_price and price > max_price:
                    continue

                container = candidates.nth(i).locator(
                    "xpath=ancestor::*[self::div or self::article][1]"
                )
                text = container.inner_text()
                title = text.split("\n")[0][:120].strip()

                key = (title, price)
                if key in seen:
                    continue
                seen.add(key)

                presas.append(
                    {
                        "title": title or "Vuelo Despegar",
                        "price": price,
                        "url": url,
                        "source": "despegar",
                    }
                )

            except Exception:
                continue

        browser.close()
        return presas