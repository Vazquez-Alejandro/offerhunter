import requests
from bs4 import BeautifulSoup
import re

def check_price(url, keywords):
    try:
        # Headers más realistas para evitar bloqueos
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if "captcha" in response.text.lower():
            return [{"titulo": "BLOQUEO POR CAPTCHA", "precio": "0", "link": "#"}]
    
        if response.status_code != 200:
            return [{"titulo": f"Error HTTP {response.status_code}", "precio": "0", "link": "#"}]

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # ML usa 'ui-search-result__wrapper' para los contenedores principales
        items = soup.select('div.ui-search-result__wrapper, div.poly-card, li.ui-search-layout__item')
        
        resultados = []
        keywords_list = keywords.lower().split()

        for item in items:
            # Buscamos el título en cualquier etiqueta h2, h3 o a con clases de título
            title_el = item.select_one('h2, h3, .poly-component__title, .ui-search-item__title')
            if not title_el: continue
            
            title_text = title_el.get_text().strip()
            
            # Validación flexible
            if all(word in title_text.lower() for word in keywords_list):
                # Precio: Buscamos la fracción (el número grande)
                price_el = item.select_one('.andes-money-amount__fraction')
                # Link: El primer <a> que encontremos suele ser el del producto
                link_el = item.select_one('a[href]')
                
                if price_el and link_el:
                    precio = price_el.get_text().replace('.', '').replace(',', '')
                    link = link_el['href']
                    if not link.startswith('http'):
                        link = "https://www.mercadolibre.com.ar" + link

                    resultados.append({
                        "titulo": title_text,
                        "precio": precio,
                        "link": link
                    })
                    break # Encontramos el primero y salimos

        return resultados
    except Exception as e:
        return []