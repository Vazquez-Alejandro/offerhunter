import os
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def check_price(url, keywords):
    # Preparamos las palabras clave
    keywords_list = str(keywords).lower().strip().split()
    resultados = []
    # Ruta absoluta para el perfil de Chrome
    user_data_dir = os.path.abspath("chrome_profile")

    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir,
                headless=True,
                args=['--disable-blink-features=AutomationControlled', '--no-sandbox', '--disable-dev-shm-usage'],
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            
            page = context.new_page()
            # Mostramos en consola a dónde vamos realmente
            print(f"[DEBUG 🐺] Navegando a: {url}")
            
            # Navegación con tiempo de espera para sitios pesados como Despegar
            page.goto(url.split('#')[0], wait_until="networkidle", timeout=90000)
            
            # Verificación de Captcha o Login
            if "login" in page.url or "account-verification" in page.url:
                context.close()
                return "AUTH_REQUIRED"

            # Bajamos un poco para disparar la carga de precios
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(4000)
            
            soup = BeautifulSoup(page.content(), 'html.parser')

            # --- CASO 1: MERCADO LIBRE ---
            if "mercadolibre.com" in url:
                items = soup.select('li.ui-search-layout__item')
                for item in items:
                    title_el = item.select_one('.ui-search-item__title, h2')
                    price_el = item.select_one('.andes-money-amount__fraction')
                    link_el = item.select_one('a.ui-search-link')
                    
                    if title_el and price_el:
                        title_text = title_el.get_text().strip().lower()
                        if any(word in title_text for word in keywords_list):
                            resultados.append({
                                "titulo": title_el.get_text().strip(),
                                "precio": "".join(filter(str.isdigit, price_el.get_text())),
                                "link": link_el['href'] if link_el else url
                            })

            # --- CASO 2: DESPEGAR ---
            elif "despegar.com" in url:
                # Selectores genéricos para hoteles o vuelos
                items = soup.select('.cluster-container, .v-cluster, .item-fare-container, .accommodation-name')
                for item in items:
                    title_el = item.select_one('.cluster-title, .title, .item-location, span')
                    price_el = item.select_one('.price-amount, .amount, .main-value')
                    
                    if price_el:
                        title_text = title_el.get_text().strip() if title_el else "Resultado Despegar"
                        # En Despegar somos más permisivos con el filtro
                        if not keywords_list or any(word in title_text.lower() for word in keywords_list):
                            resultados.append({
                                "titulo": title_text,
                                "precio": "".join(filter(str.isdigit, price_el.get_text())),
                                "link": url
                            })

            print(f"[DEBUG 🐺] Cacería terminada. Total encontrados: {len(resultados)}")
            context.close()
            
        except Exception as e:
            print(f"[DEBUG ❌] Error crítico: {e}")
            
    return resultados