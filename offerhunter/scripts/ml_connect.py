from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parents[1]  # .../offerhunter
PROFILE_PATH = BASE_DIR / "sessions" / "ml_profile"
PROFILE_PATH.mkdir(parents=True, exist_ok=True)


def main():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_PATH),
            headless=False,
            channel="chrome",
            viewport={"width": 1365, "height": 900},
            locale="es-AR",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )

        context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['es-AR', 'es', 'en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            window.chrome = window.chrome || { runtime: {} };
            """
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.mercadolibre.com.ar/", wait_until="domcontentloaded")

        try:
            page.bring_to_front()
        except Exception:
            pass

        print("\n✅ Se abrió MercadoLibre con perfil persistente.")
        print("1) Si aparece CAPTCHA, resolvelo en la ventana.")
        print("2) Si te pide login, logueate.")
        print("3) Navegá un poco por MercadoLibre para dejar la sesión 'caliente'.")
        input("\nCuando termines, apretá ENTER acá para cerrar y guardar el perfil... ")

        context.close()
        print(f"💾 Perfil persistente listo en: {PROFILE_PATH}")


if __name__ == "__main__":
    main()