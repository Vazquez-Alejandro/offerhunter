import sqlite3
from apscheduler.schedulers.background import BackgroundScheduler
from scraper_pro import hunt_offers
from vistos import filtrar_nuevos
from alertas import notificar_oferta_encontrada

DB_NAME = "offerhunter.db"

scheduler = None  # 👈 GLOBAL

def vigilar_ofertas():
    print("\n🐺 Vigilando ofertas...")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, usuario_id, producto, link, precio_max
        FROM cazas
    """)

    cazas = cursor.fetchall()
    print(f"📦 Total cazas encontradas: {len(cazas)}")

    for caza_id, user_id, producto, url, precio_max in cazas:
        print(f"🔎 Procesando caza {caza_id}")

        try:
            resultados = hunt_offers(url, producto, precio_max)
            print(f"   📊 Resultados scraper: {len(resultados)}")

            nuevos = filtrar_nuevos(resultados)
            print(f"   🆕 Nuevos: {len(nuevos)}")

            for oferta in nuevos:
                if oferta.get("precio") and oferta["precio"] <= precio_max:
                    print(f"   🎯 Oferta válida: {oferta['titulo']}")
                    notificar_oferta_encontrada(user_id, oferta)

        except Exception as e:
            print(f"⚠ Error en caza {caza_id}: {e}")

    conn.close()
    print("✅ Ciclo terminado\n")


scheduler = None

def start_engine():
    global scheduler

    if scheduler is not None:
        return

    scheduler = BackgroundScheduler()
    scheduler.add_job(vigilar_ofertas, 'interval', minutes=15)
    scheduler.start()

    print("🚀 Motor iniciado correctamente")