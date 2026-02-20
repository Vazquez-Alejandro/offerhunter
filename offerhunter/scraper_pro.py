from playwright.sync_api import sync_playwright

def hunt_offers(url, keyword, max_price):
    with sync_playwright() as p:
        # Mantenemos headless=False para monitorear
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            target_url = f"https://listado.mercadolibre.com.ar/{keyword.replace(' ', '-')}"
            print(f"🕵️ Sabueso rastreando en: {target_url}")
            
            page.goto(target_url, wait_until="networkidle", timeout=60000)
            
            # 1. Limpiamos pop-ups que estorben
            try:
                page.click("button:has-text('Aceptar cookies')", timeout=3000)
                page.click("button:has-text('Más tarde')", timeout=3000)
            except:
                pass

            # 2. Selector que agarra tanto cuadraditos como filas
            # Buscamos el contenedor genérico de cada celda de producto
            page.wait_for_selector(".ui-search-layout__item", timeout=10000)
            items = page.locator(".ui-search-layout__item").all()
            print(f"🔎 Items en el radar: {len(items)}")

            presas = []
            for item in items[:20]:
                try:
                    # El título siempre está en un h2 o h3 dentro del item
                    titulo = item.locator("h2, h3").first.inner_text().strip()
                    
                    # El precio: buscamos la clase que contiene la 'fraction'
                    # Usamos .first para evitar agarrar el precio "tachado" si hay oferta
                    precio_text = item.locator(".andes-money-amount__fraction").first.inner_text()
                    precio = int("".join(filter(str.isdigit, precio_text)))
                    
                    # El link: el primer enlace del contenedor
                    link = item.locator("a").first.get_attribute("href")

                    print(f"   ✅ Encontré: {titulo[:30]}... | ${precio}")

                    if precio <= float(max_price):
                        print("      🎯 ¡DENTRO DEL PRESUPUESTO!")
                        presas.append({'titulo': titulo, 'precio': precio, 'link': link})
                except Exception:
                    continue

            browser.close()
            return presas

        except Exception as e:
            print(f"🚨 Error en la cacería: {e}")
            if 'browser' in locals(): browser.close()
            return []

if __name__ == "__main__":
    # Test con margen amplio para confirmar que lee
    res = hunt_offers("", "iphone 13", 5000000)
    print(f"\n🏆 Total de ofertas capturadas: {len(res)}")