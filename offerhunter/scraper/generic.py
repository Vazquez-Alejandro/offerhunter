from __future__ import annotations

import json
import re
from urllib.parse import urlparse, urljoin

from playwright.sync_api import sync_playwright


def _to_int_price(text: str) -> int | None:
    if not text:
        return None
    m = re.search(r"\$?\s*([\d\.\,]+)", text)
    if not m:
        return None
    raw = m.group(1).replace(".", "").replace(",", "")
    try:
        return int(raw)
    except Exception:
        return None


def hunt_offers_generic(url_input: str, keyword: str, max_price: int):
    """
    Scraper GENERIC para tiendas chicas / HTML simple.
    No apto para monstruos React complejos.
    """

    keyword_l = (keyword or "").strip().lower()
    presas = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            page.goto(url_input, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(2000)

            # ==========================================
            # 1️⃣ Intentar JSON-LD (schema.org Product)
            # ==========================================
            scripts = page.locator("script[type='application/ld+json']").all()

            for s in scripts:
                try:
                    content = s.inner_text()
                    data = json.loads(content)

                    if isinstance(data, dict):
                        data = [data]

                    for item in data:
                        if not isinstance(item, dict):
                            continue

                        if item.get("@type") in ["Product", "Offer"]:
                            titulo = item.get("name")
                            offer = item.get("offers", {})
                            precio = None

                            if isinstance(offer, dict):
                                precio = offer.get("price")

                            if titulo and precio:
                                precio = int(float(precio))
                                if precio <= max_price:
                                    presas.append({
                                        "titulo": titulo[:120],
                                        "precio": precio,
                                        "link": url_input
                                    })

                except Exception:
                    continue

            if presas:
                return presas[:40]

            # ==========================================
            # 2️⃣ Fallback heurístico simple
            # ==========================================
            items = page.locator("a").all()

            for item in items[:200]:
                try:
                    texto = item.inner_text()
                    if not texto:
                        continue

                    if keyword_l and keyword_l not in texto.lower():
                        continue

                    precio = _to_int_price(texto)
                    if not precio:
                        continue

                    if precio > max_price:
                        continue

                    link = item.get_attribute("href")
                    if link:
                        link = urljoin(url_input, link)

                    titulo = texto.split("\n")[0].strip()

                    presas.append({
                        "titulo": titulo[:120],
                        "precio": precio,
                        "link": link or url_input
                    })

                except Exception:
                    continue

            return presas[:40]

        finally:
            try:
                context.close()
            finally:
                browser.close()