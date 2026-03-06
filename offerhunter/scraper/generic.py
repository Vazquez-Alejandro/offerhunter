# -*- coding: utf-8 -*-
"""
OfferHunter - Generic scraper

Estrategia:
- Carrefour (carrefour.com.ar): usar API VTEX (JSON) porque el DOM puede venir vacío
  (tu log ya mostró total anchors = 0).
- Otros sitios: Playwright + scroll + extracción DOM (fallback).

Env vars:
- OH_SCRAPER_DEBUG=1  -> imprime logs [generic]
- OH_HEADLESS=0       -> abre navegador visible (para debug)
"""

from __future__ import annotations

import os
import re
import time
import unicodedata
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests

DEBUG = os.getenv("OH_SCRAPER_DEBUG", "0") == "1"
HEADLESS = os.getenv("OH_HEADLESS", "1") != "0"


def _log(*args):
    if DEBUG:
        print("[generic]", *args)


def _ensure_int(x: Any, default: int = 0) -> int:
    try:
        return int(float(x))
    except Exception:
        return default


def _norm(s: str) -> str:
    s = (s or "").lower().strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _kw_match(title: str, keyword: str) -> bool:
    k = _norm(keyword)
    if not k:
        return True
    t = _norm(title)
    tokens = [x for x in k.split() if x]
    return all(tok in t for tok in tokens)


