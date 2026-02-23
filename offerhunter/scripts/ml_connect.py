# scripts/ml_connect.py
from pathlib import Path
from playwright.sync_api import sync_playwright

STATE_PATH = Path("sessions/ml_state.json")
STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # ✅ visible
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://www.mercadolibre.com.ar/", wait_until="domcontentloaded")

        print("\n✅ Se abrió MercadoLibre.")
        print("1) Si aparece CAPTCHA, resolvelo en la ventana.")
        print("2) Si te pide login, logueate.")
        input("\nCuando termines, apretá ENTER acá para guardar la sesión... ")

        context.storage_state(path=str(STATE_PATH))
        print(f"💾 Sesión guardada en: {STATE_PATH}")

        browser.close()

if __name__ == "__main__":
    main()