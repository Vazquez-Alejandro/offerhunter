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
    presas: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # Un user agent común ayuda en algunas tiendas
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        # Timeouts duros para que nunca se cuelgue el engine
        page.set_default_timeout(2500)
        page.set_default_navigation_timeout(12000)

        try:
            page.goto(url_input, wait_until="domcontentloaded", timeout=12000)
            page.wait_for_timeout(1200)

            # ==========================================
            # 1️⃣ Intentar JSON-LD (schema.org Product)
            # ==========================================
            scripts = page.locator("script[type='application/ld+json']").all()

            for s in scripts[:50]:
                try:
                    content = s.inner_text(timeout=1000)
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
                                try:
                                    precio_i = int(float(precio))
                                except Exception:
                                    continue

                                if precio_i <= int(max_price):
                                    presas.append({
                                        "titulo": str(titulo)[:120],
                                        "precio": precio_i,
                                        "link": url_input
                                    })

                except Exception:
                    continue

            if presas:
                return presas[:40]

            # ==========================================
            # 2️⃣ Fallback Magento (Tripstore suele ser Magento)
            #    - li.product-item
            #    - title: a.product-item-link
            #    - price: [data-price-amount] o span.price
            # ==========================================
            magento_cards = page.locator("li.product-item").all()

            for card in magento_cards[:60]:
                try:
                    title_el = card.locator("a.product-item-link").first
                    if not title_el:
                        continue

                    try:
                        titulo = (title_el.inner_text(timeout=1000) or "").strip()
                    except Exception:
                        continue

                    if not titulo:
                        continue

                    if keyword_l and keyword_l not in titulo.lower():
                        continue

                    precio: int | None = None

                    # 2.1) data-price-amount (muchas tiendas Magento)
                    price_attr_el = card.locator("[data-price-amount]").first
                    if price_attr_el:
                        raw = (price_attr_el.get_attribute("data-price-amount") or "").strip()
                        if raw:
                            try:
                                precio = int(float(raw))
                            except Exception:
                                precio = None

                    # 2.2) fallback: texto de span.price
                    if not precio:
                        price_el = card.locator("span.price").first
                        if not price_el:
                            continue
                        try:
                            precio_txt = (price_el.inner_text(timeout=1000) or "").strip()
                        except Exception:
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
            # 3️⃣ Intentar por "product cards" genéricas
            #    (WooCommerce / Shopify simples)
            # ==========================================
            cards = page.locator(
                "div.product-card, "
                "div.product-item-info, "
                "div.product, "
                "li.product"
            ).all()

            for card in cards[:50]:
                try:
                    title_el = card.locator(
                        "a.product-item-link, "
                        "a.woocommerce-LoopProduct-link, "
                        "a.product-name, "
                        "a[href]"
                    ).first

                    if not title_el:
                        continue

                    try:
                        titulo = (title_el.inner_text(timeout=1000) or "").strip()
                    except Exception:
                        continue

                    if not titulo:
                        continue

                    if keyword_l and keyword_l not in titulo.lower():
                        continue

                    price_el = card.locator(
                        "span.price, "
                        ".price, "
                        ".product-price, "
                        "[class*='price']"
                    ).first

                    if not price_el:
                        continue

                    # Evitar waits eternos: si no es visible, saltar
                    try:
                        if not price_el.is_visible():
                            continue
                    except Exception:
                        continue

                    try:
                        precio_txt = (price_el.inner_text(timeout=1200) or "").strip()
                    except Exception:
                        continue

                    if not precio_txt:
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
            # 4️⃣ Último fallback (links con precio en texto)
            # ==========================================
            links = page.locator("a").all()

            for link_el in links[:200]:
                try:
                    try:
                        texto = link_el.inner_text(timeout=600)
                    except Exception:
                        continue

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
            except Exception:
                pass

            try:
                browser.close()
            except Exception:
                pass