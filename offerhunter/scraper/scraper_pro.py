from __future__ import annotations

import os
import random
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from .generic import hunt_offers_generic

# -------------------------------------------------
# Config
# -------------------------------------------------
# ML queda headful por defecto para evitar detección agresiva.
ML_FORCE_HEADLESS = os.getenv("OH_ML_HEADLESS", "") == "1"
ML_FORCE_HEADFUL = os.getenv("OH_ML_HEADLESS", "") == "0"

BASE_DIR = Path(__file__).resolve().parents[1]  # .../offerhunter
PROFILE_PATH = BASE_DIR / "sessions" / "ml_profile"
DEBUG_SHOT_PATH = BASE_DIR / "sessions" / "ml_debug.png"


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


def _has_result_cards(page) -> bool:
    selectors = [
        "div.poly-card",
        "div.ui-search-result__wrapper",
        "li.ui-search-layout__item",
    ]
    for sel in selectors:
        try:
            if page.locator(sel).count() > 0:
                return True
        except Exception:
            pass
    return False


def _looks_like_block(html_lower: str) -> bool:
    needles = [
        "captcha",
        "recaptcha",
        "no soy un robot",
        "access denied",
        "forbidden",
        "hubo un problema al validar",
        "verifica que no seas un robot",
    ]
    return any(x in html_lower for x in needles)


def _human_touch(page) -> None:
    try:
        time.sleep(random.uniform(2.0, 4.5))
        page.mouse.move(random.randint(120, 500), random.randint(120, 500), steps=random.randint(12, 25))
        time.sleep(random.uniform(0.3, 1.1))
        page.mouse.wheel(0, random.randint(400, 1400))
        time.sleep(random.uniform(0.7, 1.6))
    except Exception:
        pass


