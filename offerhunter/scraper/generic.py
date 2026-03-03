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


def _looks_like_promo_text(text: str) -> bool:
    t = (text or "").lower()
    promo_tokens = [
        "%", "cuota", "cuotas", "sin interés", "sin interes",
        "descuento", "promo", "promoción", "promocion",
        "mi carrefour", "crédito", "credito", "cuenta digital",
        "precio por unidad", "precioporunidad",
        "llevá", "lleva", "pagando con", "tope", "super",
    ]
    return any(tok in t for tok in promo_tokens)


def _is_probably_price_text(text: str) -> bool:
    if not text:
        return False

    t = text.strip()
    tl = t.lower()

    if _looks_like_promo_text(t):
        return False

    if ("$" not in t) and ("ars" not in tl):
        return False

    p = _to_int_price(t)
    if not p:
        return False

    if p < 100:
        return False

    return True


def _clean_title(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"\s+", " ", t)
    t = t.replace("\u00a0", " ").strip()
    return t


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
    if not keyword_l:
        return items
    filtered = [x for x in items if keyword_l in (x.get("titulo", "") or "").lower()]
    return filtered if filtered else items


def _kick_lazy_load(page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=12000)
    except Exception:
        pass

    for _ in range(7):
        try:
            page.mouse.wheel(0, 1800)
        except Exception:
            pass
        try:
            page.wait_for_timeout(650)
        except Exception:
            pass

    try:
        page.wait_for_selector(
            "a[href*='/p/'], "
            "div[class*='vtex-product-summary'], "
            "div[class*='product-summary'], "
            "div[class*='vtex-search-result'], "
            "article",
            timeout=12000
        )
    except Exception:
        pass


def _safe_get_attr(el, name: str, timeout_ms: int = 600) -> str:
    try:
        v = el.get_attribute(name, timeout=timeout_ms)
        return (v or "").strip()
    except Exception:
        return ""


def _safe_text(el, timeout_ms: int = 800) -> str:
    try:
        return _clean_title(el.text_content(timeout=timeout_ms) or "")
    except Exception:
        return ""


# =========================
# GENERIC SCRAPER
# =========================

