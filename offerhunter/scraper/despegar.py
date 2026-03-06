from playwright.sync_api import sync_playwright
import re
import time


def _parse_price(text):
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


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

        time.sleep(6)

        # scroll para que carguen vuelos
        for _ in range(6):
            page.mouse.wheel(0, 2000)
            time.sleep(1)

        # buscar cualquier bloque que contenga precios
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

                # intentar obtener contenedor del vuelo
                container = candidates.nth(i).locator(
                    "xpath=ancestor::*[self::div or self::article][1]"
                )

                text = container.inner_text()

                title = text.split("\n")[0][:120]

                if price in seen:
                    continue

                seen.add(price)

                presas.append(
                    {
                        "title": title,
                        "price": price,
                        "url": url,
                        "source": "despegar",
                    }
                )

            except:
                continue

        browser.close()

    return presas