# -------------------------------------------------
# MercadoLibre scraper usando perfil persistente real
# -------------------------------------------------
def _scrape_mercadolibre(url_input: str, keyword: str, max_price: int, *, headless: bool) -> list[dict]:
    if url_input and url_input.startswith("http") and not _is_mercadolibre(url_input):
        raise ValueError(f"[ML] URL no es MercadoLibre: {url_input}")

    if url_input and url_input.startswith("http"):
        target_url = url_input
    else:
        slug = (keyword or "").strip().replace(" ", "-")
        target_url = f"https://listado.mercadolibre.com.ar/{slug}"

    max_price_i = int(max_price or 0)
    presas: list[dict] = []

    PROFILE_PATH.mkdir(parents=True, exist_ok=True)
    DEBUG_SHOT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_PATH),
            headless=headless,
            channel="chrome",
            locale="es-AR",
            viewport={"width": 1365, "height": 900},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )

        context.add_init_script(
            '''
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['es-AR', 'es', 'en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            window.chrome = window.chrome || { runtime: {} };
            '''
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(60000)

        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=60000)

            if not headless:
                try:
                    page.bring_to_front()
                except Exception:
                    pass

            _human_touch(page)

            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass

            # PRIMERO: si ya hay cards, NO es bloqueo
            if _has_result_cards(page):
                print("✅ ML: la página cargó cards de resultados.")
            else:
                html_lower = ""
                try:
                    html_lower = page.content().lower()
                except Exception:
                    pass

                if html_lower and _looks_like_block(html_lower):
                    print("🧩 ML: Detectado bloqueo/verificación.")
                    if headless:
                        return [{"source": "mercadolibre", "blocked": True, "url": target_url}]

                    print("🧩 ML: Modo headful: resolvé la verificación/login en la ventana (75s)...")
                    try:
                        page.bring_to_front()
                    except Exception:
                        pass

                    try:
                        page.wait_for_selector(
                            "div.poly-card, div.ui-search-result__wrapper, li.ui-search-layout__item",
                            timeout=75000,
                        )
                    except Exception:
                        pass

                    _human_touch(page)

                    if not _has_result_cards(page):
                        try:
                            html_lower = page.content().lower()
                        except Exception:
                            html_lower = ""

                        if html_lower and _looks_like_block(html_lower):
                            print("❌ ML: Sigue bloqueado después del intento manual.")
                            try:
                                page.screenshot(path=str(DEBUG_SHOT_PATH), full_page=True)
                                print(f"📸 ML DEBUG: screenshot guardado en {DEBUG_SHOT_PATH}")
                            except Exception:
                                pass
                            return [{"source": "mercadolibre", "blocked": True, "url": target_url}]

            try:
                page.wait_for_selector(
                    "div.poly-card, div.ui-search-result__wrapper, li.ui-search-layout__item",
                    timeout=15000,
                )
                cards = page.locator(
                    "div.poly-card, div.ui-search-result__wrapper, li.ui-search-layout__item"
                )
            except Exception:
                print("🐺 ML DEBUG: no se encontró selector de cards.")
                try:
                    page.screenshot(path=str(DEBUG_SHOT_PATH), full_page=True)
                    print(f"📸 ML DEBUG: screenshot guardado en {DEBUG_SHOT_PATH}")
                except Exception:
                    pass
                return []

            _human_touch(page)

            count_cards = cards.count()
            print(f"🐺 ML DEBUG: cards encontrados = {count_cards} | url={target_url} | headless={headless}")

            if count_cards == 0:
                try:
                    page.screenshot(path=str(DEBUG_SHOT_PATH), full_page=True)
                    print(f"📸 ML DEBUG: screenshot guardado en {DEBUG_SHOT_PATH}")
                except Exception:
                    pass
                return []

            n = min(count_cards, 60)
            for i in range(n):
                try:
                    card = cards.nth(i)

                    link = None
                    a = card.locator("a.ui-search-link").first
                    if a.count() == 0:
                        a = card.locator("a").first
                    if a.count() > 0:
                        link = a.get_attribute("href")
                        if link and link.startswith("/"):
                            link = "https://www.mercadolibre.com.ar" + link

                    title = ""
                    tloc = card.locator(
                        "h2.ui-search-item__title, h2, span.poly-component__title, a.ui-search-link"
                    ).first
                    if tloc.count() > 0:
                        title = (tloc.inner_text() or "").strip()
                    if not title:
                        txt = (card.inner_text() or "").strip()
                        title = (txt.split("\n")[0].strip() if txt else "")
                    if not title:
                        continue

                    precio = None
                    ploc = card.locator(
                        "span.andes-money-amount__fraction, span.price-tag-fraction"
                    ).first
                    if ploc.count() > 0:
                        raw = (ploc.inner_text() or "").strip().replace(".", "").replace(",", "")
                        if raw.isdigit():
                            precio = int(raw)

                    if precio is None:
                        precio = _to_int_price(card.inner_text() or "")

                    if precio is None:
                        continue
                    if max_price_i > 0 and int(precio) > max_price_i:
                        continue

                    presas.append(
                        {
                            "title": title[:120],
                            "price": int(precio),
                            "url": link or target_url,
                            "source": "mercadolibre",
                        }
                    )
                except Exception:
                    continue

            print(f"🐺 ML DEBUG: presas parseadas = {len(presas)}")
            return presas

        finally:
            try:
                context.close()
            except Exception:
                pass


# -------------------------------------------------
# Router central
# -------------------------------------------------
def hunt_offers(url: str, keyword: str, max_price: int):
    host = _domain(url)

    if "mercadolibre" in host:
        if ML_FORCE_HEADLESS:
            res = _scrape_mercadolibre(url, keyword, max_price, headless=True)
            if res and isinstance(res[0], dict) and res[0].get("blocked"):
                return []
            return res

        res = _scrape_mercadolibre(url, keyword, max_price, headless=False)
        if res and isinstance(res[0], dict) and res[0].get("blocked"):
            return []
        return res

    return hunt_offers_generic(url, keyword, max_price)