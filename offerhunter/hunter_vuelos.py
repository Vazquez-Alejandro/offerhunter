from playwright.sync_api import sync_playwright
import time

# 1. FUNCIÓN LIMPIADORA (Transforma texto en números para operar)
def limpiar_guita(texto):
    # De "ARS 1,305,031.00" -> 1305031
    # Borramos todo lo que no sea número antes del primer punto/coma decimal
    solo_numeros = "".join(filter(str.isdigit, texto.split(",")[0].split(".")[0]))
    return int(solo_numeros) if solo_numeros else 0

def hunt_vuelos(origen, destino, config_usuario):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        print(f"\n📡 Rastreando: {origen} -> {destino}")
        page.goto(f"https://www.google.com.ar/search?q=vuelos+directos+de+{origen}+a+{destino}")

        print("\n⚠️  CONTROL DE SEGURIDAD: Resolvé el captcha y presioná ENTER en la terminal.")
        input("👉 ENTER para continuar...")

        try:
            page.wait_for_selector("text=$", timeout=10000)
            elementos = page.locator("span:has-text('$'), span:has-text('ARS')").all()
            
            precios_encontrados = []
            for el in elementos:
                precio_raw = el.inner_text().strip()
                valor = limpiar_guita(precio_raw)
                if valor > 10000 and valor not in precios_encontrados:
                    precios_encontrados.append(valor)

            if precios_encontrados:
                # Tomamos el más barato encontrado
                menor_precio = min(precios_encontrados)
                print(f"✅ Menor precio detectado: ${menor_precio}")

                # 2. LÓGICA DE ALERTA (Piso o Descuento)
                tipo = config_usuario['tipo'] # 'piso' o 'descuento'
                objetivo = config_usuario['objetivo']
                
                disparar = False
                msg = ""

                if tipo == 'piso':
                    if menor_precio <= objetivo:
                        disparar = True
                        msg = f"🔥 ¡Bajó del piso! Precio actual: ${menor_precio} (Límite: ${objetivo})"
                
                elif tipo == 'descuento':
                    ref = config_usuario['precio_referencia']
                    ahorro = ((ref - menor_precio) / ref) * 100
                    if ahorro >= objetivo:
                        disparar = True
                        msg = f"📉 ¡OFERTÓN! Descuento del {int(ahorro)}% (Buscabas {objetivo}%)"

                if disparar:
                    print(f"\n📢 DISPARANDO NOTIFICACIÓN: {msg}")
                    # Acá iría tu llamado a auth.py para mandar el mensaje
                else:
                    print("😴 No hay ofertas que cumplan el criterio todavía.")

            else:
                print("🚨 No se capturaron precios.")

        except Exception as e:
            print(f"🚨 Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    # --- SIMULACIÓN DE INTERFAZ DE USUARIO ---
    # El usuario elige una de estas dos configuraciones:
    
    # OPCIÓN A: Por precio fijo
    # config = {'tipo': 'piso', 'objetivo': 1200000} 

    # OPCIÓN B: Por porcentaje de descuento (el 35% que querías)
    config = {
        'tipo': 'descuento', 
        'objetivo': 5, 
        'precio_referencia': 1880000 # Precio promedio normal
    }

    hunt_vuelos("Buenos Aires", "Madrid", config)