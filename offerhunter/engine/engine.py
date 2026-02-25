import os
import sqlite3
from datetime import datetime, timedelta
from urllib.parse import urlparse

from apscheduler.schedulers.background import BackgroundScheduler

from scraper.scraper_pro import hunt_offers

# =========================
# DB PATH ROBUSTO
# =========================
BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # .../offerhunter
DB_PATH = os.path.join(BASE_DIR, "offerhunter.db")

# Evita crear mil schedulers por los reruns de Streamlit
_scheduler = None


# =========================
# HELPERS
# =========================
def _domain_from_url(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower().strip()
        if host.startswith("www."):
            host = host[4:]
        return host or "unknown"
    except Exception:
        return "unknown"


def _freq_to_minutes(freq: str) -> int:
    """
    Convierte strings tipo:
    - "15 min", "30 min", "45 min"
    - "1 hora", "2 horas", "3 hs"
    a minutos.
    """
    if not freq:
        return 60

    s = str(freq).strip().lower()

    # normalizaciones
    s = s.replace("hs", "hora").replace("horas", "hora")
    s = s.replace("minutos", "min").replace("mins", "min")

    # minutos comunes
    if "15" in s and "min" in s:
        return 15
    if "30" in s and "min" in s:
        return 30
    if "45" in s and "min" in s:
        return 45

    # horas comunes
    if "1" in s and "hora" in s:
        return 60
    if "2" in s and "hora" in s:
        return 120
    if "3" in s and "hora" in s:
        return 180
    if "4" in s and "hora" in s:
        return 240

    # fallback: si hay dígitos sueltos, interpretarlos como minutos
    digits = "".join(c for c in s if c.isdigit())
    return int(digits) if digits else 60


def _parse_sqlite_dt(value) -> datetime:
    """
    SQLite suele guardar 'YYYY-MM-DD HH:MM:SS' (UTC si usás CURRENT_TIMESTAMP).
    """
    if not value:
        return datetime(1970, 1, 1)

    s = str(value).strip()
    s = s.replace("T", " ").replace("Z", "")
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return datetime(1970, 1, 1)


def _clamp_minutes_by_plan(plan: str, mins: int) -> int:
    """
    Blindaje mínimo por plan (por si se guarda mal frecuencia).
    """
    p = (plan or "").strip().lower()
    if p == "omega":
        return max(mins, 60)
    if p == "beta":
        return max(mins, 30)
    if p == "alfa":
        return max(mins, 15)
    return max(mins, 60)


# =========================
# HEALTH + LOGS
# =========================
def _mark_site_ok(cursor, domain: str):
    cursor.execute(
        """
        INSERT INTO site_health (domain, status, last_ok_at, fail_streak, last_error)
        VALUES (?, 'ok', CURRENT_TIMESTAMP, 0, NULL)
        ON CONFLICT(domain) DO UPDATE SET
            status='ok',
            last_ok_at=CURRENT_TIMESTAMP,
            fail_streak=0,
            last_error=NULL
        """,
        (domain,),
    )


def _mark_site_fail(cursor, domain: str, err: str):
    cursor.execute(
        """
        INSERT INTO site_health (domain, status, last_fail_at, fail_streak, last_error)
        VALUES (?, 'broken', CURRENT_TIMESTAMP, 1, ?)
        ON CONFLICT(domain) DO UPDATE SET
            status='broken',
            last_fail_at=CURRENT_TIMESTAMP,
            fail_streak=fail_streak + 1,
            last_error=?
        """,
        (domain, err[:500], err[:500]),
    )


def _log_run(cursor, domain: str, caza_id: int, ok: int, items_found: int, error: str | None):
    cursor.execute(
        """
        INSERT INTO scrape_runs (domain, caza_id, ok, items_found, error)
        VALUES (?, ?, ?, ?, ?)
        """,
        (domain, caza_id, ok, items_found, (error[:800] if error else None)),
    )


# =========================
# MAIN LOOP
# =========================
def vigilar_ofertas():
    print("🐺 Vigilando ofertas...")

    now = datetime.utcnow()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            usuario_id,
            producto,
            link,
            precio_max,
            COALESCE(frecuencia,'') as frecuencia,
            COALESCE(plan,'omega') as plan,
            last_check
        FROM cazas
        WHERE estado = 'activa'
        """
    )
    cazas = cursor.fetchall()
    print(f"📦 Total cazas activas: {len(cazas)}")

    # 👇 TOPE anti-spam (por defecto 1 por corrida)
    # Podés cambiarlo: export MAX_ALERTS_PER_RUN=5
    try:
        max_alerts_global = int(os.getenv("MAX_ALERTS_PER_RUN", "1"))
    except Exception:
        max_alerts_global = 1

    for caza_id, user_id, producto, link, precio_max, frecuencia, plan, last_check in cazas:
        if not link:
            continue

        mins = _freq_to_minutes(frecuencia)
        mins = _clamp_minutes_by_plan(plan, mins)

        last_dt = _parse_sqlite_dt(last_check)
        if now - last_dt < timedelta(minutes=mins):
            continue

        domain = _domain_from_url(link)
        print(f"🔎 Caza #{caza_id} | {producto} | max ${precio_max} | {domain} | cada {mins} min")

        try:
            resultados = hunt_offers(link, producto, precio_max)
            items_found = len(resultados) if resultados else 0
            print(f"   📊 Resultados scraper: {items_found}")

            # Import acá (evita problemas si tocás alertas.py)
            from scraper.alertas import notificar_oferta_encontrada

            sent = 0

            for oferta in resultados or []:
                if sent >= max_alerts_global:
                    break

                link_oferta = oferta.get("link")
                precio = oferta.get("precio")

                if not link_oferta or precio is None:
                    continue

                # Parse precio
                try:
                    precio_num = float(precio)
                except Exception:
                    continue

                if precio_num > float(precio_max):
                    continue

                try:
                    # Dedup: si ya existe, UNIQUE lo bloquea
                    cursor.execute(
                        """
                        INSERT INTO seen_offers (usuario_id, caza_id, link)
                        VALUES (?, ?, ?)
                        """,
                        (user_id, caza_id, link_oferta),
                    )

                    print(f"🎯 Nueva oferta para caza {caza_id}: {link_oferta}")
                    notificar_oferta_encontrada(user_id, oferta)

                    sent += 1

                except sqlite3.IntegrityError:
                    continue

            # last_check
            cursor.execute(
                """
                UPDATE cazas
                SET last_check = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (caza_id,),
            )

            _mark_site_ok(cursor, domain)
            _log_run(cursor, domain, caza_id, 1, items_found, None)

        except Exception as e:
            err = str(e)
            print(f"⚠ Error en caza {caza_id}: {err}")

            _mark_site_fail(cursor, domain, err)
            _log_run(cursor, domain, caza_id, 0, 0, err)

            cursor.execute(
                """
                UPDATE cazas
                SET last_check = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (caza_id,),
            )

    conn.commit()
    conn.close()
    print("✅ Ciclo terminado")


# =========================
# SCHEDULER
# =========================
def start_engine(run_once: bool = False):
    """
    run_once=True: ejecuta una ronda inmediatamente (útil para debug).
    El scheduler hace tick cada 1 minuto, pero cada caza corre según su frecuencia.
    """
    global _scheduler

    print("🔥 start_engine() fue llamado")

    if run_once:
        print("⚡ Ejecutando vigilar_ofertas() manualmente")
        vigilar_ofertas()

    if _scheduler is not None:
        return

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(vigilar_ofertas, "interval", minutes=1, max_instances=1, coalesce=True)
    _scheduler.start()

    print("🚀 Motor OfferHunter iniciado (tick 1 min, frecuencia por caza)")


if __name__ == "__main__":
    start_engine(run_once=True)