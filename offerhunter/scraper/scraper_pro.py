from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from scraper.generic import hunt_offers_generic

# -------------------------------------------------
# Config
# -------------------------------------------------
# Default behavior:
# - Try MercadoLibre headless first (fast, no windows)
# - If ML looks blocked/captcha, retry once headful to let the user solve it.
ML_TRY_HEADLESS_FIRST = os.getenv("OH_ML_TRY_HEADLESS_FIRST", "1") == "1"
ML_FORCE_HEADLESS = os.getenv("OH_ML_HEADLESS", "") == "1"          # force ML headless
ML_FORCE_HEADFUL = os.getenv("OH_ML_HEADLESS", "") == "0"           # force ML headful
STATE_PATH = Path("sessions/ml_state.json")

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def _domain(url: str) -> str:
    try:
        host = urlparse(str(url)).netloc.lower().strip()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _is_mercadolibre(url: str) -> bool:
    return "mercadolibre" in _domain(url)


def _to_int_price(text: str) -> int | None:
    """Convierte '$ 1.234.567' / '$1,234,567' a int."""
    if not text:
        return None
    m = re.search(r"\$\s*([\d\.\,]+)", text)
    if not m:
        return None
    raw = m.group(1).replace(".", "").replace(",", "")
    try:
        return int(raw)
    except Exception:
        return None


def _looks_like_block(html_lower: str) -> bool:
    needles = [
        "captcha",
        "recaptcha",
        "verify you are human",
        "no soy un robot",
        "robot",
        "access denied",
        "blocked",
        "forbidden",
    ]
    return any(x in html_lower for x in needles)


# -------------------------------------------------
# MercadoLibre scraper (monstruo)
# -------------------------------------------------
def _scrape_mercadolibre(url_input: str, keyword: str, max_price: int, *, headless: bool) -> list[dict]:
    """
    Devuelve SIEMPRE:
      [{title, price, url, source="mercadolibre"}]
    """
    if url_input and url_input.startswith("http") and not _is_mercadolibre(url_input):
        raise ValueError(f"[ML] URL no es MercadoLibre: {url_input}")

    if url_input and url_input.startswith("http"):
        target_url = url_input
    else:
        slug = (keyword or "").strip().replace(" ", "-")
        target_url = f"https://listado.mercadolibre.com.ar/{slug}"

    keyword_l = (keyword or "").strip().lower()
    max_price_i = int(max_price or 0)

    presas: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)

        ctx_kwargs = dict(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                " AppleWebKit/537.36 (KHTML, like Gecko)"
                " Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="es-AR",
            viewport={"width": 1365, "height": 900},
        )

        # usar storage_state si existe (reduce captchas)
        if STATE_PATH.exists():
            print("✅ ML: usando sesión guardada")
            context = browser.new_context(storage_state=str(STATE_PATH), **ctx_kwargs)
        else:
            print("⚠ ML: no hay sesión guardada (corré: python scripts/ml_connect.py)")
            context = browser.new_context(**ctx_kwargs)

        page = context.new_page()
        page.set_default_timeout(60000)

        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=60000)

            # hidratar
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass

            html_lower = ""
            try:
                html_lower = page.content().lower()
            except Exception:
                pass

            if html_lower and _looks_like_block(html_lower):
                # señal de bloqueo/captcha
                return [{"source": "mercadolibre", "blocked": True, "url": target_url}]

            # selector principal (layout actual)
            try:
                page.wait_for_selector("li.ui-search-layout__item", timeout=15000)
                cards = page.locator("li.ui-search-layout__item")
            except Exception:
                # fallbacks
                try:
                    page.wait_for_selector("div.poly-card, div.ui-search-result__wrapper", timeout=12000)
                    cards = page.locator("div.poly-card, div.ui-search-result__wrapper")
                except Exception:
                    return []

            # refrescar sesión ya con listado cargado
            try:
                STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
                context.storage_state(path=str(STATE_PATH))
                print("💾 ML: sesión actualizada")
            except Exception:
                pass

            # scroll suave
            try:
                page.mouse.wheel(0, 2200)
                page.wait_for_timeout(1200)
            except Exception:
                pass

            n = min(cards.count(), 60)
            for i in range(n):
                try:
                    card = cards.nth(i)

                    a = card.locator("a").first
                    link = a.get_attribute("href") if a else None
                    if link and link.startswith("/"):
                        link = "https://www.mercadolibre.com.ar" + link

                    title = ""
                    for sel in [
                        "h2.ui-search-item__title",
                        "h2.poly-box",
                        "h2",
                        "span.poly-component__title",
                        "a.ui-search-link",
                    ]:
                        loc = card.locator(sel)
                        if loc.count() > 0:
                            t = (loc.first.inner_text() or "").strip()
                            if t:
                                title = t
                                break
                    if not title:
                        title = (card.inner_text() or "").split("\n")[0].strip()
                    if not title:
                        continue

#if keyword_l and keyword_l not in title.lower():
 #                       continue

                    # precio
                    price_txt = ""
                    frac = card.locator("span.andes-money-amount__fraction")
                    if frac.count() > 0:
                        price_txt = (frac.first.inner_text() or "").strip()
                    else:
                        frac2 = card.locator("span.price-tag-fraction")
                        if frac2.count() > 0:
                            price_txt = (frac2.first.inner_text() or "").strip()

                    precio = None
                    if price_txt:
                        raw = price_txt.replace(".", "").replace(",", "")
                        if raw.isdigit():
                            precio = int(raw)
                    if precio is None:
                        precio = _to_int_price(card.inner_text())

                    if precio is None:
                        continue
                    if max_price_i > 0 and int(precio) > max_price_i:
                        continue

                    presas.append(
                        {"title": title[:120], "price": int(precio), "url": link or target_url, "source": "mercadolibre"}
                    )
                except Exception:
                    continue

            return presas

        finally:
            try:
                context.close()
            finally:
                browser.close()


# -------------------------------------------------
# Router central
# -------------------------------------------------
def hunt_offers(url: str, keyword: str, max_price: int):
    """
    Único entrypoint.
    Devuelve SIEMPRE lista de dicts {title, price, url, source}
    """
    host = _domain(url)

    if "mercadolibre" in host:
        # strategy:
        # - headless first to avoid windows
        # - if blocked -> retry headful once
        if ML_FORCE_HEADFUL:
            res = _scrape_mercadolibre(url, keyword, max_price, headless=False)
            # si igual bloquea, devolvemos vacío (la UI debería pedir "Conectar ML")
            if res and isinstance(res[0], dict) and res[0].get("blocked"):
                return []
            return res

        if ML_FORCE_HEADLESS:
            res = _scrape_mercadolibre(url, keyword, max_price, headless=True)
            if res and isinstance(res[0], dict) and res[0].get("blocked"):
                return []
            return res

        if ML_TRY_HEADLESS_FIRST:
            res = _scrape_mercadolibre(url, keyword, max_price, headless=True)
            if res and isinstance(res[0], dict) and res[0].get("blocked"):
                print("⚠ ML: bloqueo en headless, reintento headful para verificación…")
                res2 = _scrape_mercadolibre(url, keyword, max_price, headless=False)
                if res2 and isinstance(res2[0], dict) and res2[0].get("blocked"):
                    return []
                return res2
            return res

        # fallback: headful directo
        res = _scrape_mercadolibre(url, keyword, max_price, headless=False)
        if res and isinstance(res[0], dict) and res[0].get("blocked"):
            return []
        return res

    # long tail
    return hunt_offers_generic(url, keyword, max_price)