def _parse_price_ar(raw: Any) -> Optional[int]:
    """
    Convierte:
      "$ 5.639,00" -> 5639
      "18.000"     -> 18000
      5639.0       -> 5639
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        try:
            return int(raw)
        except Exception:
            return None

    s = str(raw).strip()
    if not s:
        return None

    s = s.replace("$", "").replace(" ", "")
    s = re.sub(r"[^0-9\.,]", "", s)

    # "5.639,00" -> "5.639" -> "5639"
    if "," in s:
        s = s.split(",")[0]
    s = s.replace(".", "")

    if not s.isdigit():
        return None
    try:
        return int(s)
    except Exception:
        return None


# ----------------------------
# Carrefour: VTEX API strategy
# ----------------------------

def _carrefour_category_path(u: str) -> str:
    """
    Toma una URL como:
      https://www.carrefour.com.ar/Bebidas/Fernet-y-aperitivos/Fernet?order=
    y devuelve:
      /Bebidas/Fernet-y-aperitivos/Fernet
    """
    p = urlparse(u)
    path = p.path.strip("/")
    return "/" + path if path else "/"


def _carrefour_api_search(category_url: str, keyword: str, max_price: int, limit: int = 80) -> List[Dict[str, Any]]:
    """
    Busca productos en Carrefour usando la API pública de VTEX:
      https://www.carrefour.com.ar/api/catalog_system/pub/products/search/<categoryPath>?_from=0&_to=49

    Devuelve items:
      {title, price, url, source}
    """
    base = "https://www.carrefour.com.ar"
    path = _carrefour_category_path(category_url)
    api = base + "/api/catalog_system/pub/products/search" + path

    headers = {
        "user-agent": "Mozilla/5.0",
        "accept": "application/json,text/plain,*/*",
        "referer": base + "/",
    }

    out: List[Dict[str, Any]] = []
    seen = set()

    batch = 50
    kw = (keyword or "").strip()

    _log("carrefour API:", api)
    _log("keyword:", repr(kw), "max_price:", max_price)

    # paginamos hasta alcanzar limit o hasta que VTEX devuelva vacío
    for start in range(0, max(limit, batch), batch):
        end = start + batch - 1
        params = {"_from": start, "_to": end}

        try:
            r = requests.get(api, params=params, headers=headers, timeout=30)
        except Exception as e:
            _log("carrefour API error:", e)
            break

        if r.status_code != 200:
            _log("carrefour API status:", r.status_code)
            break

        try:
            data = r.json()
        except Exception:
            _log("carrefour API: json inválido")
            break

        if not isinstance(data, list) or not data:
            _log("carrefour API: sin datos (fin paginado)")
            break

        for prod in data:
            title = (prod.get("productName") or "").strip()
            if not title:
                continue

            # keyword strict por tokens (sin acentos)
            if kw and not _kw_match(title, kw):
                continue

            # link
            link = prod.get("link") or ""
            if link and link.startswith("/"):
                link = base + link

            # precio: items[0].sellers[0].commertialOffer.Price
            price_raw = None
            try:
                price_raw = prod["items"][0]["sellers"][0]["commertialOffer"]["Price"]
            except Exception:
                price_raw = None

            price = _parse_price_ar(price_raw)
            if price is None:
                continue

            if max_price > 0 and price > max_price:
                continue

            key = link or title
            if key in seen:
                continue
            seen.add(key)

            out.append({"title": title, "price": price, "url": link, "source": "carrefour_api"})

            if len(out) >= limit:
                _log("carrefour API returned:", len(out))
                return out

    _log("carrefour API returned:", len(out))
    return out


# ---------------------------------
# Fallback genérico: Playwright DOM
# ---------------------------------

def _playwright_available() -> bool:
    try:
        import playwright  # noqa
        return True
    except Exception:
        return False


def _hunt_offers_playwright_dom(url: str, keyword: str, max_price: int, limit: int = 80) -> List[Dict[str, Any]]:
    """
    Fallback general para sitios que sí renderizan productos en DOM.
    """
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception:
        _log("Playwright no disponible.")
        return []

    base = "{u.scheme}://{u.netloc}".format(u=urlparse(url))
    seen = set()
    out: List[Dict[str, Any]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1365, "height": 900},
            locale="es-AR",
        )
        page = context.new_page()
        page.set_default_timeout(60000)

        page.goto(url, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=45000)
        except Exception:
            pass
        time.sleep(1.0)

        # Scroll para lazy-load
        last_count = 0
        stable = 0
        for _ in range(12):
            page.mouse.wheel(0, 2600)
            time.sleep(1.0)

            links = page.locator(
                "a[href*='/p/'], a[href*='/product/'], a[href*='/producto/'], a[data-testid*='product']"
            )
            cnt = links.count()
            _log("scroll cards:", cnt)

            if cnt <= last_count:
                stable += 1
            else:
                stable = 0
                last_count = cnt

            if stable >= 3:
                break

        links = page.locator(
            "a[href*='/p/'], a[href*='/product/'], a[href*='/producto/'], a[data-testid*='product']"
        )
        total = min(links.count(), 140)
        _log("total anchors:", links.count(), "-> scanning:", total)

        for i in range(total):
            if len(out) >= limit:
                break

            try:
                a = links.nth(i)
                href = a.get_attribute("href") or ""
                if not href:
                    continue
                full_url = urljoin(base, href)

                # Título
                title = (a.get_attribute("title") or "").strip()
                if not title:
                    try:
                        title = (a.inner_text() or "").strip()
                    except Exception:
                        title = ""

                title = title.strip()

                # cortar basura típica de Frávega
                cut_tokens = ["Vendido por", "$", "Precio s/imp", "Precio s/imp.", "Precio s/imp. nac"]
                for tok in cut_tokens:
                    if tok in title:
                        title = title.split(tok)[0].strip()

                # si venía con saltos de línea, quedarnos con la primera línea
                title = title.split("\n")[0].strip()

                if not title:
                    continue
                if len(title) > 160:
                    title = title[:160].strip()         
                # Keyword
                if keyword and not _kw_match(title, keyword):
                    continue

                # Precio cercano al contenedor
                price = None
                try:
                    container = a.locator("xpath=ancestor::*[self::article or self::div][1]")
                    price_candidates = container.locator("text=/\\$\\s*\\d/")

                    parsed_prices = []
                    total_prices = min(price_candidates.count(), 12)

                    for j in range(total_prices):
                        try:
                            raw_price = (price_candidates.nth(j).inner_text() or "").strip().lower()

                            # ignorar precios sin impuesto nacional
                            if "imp" in raw_price or "nac" in raw_price:
                                continue

                            p = _parse_price_ar(raw_price)
                            if p is not None and p > 0:
                                parsed_prices.append(p)
                        except Exception:
                            continue

                    if parsed_prices:
                        price = min(parsed_prices)
                except Exception:
                    price = None

                if price is None:
                    continue
                if max_price > 0 and price > max_price:
                    continue

                if full_url in seen:
                    continue
                seen.add(full_url)

                out.append({"title": title, "price": price, "url": full_url, "source": "generic_dom"})
            except Exception:
                continue

        browser.close()

    _log("dom returned:", len(out))
    return out


# ----------------------------
# Public entrypoint
# ----------------------------

def hunt_offers_generic(url: str, keyword: str = "", max_price: Any = 0, depth: int = 1) -> List[Dict[str, Any]]:
    """
    Un único entrypoint para OfferHunter.
    Decide estrategia según dominio.
    """
    host = urlparse(url).netloc.lower()
    max_price_i = _ensure_int(max_price, 0)

    _log("URL:", url)
    _log("keyword:", repr(keyword), "max_price:", max_price_i)

    # Carrefour: SI o SI API, porque DOM te dio anchors=0
    if "carrefour.com.ar" in host:
        _log("strategy: carrefour_api")
        return _carrefour_api_search(url, keyword, max_price_i, limit=80)

    # Otros: fallback DOM con Playwright
    _log("strategy: playwright_dom")
    return _hunt_offers_playwright_dom(url, keyword, max_price_i, limit=80)