from __future__ import annotations

import json
import re
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright


# =========================
# HELPERS
# =========================

def _to_int_price(text: str) -> int | None:
    """
    Convierte:
      "$ 41.999,00"
      "$41.999"
      "41999"
    a int.
    """
    if not text:
        return None

    m = re.search(r"([\d\.\,]+)", text)
    if not m:
        return None

    raw = m.group(1).replace(".", "").replace(",", "")
    try:
        return int(raw)
    except Exception:
        return None


# =========================
# GENERIC SCRAPER
# =========================

def hunt_offers_generic(url_input: str, keyword: str, max_price: int):
    """
    Scraper GENERIC para tiendas chicas / HTML simple.
    No pensado para monstruos React complejos.
    Devuelve:
      List[{"titulo": str, "precio": int, "link": str}]
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
                                if precio <= int(max_price):
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
            # 2️⃣ Intentar por "product cards"
            # Compatible con Magento / WooCommerce / Shopify
            # ==========================================

            cards = page.locator(
                "li.product-item, "
                "div.product-card, "
                "div.product-item-info"
            ).all()

            for card in cards[:40]:
                try:
                    title_el = card.locator(
                        "a.product-item-link, "
                        "a.product-name, "
                        "a[href]"
                    ).first

                    price_el = card.locator(
                        ".price, "
                        ".product-price, "
                        "[class*='price']"
                    ).first

                    if not price_el:
                        continue

                    if not price_el.is_visible():
                        continue

                    titulo = (title_el.inner_text() or "").strip()
                    try:
                        precio_txt = (price_el.inner_text(timeout=1500) or "").strip()
                    except:
                        continue

                    if not titulo or not precio_txt:
                        continue

                    if keyword_l and keyword_l not in titulo.lower():
                        continue

                    precio = _to_int_price(precio_txt)
                    if not precio:
                        continue

                    if precio > int(max_price):
                        continue

                    link = title_el.get_attribute("href")
                    if link:
                        link = urljoin(url_input, link)

                    presas.append({
                        "titulo": titulo[:120],
                        "precio": int(precio),
                        "link": link or url_input
                    })

                except Exception:
                    continue

            if presas:
                return presas[:40]

            # ==========================================
            # 3️⃣ Último fallback (buscar links con precio en texto)
            # ==========================================

            links = page.locator("a").all()

            for link_el in links[:200]:
                try:
                    texto = link_el.inner_text()
                    if not texto:
                        continue

                    if keyword_l and keyword_l not in texto.lower():
                        continue

                    precio = _to_int_price(texto)
                    if not precio:
                        continue

                    if precio > int(max_price):
                        continue

                    href = link_el.get_attribute("href")
                    if href:
                        href = urljoin(url_input, href)

                    titulo = texto.split("\n")[0].strip()

                    presas.append({
                        "titulo": titulo[:120],
                        "precio": int(precio),
                        "link": href or url_input
                    })

                except Exception:
                    continue

            return presas[:40]

        finally:
            try:
                context.close()
            except:
                pass

            try:
                browser.close()
            except:
                pass