import sqlite3
from datetime import datetime
from urllib.parse import urlparse

from apscheduler.schedulers.background import BackgroundScheduler

from scraper.scraper_pro import hunt_offers

DB_NAME = "offerhunter.db"

# Evita crear mil schedulers por los reruns de Streamlit
_scheduler = None


def _domain_from_url(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower().strip()
        if host.startswith("www."):
            host = host[4:]
        return host or "unknown"
    except Exception:
        return "unknown"


def _mark_site_ok(cursor, domain: str):
    cursor.execute("""
        INSERT INTO site_health (domain, status, last_ok_at, fail_streak, last_error)
        VALUES (?, 'ok', CURRENT_TIMESTAMP, 0, NULL)
        ON CONFLICT(domain) DO UPDATE SET
            status='ok',
            last_ok_at=CURRENT_TIMESTAMP,
            fail_streak=0,
            last_error=NULL
    """, (domain,))


def _mark_site_fail(cursor, domain: str, err: str):
    cursor.execute("""
        INSERT INTO site_health (domain, status, last_fail_at, fail_streak, last_error)
        VALUES (?, 'broken', CURRENT_TIMESTAMP, 1, ?)
        ON CONFLICT(domain) DO UPDATE SET
            status='broken',
            last_fail_at=CURRENT_TIMESTAMP,
            fail_streak=fail_streak + 1,
            last_error=?
    """, (domain, err[:500], err[:500]))


def _log_run(cursor, domain: str, caza_id: int, ok: int, items_found: int, error: str | None):
    cursor.execute("""
        INSERT INTO scrape_runs (domain, caza_id, ok, items_found, error)
        VALUES (?, ?, ?, ?, ?)
    """, (domain, caza_id, ok, items_found, (error[:800] if error else None)))


def vigilar_ofertas():
    print("🐺 Vigilando ofertas...")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, usuario_id, producto, link, precio_max
        FROM cazas
        WHERE estado = 'activa'
    """)
    cazas = cursor.fetchall()
    print(f"📦 Total cazas activas: {len(cazas)}")

    for caza_id, user_id, producto, link, precio_max in cazas:
        if not link:
            continue

        domain = _domain_from_url(link)
        print(f"🔎 Caza #{caza_id} | {producto} | max ${precio_max} | {domain}")

        try:
            resultados = hunt_offers(link, producto, precio_max)
            items_found = len(resultados) if resultados else 0
            print(f"   📊 Resultados scraper: {items_found}")

            # --- Aquí después enchufamos vistos + alertas ---
            # nuevos = filtrar_nuevos(resultados)
            # for oferta in nuevos:
            #     if oferta["precio"] <= precio_max:
            #         notificar_oferta_encontrada(user_id, oferta)

            # last_check
            cursor.execute("""
                UPDATE cazas
                SET last_check = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (caza_id,))

            # health + log
            _mark_site_ok(cursor, domain)
            _log_run(cursor, domain, caza_id, 1, items_found, None)

        except Exception as e:
            err = str(e)
            print(f"⚠ Error en caza {caza_id}: {err}")

            _mark_site_fail(cursor, domain, err)
            _log_run(cursor, domain, caza_id, 0, 0, err)

            # Igual actualizamos last_check para saber que lo intentó
            cursor.execute("""
                UPDATE cazas
                SET last_check = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (caza_id,))

    conn.commit()
    conn.close()
    print("✅ Ciclo terminado")


def start_engine(run_once: bool = False):
    """
    run_once=True: ejecuta una ronda inmediatamente (útil para debug).
    """
    global _scheduler

    print("🔥 start_engine() fue llamado")

    if run_once:
        print("⚡ Ejecutando vigilar_ofertas() manualmente")
        vigilar_ofertas()

    if _scheduler is not None:
        # Ya existe (Streamlit rerun)
        return

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(vigilar_ofertas, "interval", minutes=15)
    _scheduler.start()

    print("🚀 Motor OfferHunter iniciado cada 15 minutos")


if __name__ == "__main__":
    start_engine(run_once=False)