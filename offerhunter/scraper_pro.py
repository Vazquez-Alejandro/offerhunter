import requests
from bs4 import BeautifulSoup
import re

def check_price(url, keywords):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None, f"Error ML: {response.status_code}"

        soup = BeautifulSoup(response.text, 'html.parser')
        # Buscamos los items del listado
        items = soup.find_all(['li', 'div'], class_=re.compile(r'ui-search-layout__item|poly-card'))

        for item in items:
            title_el = item.find(['h2', 'h3'])
            if not title_el: continue
            
            title_text = title_el.get_text().lower()
            
            # Validamos keywords
            if all(word.lower() in title_text for word in keywords.split()):
                # Buscamos el precio
                price_el = item.find('span', class_='andes-money-amount__fraction')
                if price_el:
                    price_val = float(price_el.get_text().replace('.', '').replace(',', ''))
                    return price_val, title_el.get_text()

        return None, "Producto no encontrado con esas palabras clave."
    except Exception as e:
        return None, f"Error crítico: {str(e)}"