import sqlite3
from apscheduler.schedulers.background import BackgroundScheduler

from scraper_pro import hunt_offers

DB_NAME = "offerhunter.db"

# Evita crear mil schedulers por los reruns de Streamlit
_scheduler = None


def _tiene_columna(cursor, tabla: str, col: str) -> bool:
    cursor.execute(f"PRAGMA table_info({tabla});")
    cols = [r[1].lower() for r in cursor.fetchall()]
    return col.lower() in cols


def _asegurar_schema():
    """
    Tu DB actual (según lo que pegaste) es:
    cazas(id, usuario_id, producto, link, precio_max, frecuencia, tipo_alerta, plan)

    Este helper NO te rompe nada:
    - crea la tabla si no existe
    - agrega columnas opcionales si faltan (estado, last_check)
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cazas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            producto TEXT,
            link TEXT,
            precio_max INTEGER,
            frecuencia TEXT,
            tipo_alerta TEXT DEFAULT 'piso',
            plan TEXT
        )
    """)

    # Opcionales (por si querés después filtrar activas / guardar last_check)
    if not _tiene_columna(cursor, "cazas", "estado"):
        cursor.execute("ALTER TABLE cazas ADD COLUMN estado TEXT DEFAULT 'activa'")
    if not _tiene_columna(cursor, "cazas", "last_check"):
        cursor.execute("ALTER TABLE cazas ADD COLUMN last_check TIMESTAMP")

    conn.commit()
    conn.close()


def vigilar_ofertas():
    print("🐺 Vigilando ofertas...")

    _asegurar_schema()

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Si existe estado, filtramos activas. Si no, traemos todo.
    if _tiene_columna(cursor, "cazas", "estado"):
        cursor.execute("""
            SELECT id, usuario_id, producto, link, precio_max
            FROM cazas
            WHERE estado = 'activa'
        """)
    else:
        cursor.execute("""
            SELECT id, usuario_id, producto, link, precio_max
            FROM cazas
        """)

    cazas = cursor.fetchall()
    print(f"📦 Total cazas encontradas: {len(cazas)}")

    for caza_id, user_id, producto, url, precio_max in cazas:
        if not url:
            continue

        print(f"🔎 Procesando caza {caza_id} | {producto} | max ${precio_max}")

        try:
            resultados = hunt_offers(url, producto, precio_max)
            print(f"   📊 Resultados scraper: {len(resultados)}")

            # Acá después enchufamos vistos + alertas si querés:
            # nuevos = filtrar_nuevos(resultados)
            # for oferta in nuevos: notificar_oferta_encontrada(user_id, oferta)

            # Guardar last_check si existe
            if _tiene_columna(cursor, "cazas", "last_check"):
                cursor.execute("""
                    UPDATE cazas SET last_check = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (caza_id,))

        except Exception as e:
            print(f"⚠ Error en caza {caza_id}: {e}")

    conn.commit()
    conn.close()
    print("✅ Ciclo terminado")


def start_engine(run_once=False):
    """
    run_once=True: ejecuta una ronda inmediatamente (útil para debug).
    """
    global _scheduler

    _asegurar_schema()

    print("🔥 start_engine() fue llamado")

    if run_once:
        print("⚡ Ejecutando vigilar_ofertas() manualmente")
        vigilar_ofertas()

    if _scheduler is not None:
        # Ya existe (Streamlit rerun)
        return

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(vigilar_ofertas, 'interval', minutes=15)
    _scheduler.start()

    print("🚀 Motor OfferHunter iniciado cada 15 minutos")


if __name__ == "__main__":
    start_engine(run_once=True)