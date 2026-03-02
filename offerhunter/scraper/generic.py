from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright


# =========================
# HELPERS
# =========================

def _to_int_price(text: str) -> int | None:
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


def _looks_like_facet_link(url: str) -> bool:
    u = (url or "").lower()
    bad_tokens = [
        "/marca-",
        "/disciplina-",
        "/price-",
        "/genero-",
        "/género-",
        "/talle-",
        "/color-",
        "/size-",
        "/filter-",
        "/filtro-",
        "limit=",
        "p=",
    ]
    return any(t in u for t in bad_tokens)


def _looks_like_item_count_text(text: str) -> bool:
    t = (text or "").lower().strip()
    return "artículo" in t or "articulos" in t or "artículos" in t


def _dedup_by_link(items: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for it in items:
        link = (it.get("link") or "").strip()
        if not link or link in seen:
            continue
        seen.add(link)
        out.append(it)
    return out


def _apply_keyword_soft(items: list[dict], keyword_l: str) -> list[dict]:
    """
    Keyword soft:
    - Si keyword filtra y queda algo => devolvemos filtradas.
    - Si keyword filtra y queda 0 => devolvemos originales (mejor que 0, evita "caza muerta").
    """
    if not keyword_l:
        return items

    filtered = [x for x in items if keyword_l in (x.get("titulo", "") or "").lower()]
    return filtered if filtered else items


# =========================
# GENERIC SCRAPER
# =========================

def hunt_offers_generic(url_input: str, keyword: str, max_price: int, depth: int = 0):
    """
    Scraper GENERIC para tiendas chicas / HTML simple.
    depth = 0 → página original
    depth = 1 → subcategoría automática (máximo 1 salto)
    Devuelve: List[{"titulo": str, "precio": int, "link": str}]
    """
    keyword_l = (keyword or "").strip().lower()
    presas: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
        )

        page = context.new_page()
        page.set_default_timeout(2500)
        page.set_default_navigation_timeout(12000)

        try:
            page.goto(url_input, wait_until="domcontentloaded", timeout=12000)

            # Espera extra para listas tipo Magento
            try:
                page.wait_for_selector("li.product-item", timeout=6000)
            except Exception:
                pass

            # networkidle ayuda cuando hay JS cargando precios
            try:
                page.wait_for_load_state("networkidle", timeout=6000)
            except Exception:
                pass

            # ==========================================
            # 1) JSON-LD (schema.org)
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
                presas = _dedup_by_link(presas)
                presas = _apply_keyword_soft(presas, keyword_l)
                return presas[:40]

            # ==========================================
            # 2) Product cards (Magento/Woo/Shopify)
            # ==========================================
            cards = page.locator(
                "li.product-item, "
                "div.product-card, "
                "div.product-item-info"
            ).all()

            for card in cards[:80]:
                try:
                    title_el = card.locator(
                        "a.product-item-link, "
                        "a.product-name"
                    ).first
                    if not title_el:
                        continue

                    link = (title_el.get_attribute("href") or "").strip()
                    if link:
                        link = urljoin(url_input, link)

                    if not link or _looks_like_facet_link(link):
                        continue

                    try:
                        titulo = (title_el.text_content(timeout=1000) or "").strip()
                    except Exception:
                        continue

                    if not titulo:
                        continue

                    precio = None

                    # A) data-price-amount (Magento, puede haber varios)
                    amounts = card.locator("[data-price-amount]").all()
                    vals = []
                    for a in amounts[:6]:
                        raw = (a.get_attribute("data-price-amount") or "").strip()
                        if not raw:
                            continue
                        try:
                            v = float(raw)
                            if v > 0:
                                vals.append(v)
                        except Exception:
                            continue
                    if vals:
                        precio = int(min(vals))

                    # B) texto visible
                    if not precio:
                        price_el = card.locator(
                            "span.price:visible, "
                            ".price:visible"
                        ).first
                        if not price_el:
                            continue

                        try:
                            precio_txt = (price_el.text_content(timeout=1200) or "").strip()
                        except Exception:
                            continue

                        if not precio_txt:
                            continue
                        if _looks_like_item_count_text(precio_txt):
                            continue
                        if "$" not in precio_txt and "ars" not in precio_txt.lower():
                            continue

                        precio = _to_int_price(precio_txt)

                    if not precio:
                        continue
                    if int(precio) > int(max_price):
                        continue

                    presas.append({
                        "titulo": titulo[:120],
                        "precio": int(precio),
                        "link": link
                    })

                except Exception:
                    continue

            if presas:
                presas = _dedup_by_link(presas)
                presas = _apply_keyword_soft(presas, keyword_l)
                return presas[:40]

            # ==========================================
            # 2.5) Subcategory auto-follow (1 salto máx)
            # ==========================================
            if depth == 0:
                base = urlparse(url_input)
                base_path = base.path.rstrip("/")

                # intentamos links dentro del contenido principal
                candidates = page.locator("main a[href], #maincontent a[href]").all()

                for a in candidates[:250]:
                    try:
                        href = (a.get_attribute("href") or "").strip()
                        if not href:
                            continue

                        href_full = urljoin(url_input, href)
                        u = urlparse(href_full)

                        # mismo dominio
                        if u.netloc != base.netloc:
                            continue

                        # subruta dentro de la misma categoría
                        if not u.path.startswith(base_path):
                            continue

                        # evitamos loops/paginación
                        if "p=" in (u.query or ""):
                            continue

                        # acá NO filtramos facetas: justamente seguimos 1 sublink
                        # (Tripstore case: la categoría es hub)
                        return hunt_offers_generic(href_full, keyword, max_price, depth=1)

                    except Exception:
                        continue

            # ==========================================
            # 3) Último fallback: links con precio en texto
            # ==========================================
            links = page.locator("a").all()

            for link_el in links[:200]:
                try:
                    texto = (link_el.text_content(timeout=600) or "").strip()
                    if not texto:
                        continue
                    if _looks_like_item_count_text(texto):
                        continue
                    if "$" not in texto and "ars" not in texto.lower():
                        continue

                    precio = _to_int_price(texto)
                    if not precio:
                        continue
                    if precio > int(max_price):
                        continue

                    href = (link_el.get_attribute("href") or "").strip()
                    if href:
                        href = urljoin(url_input, href)

                    if not href or _looks_like_facet_link(href):
                        continue

                    presas.append({
                        "titulo": texto[:120],
                        "precio": int(precio),
                        "link": href
                    })

                except Exception:
                    continue

            presas = _dedup_by_link(presas)
            presas = _apply_keyword_soft(presas, keyword_l)
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