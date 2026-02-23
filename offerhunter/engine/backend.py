import requests
from flask import Flask, request
import sqlite3
from scraper.alertas import notificar_caceria_iniciada, notificar_oferta_encontrada # <--- Agregamos alerta de hallazgo
from scraper.scraper_pro import hunt_offers as rastrear # <--- Importamos el scraper
from apscheduler.schedulers.background import BackgroundScheduler # <--- EL MOTOR

DB_NAME = "offerhunter.db"
VERIFY_TOKEN = "offerhunter_token"

app = Flask(__name__)

# --- EL MOTOR DE FONDO (El Vigilante) ---
def vigilar_ofertas():
    print("🐺 Olfateando la red en busca de presas...")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Traemos las cazas activas (asumiendo que agregaste columna url y precio_max)
    cursor.execute("SELECT id, usuario_id, producto, link, precio_max FROM cazas WHERE estado = 'activa'")
    cacerias = cursor.fetchall()
    
    for caza_id, user_id, producto, url, p_max in cacerias:
        if not url: continue
        
        # Ejecutamos el scraper que ya pulimos
        resultados = rastrear(url, producto, p_max)
        
        if resultados:
            for r in resultados:
                # Si encontramos algo por debajo del precio, avisamos
                if r['precio'] <= p_max:
                    print(f"🎯 ¡PRESA ENCONTRADA! {r['titulo']} a ${r['precio']}")
                    notificar_oferta_encontrada(user_id, r) # <--- Función que debés tener en alertas.py
    
    conn.close()

# Iniciamos el Scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(func=vigilar_ofertas, trigger="interval", minutes=15) # Cada 15 min
scheduler.start()

# --- (Tus funciones de DB y Webhook siguen igual abajo) ---
# ... (guardar_caza, obtener_usuario_id, @app.route("/webhook"), etc.)

if __name__ == "__main__":
    app.run(port=5000, debug=False) # Debug en False para que el scheduler no se duplique