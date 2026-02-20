from playwright.sync_api import sync_playwright
import re


def _to_int_price(text: str) -> int | None:
    """
    Convierte "$ 1.234.567" / "$1,234,567" en int.
    """
    if not text:
        return None
    m = re.search(r"\$\s*([\d\.\,]+)", text)
    if not m:
        return None
    raw = m.group(1).replace(".", "").replace(",", "")
    try:
        return int(raw)
    except:
        return None


def hunt_offers(url_input: str, keyword: str, max_price: int):
    """
    ✅ SOLO MERCADOLIBRE
    Devuelve: [{"titulo": str, "precio": int, "link": str}, ...]
    """

    # Si te pasan "ps5" sin esquema, armamos búsqueda de ML
    if url_input and url_input.startswith("http"):
        target_url = url_input
    else:
        slug = (keyword or "").strip().replace(" ", "-")
        target_url = f"https://listado.mercadolibre.com.ar/{slug}"

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
            print(f"🕵️ Sabueso rastreando en: {target_url}")
            page.goto(target_url, wait_until="domcontentloaded", timeout=60000)

            # Esperamos contenedores reales de resultados
            page.wait_for_selector("div.ui-search-result__wrapper, div.poly-card", timeout=20000)

            # Scroll suave (a veces ML carga lazy)
            page.mouse.wheel(0, 1200)
            page.wait_for_timeout(1500)

            items = page.locator("div.ui-search-result__wrapper, div.poly-card").all()
            print(f"🔎 Items en el radar: {len(items)}")

            for item in items[:60]:
                try:
                    texto = item.inner_text()

                    # Filtro keyword (si no querés filtrar, comentá estas 2 líneas)
                    if keyword_l and keyword_l not in texto.lower():
                        continue

                    precio = _to_int_price(texto)
                    if precio is None:
                        continue

                    if precio > int(max_price):
                        continue

                    # Link
                    link = None
                    a = item.locator("a").first
                    if a:
                        link = a.get_attribute("href")

                    if link and link.startswith("/"):
                        link = "https://www.mercadolibre.com.ar" + link

                    # Título (mejor que poner keyword)
                    titulo = texto.split("\n")[0].strip()
                    if not titulo:
                        titulo = keyword.capitalize() if keyword else "Oferta"

                    presas.append({
                        "titulo": titulo[:120],
                        "precio": precio,
                        "link": link or target_url
                    })

                    # debug opcional:
                    # print(f"   ✅ Encontré: {titulo[:25]}... | ${precio}")

                except:
                    continue

        except Exception as e:
            print(f"🚨 Error en la cacería: {e}")

        finally:
            context.close()
            browser.close()

    return presas


if __name__ == "__main__":
    res = hunt_offers("https://listado.mercadolibre.com.ar/iphone-15", "iphone 15", 1000000)
    print(f"🏆 Resultados: {len(res)}")
    for r in res[:5]:
        print(r)