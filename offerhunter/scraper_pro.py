from playwright.sync_api import sync_playwright
import time

def check_price(url_objetivo, keywords, precio_max=5000000):
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9223")
            context = browser.contexts[0]
            page = context.new_page() # Esto evita que se trabe el dashboard
            
            page.goto(url_objetivo, wait_until="domcontentloaded", timeout=60000)
            time.sleep(5) 

            # LA LÓGICA QUE TE FUNCIONÓ (Simplificada)
            productos_encontrados = page.evaluate("""() => {
                const results = [];
                
                // 1. Tu lógica ganadora (Frávega/Musimundo)
                document.querySelectorAll('a, .product-item, article').forEach(el => {
                    const texto = el.innerText || "";
                    const link = el.tagName === 'A' ? el.href : el.querySelector('a')?.href;
                    const precioMatch = texto.match(/\\$\\s?([\\d\\.]+)/);
                    if (precioMatch && link && link.includes('http')) {
                        results.push({
                            titulo: texto.split('\\n')[0].substring(0, 70).trim(),
                            precio: parseInt(precioMatch[1].replace(/\\./g, "")),
                            link: link
                        });
                    }
                });

                // 2. Refuerzo específico para Mercado Libre (si es que la anterior no lo ve)
                document.querySelectorAll('.ui-search-result__wrapper, .poly-card').forEach(el => {
                    const titleEl = el.querySelector('.ui-search-item__title, .poly-component__title');
                    const priceEl = el.querySelector('.andes-money-amount__fraction');
                    const linkEl = el.querySelector('a');
                    if (titleEl && priceEl && linkEl) {
                        results.push({
                            titulo: titleEl.innerText.trim(),
                            precio: parseInt(priceEl.innerText.replace(/\\./g, "")),
                            link: linkEl.href
                        });
                    }
                });
                
                return results;
            }""")

            # FILTRO SIMPLE (Sin vueltas: si la palabra está, entra)
            finales = []
            k_list = [k.strip().lower() for k in keywords.split(",")]
            
            for p in productos_encontrados:
                # Si el título tiene alguna de las palabras clave y el precio es menor al max
                if any(k in p['titulo'].lower() for k in k_list) and p['precio'] <= precio_max:
                    finales.append(p)
            
            return finales
        except Exception as e:
            print(f"Error: {e}")
            return []