def hunt_offers_generic(url_input: str, keyword: str, max_price: int, depth: int = 0):
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
        page.set_default_timeout(3500)
        page.set_default_navigation_timeout(25000)

        try:
            page.goto(url_input, wait_until="domcontentloaded", timeout=25000)
            _kick_lazy_load(page)

            # ==========================================
            # 1) JSON-LD
            # ==========================================
            scripts = page.locator("script[type='application/ld+json']").all()
            for s in scripts[:60]:
                try:
                    content = s.inner_text(timeout=1200)
                    data = json.loads(content)
                    if isinstance(data, dict):
                        data = [data]

                    for item in data:
                        if not isinstance(item, dict):
                            continue

                        t = item.get("@type")
                        if t not in ["Product", "Offer", "ItemList"]:
                            continue

                        if t in ["Product", "Offer"]:
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
                                        "titulo": _clean_title(str(titulo))[:120],
                                        "precio": precio_i,
                                        "link": url_input
                                    })

                        if t == "ItemList":
                            elems = item.get("itemListElement") or []
                            if isinstance(elems, list):
                                for el in elems[:80]:
                                    try:
                                        if not isinstance(el, dict):
                                            continue
                                        it = el.get("item") or el
                                        if not isinstance(it, dict):
                                            continue

                                        titulo = it.get("name") or it.get("title")
                                        urlp = it.get("url")
                                        offers = it.get("offers") or {}
                                        precio = None
                                        if isinstance(offers, dict):
                                            precio = offers.get("price")

                                        if not titulo or not urlp or not precio:
                                            continue

                                        try:
                                            precio_i = int(float(precio))
                                        except Exception:
                                            continue

                                        if precio_i <= int(max_price):
                                            presas.append({
                                                "titulo": _clean_title(str(titulo))[:120],
                                                "precio": precio_i,
                                                "link": urljoin(url_input, str(urlp))
                                            })
                                    except Exception:
                                        continue

                except Exception:
                    continue

            if presas:
                presas = _dedup_by_link(presas)
                presas = _apply_keyword_soft(presas, keyword_l)
                return presas[:40]

            # ==========================================
            # 2) CARDS: optimizado (evita hangs por DOM cambiante)
            # ==========================================
            cards = page.locator(
                "li.product-item, "
                "div.product-card, "
                "div.product-item-info, "
                "article, "
                "div[class*='product-summary'], "
                "div[class*='vtex-product-summary'], "
                "div[class*='vtex-search-result']"
            )

            # En vez de .all() (caro y a veces cuelga), limitamos por count y nth()
            try:
                total = min(cards.count(), 120)
            except Exception:
                total = 0

            for idx in range(total):
                try:
                    card = cards.nth(idx)

                    title_el = card.locator(
                        "a.product-item-link, "
                        "a.product-name, "
                        "a[href*='/p/'], "
                        "a[href]"
                    ).first

                    href = _safe_get_attr(title_el, "href", timeout_ms=600)
                    if not href:
                        continue
                    href = urljoin(url_input, href)
                    if _looks_like_facet_link(href):
                        continue

                    titulo = _safe_text(title_el, timeout_ms=900)
                    if not titulo:
                        # fallback attributes
                        titulo = _clean_title(_safe_get_attr(title_el, "aria-label", 400))
                    if not titulo:
                        titulo = _clean_title(_safe_get_attr(title_el, "title", 400))

                    if not titulo:
                        continue
                    if _looks_like_promo_text(titulo) or _looks_like_item_count_text(titulo):
                        continue

                    # -------- price --------
                    precio = None

                    amounts = card.locator("[data-price-amount]")
                    try:
                        amt_n = min(amounts.count(), 10)
                    except Exception:
                        amt_n = 0

                    vals = []
                    for j in range(amt_n):
                        a = amounts.nth(j)
                        raw = _safe_get_attr(a, "data-price-amount", timeout_ms=300)
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

                    if not precio:
                        price_el = card.locator(
                            "span[class*='currencyContainer']:visible, "
                            "span[class*='sellingPrice']:visible, "
                            "[data-testid*='price']:visible, "
                            "[class*='price']:visible, "
                            "span.price:visible, "
                            "div.price:visible"
                        ).first

                        precio_txt = _safe_text(price_el, timeout_ms=1200)
                        if precio_txt and _is_probably_price_text(precio_txt):
                            precio = _to_int_price(precio_txt)

                    if not precio:
                        continue
                    if int(precio) > int(max_price):
                        continue

                    presas.append({"titulo": titulo[:120], "precio": int(precio), "link": href})

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

                candidates = page.locator("main a[href], #maincontent a[href], a[href]")
                try:
                    ctotal = min(candidates.count(), 350)
                except Exception:
                    ctotal = 0

                for i in range(ctotal):
                    try:
                        a = candidates.nth(i)
                        href = _safe_get_attr(a, "href", timeout_ms=300)
                        if not href:
                            continue

                        href_full = urljoin(url_input, href)
                        u = urlparse(href_full)

                        if u.netloc != base.netloc:
                            continue
                        if not u.path.startswith(base_path):
                            continue
                        if "p=" in (u.query or ""):
                            continue
                        if _looks_like_facet_link(href_full):
                            continue

                        return hunt_offers_generic(href_full, keyword, max_price, depth=1)

                    except Exception:
                        continue

            # ==========================================
            # 3) Fallback: links con "precio real"
            # ==========================================
            links = page.locator("a")
            try:
                ltotal = min(links.count(), 300)
            except Exception:
                ltotal = 0

            for i in range(ltotal):
                try:
                    link_el = links.nth(i)
                    texto = _safe_text(link_el, timeout_ms=700)
                    if not texto:
                        continue
                    if _looks_like_item_count_text(texto) or _looks_like_promo_text(texto):
                        continue
                    if not _is_probably_price_text(texto):
                        continue

                    precio = _to_int_price(texto)
                    if not precio:
                        continue
                    if precio > int(max_price):
                        continue

                    href = _safe_get_attr(link_el, "href", timeout_ms=300)
                    if not href:
                        continue
                    href = urljoin(url_input, href)
                    if _looks_like_facet_link(href):
                        continue

                    presas.append({"titulo": texto[:120], "precio": int(precio), "link": href})

                except Exception:
                    continue

            presas = _dedup_by_link(presas)
            presas = _apply_keyword_soft(presas, keyword_l)
            return presas[:40]

        except KeyboardInterrupt:
            # Para tests manuales: salir limpio
            return []
        finally:
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass