import re, os
from playwright.sync_api import sync_playwright

def check_price(url, keywords):
    k_list = str(keywords).lower().strip().split()
    resultados = []
    
    with sync_playwright() as p:
        try:
            user_data_dir = os.path.join(os.getcwd(), "chrome_profile")
            context = p.chromium.launch_persistent_context(
                user_data_dir,
                headless=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080}
            )
            
            page = context.pages[0]
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            page.goto(url, wait_until="networkidle", timeout=60000)
            
            # Scroll dinámico: baja y sube un poco para engañar trackers y cargar lazy-load
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(4000)
            
            # --- MOTOR ROBUSTO: Búsqueda por "Contenedores de Candidatos" ---
            # Buscamos cualquier elemento que parezca una tarjeta de producto o bloque de texto
            bloques = page.query_selector_all("div, article, li, section")
            
            for bloque in bloques:
                try:
                    # Solo procesamos bloques que tengan el signo pesos
                    texto = bloque.inner_text()
                    if texto and '$' in texto and any(k in texto.lower() for k in k_list):
                        
                        # Extraemos el precio con una regex que ignore decimales/centavos
                        price_match = re.search(r'\$\s?([\d\.]+)', texto)
                        if price_match:
                            precio_str = price_match.group(1).replace('.', '')
                            precio_val = int(precio_str)
                            
                            # Filtro de seguridad para evitar capturar "costo de envío" o "cuotas"
                            if 10000 < precio_val < 10000000:
                                # El título suele ser la línea más larga de las primeras 3
                                lineas = [l.strip() for l in texto.split('\n') if len(l.strip()) > 10]
                                titulo = lineas[0] if lineas else "Producto hallado"
                                
                                resultados.append({
                                    "titulo": titulo[:80],
                                    "precio": precio_str,
                                    "link": url
                                })
                except:
                    continue

            context.close()
            
            # Limpieza total de duplicados (por título y precio)
            vistos = set()
            finales = []
            for r in resultados:
                key = f"{r['titulo']}{r['precio']}"
                if key not in vistos:
                    vistos.add(key)
                    finales.append(r)
            
            return sorted(finales, key=lambda x: int(x['precio']))
            
        except Exception as e:
            print(f"[❌] Error: {e}")
            return []