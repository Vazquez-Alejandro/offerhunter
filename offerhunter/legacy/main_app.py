import time
import sqlite3
from scraper.scraper_pro import check_price
from scraper.alertas import enviar_alerta_premium

DB_NAME = "offerhunter.db"

def check_prices():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Traemos todas las alertas guardadas
    cursor.execute("SELECT id, username, url, keywords, precio_max FROM alertas")
    alertas = cursor.fetchall()

    if not alertas:
        conn.close()
        return

    for aid, username, url, keywords, precio_max in alertas:
        precio, titulo = check_price(url, keywords)
        if precio is not None and precio <= precio_max:
            # Buscamos el telegram_id del usuario
            cursor.execute("SELECT telegram_id FROM usuarios WHERE username=?", (username,))
            row = cursor.fetchone()
            if row and row[0]:
                telegram_id = row[0]
                enviar_alerta_premium(telegram_id, titulo, precio)
                print(f"✅ Oferta encontrada para {username}: {titulo} a ${precio:,.0f}")
            else:
                print(f"⚠ Usuario {username} no tiene telegram_id configurado.")
        else:
            print(f"Sin ofertas para {username} en {keywords}")

    conn.close()

if __name__ == "__main__":
    while True:
        print("🔄 Ejecutando chequeo de precios...")
        check_prices()
        print("⏳ Esperando 30 minutos para el próximo chequeo...")
        time.sleep(1800)
