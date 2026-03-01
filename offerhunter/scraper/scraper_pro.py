from __future__ import annotations

import re
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


def _is_mercadolibre_url(url: str) -> bool:
    try:
        host = urlparse(str(url)).netloc.lower().strip()
        return "mercadolibre" in host
    except Exception:
        return False


def _to_int_price(text: str) -> int | None:
    """Convierte "$ 1.234.567" / "$1,234,567" a int."""
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


def hunt_offers(url_input: str, keyword: str, max_price: int):
    """Scraper de **MercadoLibre**.

    Parámetros:
      - url_input: URL de listado/búsqueda de ML (recomendado).
      - keyword: keyword para filtrar por texto (simple contains).
      - max_price: precio máximo (int).

    Devuelve:
      List[Dict]: [{"titulo": str, "precio": int, "link": str}, ...]
    """
    if url_input and url_input.startswith("http") and not _is_mercadolibre_url(url_input):
        raise ValueError(f"[hunt_offers] SOLO MercadoLibre. URL recibida: {url_input}")

    # Si pasan keyword sin URL, armamos búsqueda en ML
    if url_input and url_input.startswith("http"):
        target_url = url_input
    else:
        slug = (keyword or "").strip().replace(" ", "-")
        target_url = f"https://listado.mercadolibre.com.ar/{slug}"

    if not _is_mercadolibre_url(target_url):
        raise ValueError(f"[hunt_offers] SOLO MercadoLibre. URL recibida: {target_url}")

    keyword_l = (keyword or "").strip().lower()
    presas = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=60000)

            # Resultados ML (clases típicas)
            try:
                page.wait_for_selector("div.ui-search-result__wrapper, div.poly-card", timeout=5000)
            except Exception:
                print("⚠ No se encontraron resultados o selector inválido.")
                browser.close()
                return []

            # Scroll suave (a veces ML carga lazy)
            page.mouse.wheel(0, 1200)
            page.wait_for_timeout(1500)

            items = page.locator("div.ui-search-result__wrapper, div.poly-card").all()

            for item in items[:60]:
                try:
                    texto = item.inner_text()

                    # Filtro keyword (si viene)
                    if keyword_l and keyword_l not in texto.lower():
                        continue

                    precio = _to_int_price(texto)
                    if precio is None:
                        continue

                    if int(precio) > int(max_price):
                        continue

                    # Link
                    link = None
                    a = item.locator("a").first
                    if a:
                        link = a.get_attribute("href")

                    if link and link.startswith("/"):
                        link = "https://www.mercadolibre.com.ar" + link

                    # Título: primer renglón
                    titulo = (texto.split("\n")[0] or "").strip()
                    if not titulo:
                        titulo = keyword.capitalize() if keyword else "Oferta"

                    presas.append({"titulo": titulo[:120], "precio": int(precio), "link": link or target_url})
                except Exception:
                    continue

            return presas

        finally:
            try:
                context.close()
            finally:
                browser.close()