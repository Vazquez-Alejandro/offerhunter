import re, os, random
from playwright.sync_api import sync_playwright

def check_price(url, keywords):
    k_list = str(keywords).lower().strip().split()
    resultados = []
    
    with sync_playwright() as p:
        try:
            # Usamos Chromium de Playwright pero bien disfrazado
            user_data_dir = os.path.join(os.getcwd(), "bot_profile")
            context = p.chromium.launch_persistent_context(
                user_data_dir,
                headless=False, # Mantenelo así que es lo que funcionó
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                args=['--disable-blink-features=AutomationControlled']
            )
            
            page = context.pages[0]
            page.set_viewport_size({"width": 1280, "height": 720})

            print(f"[DEBUG 🐺] Olfateando... No cierres la ventana.")
            page.goto(url, wait_until="commit", timeout=30000)

            # Espera a que aparezca cualquier signo de pesos
            try:
                page.wait_for_selector("text=$", timeout=20000)
                print("[!] Precios detectados en pantalla.")
            except:
                print("[!] No se ven precios todavía...")

            # Scroll para que carguen las imágenes y textos
            page.mouse.wheel(0, 800)
            page.wait_for_timeout(9000)

            # ESTRATEGIA UNIVERSAL: Buscamos todos los artículos o divs que tengan un "$"
            # Esto sirve para la Home y para la lista de búsqueda
            elementos = page.query_selector_all("//div[contains(., '$')]")

            for el in elementos:
                try:
                    # Solo nos interesan bloques pequeños (cards), no toda la pantalla
                    txt = el.inner_text()
                    if txt and 50 < len(txt) < 500: # Filtro de tamaño de texto de una 'card'
                        if any(k in txt.lower() for k in k_list) and "$" in txt:
                            # Extraer precio
                            match = re.search(r'\$\s?([\d\.,]+)', txt)
                            if match:
                                precio_raw = match.group(1).replace('.', '').replace(',', '')
                                if 1000 < int(precio_raw) < 90000000:
                                    lineas = [l.strip() for l in txt.split('\n') if len(l.strip()) > 3]
                                    resultados.append({
                                        "titulo": f"[$] {lineas[0][:50]}",
                                        "precio": precio_raw,
                                        "link": url
                                    })
                except: continue

            context.close()
            
            # Limpiar duplicados
            finales = {f"{r['titulo']}{r['precio']}": r for r in resultados}.values()
            return sorted(list(finales), key=lambda x: int(x['precio']))
            
        except Exception as e:
            print(f"[❌] Error: {e}")
            return []