import os
from datetime import datetime, timedelta
from urllib.parse import urlparse

from apscheduler.schedulers.background import BackgroundScheduler

from auth.supabase_client import supabase
from scraper.scraper_pro import hunt_offers

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


def _parse_dt(value) -> datetime:
    """
    Supabase suele devolver ISO string o datetime (según cliente).
    """
    if not value:
        return datetime(1970, 1, 1)

    if isinstance(value, datetime):
        return value

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
# MAIN LOOP
# =========================
def vigilar_ofertas():
    print("🐺 Vigilando ofertas...")

    now = datetime.utcnow()

    # Traer cazas activas desde Supabase
    res = (
        supabase
        .table("cazas")
        .select("id, user_id, producto, link, precio_max, frecuencia, plan, last_check")
        .eq("estado", "activa")
        .execute()
    )
    cazas = res.data or []
    print(f"📦 Total cazas activas: {len(cazas)}")

    # Tope anti-spam por corrida
    try:
        max_alerts_global = int(os.getenv("MAX_ALERTS_PER_RUN", "1"))
    except Exception:
        max_alerts_global = 1

    for c in cazas:
        caza_id = c.get("id")
        user_id = c.get("user_id")
        producto = c.get("producto") or ""
        link = c.get("link") or ""
        precio_max = c.get("precio_max") or 0
        frecuencia = c.get("frecuencia") or ""
        plan = (c.get("plan") or "omega").lower().strip()
        last_check = c.get("last_check")

        if not caza_id or not user_id or not link:
            continue

        mins = _freq_to_minutes(frecuencia)
        mins = _clamp_minutes_by_plan(plan, mins)

        last_dt = _parse_dt(last_check)
        if now - last_dt < timedelta(minutes=mins):
            continue

        domain = _domain_from_url(link)
        print(f"🔎 Caza #{caza_id} | {producto} | max ${precio_max} | {domain} | cada {mins} min")

        try:
            resultados = hunt_offers(link, producto, precio_max)
            items_found = len(resultados) if resultados else 0
            print(f"   📊 Resultados scraper: {items_found}")

            # 🔕 Notificaciones desactivadas por ahora (alertas.py sigue en SQLite)
            # Cuando migremos scraper/alertas.py a Supabase, activamos esto:
            #
            # from scraper.alertas import notificar_oferta_encontrada
            # sent = 0
            # for oferta in resultados or []:
            #     if sent >= max_alerts_global:
            #         break
            #     link_oferta = oferta.get("link")
            #     precio = oferta.get("precio")
            #     if not link_oferta or precio is None:
            #         continue
            #     try:
            #         precio_num = float(precio)
            #     except Exception:
            #         continue
            #     if precio_num > float(precio_max):
            #         continue
            #     notificar_oferta_encontrada(user_id, oferta)
            #     sent += 1

        except Exception as e:
            print(f"⚠ Error en caza {caza_id}: {e}")

        finally:
            # Siempre actualizamos last_check para evitar loops infinitos si algo falla
            try:
                supabase.table("cazas").update(
                    {"last_check": datetime.utcnow().isoformat()}
                ).eq("id", caza_id).execute()
            except Exception as e:
                print(f"⚠ No pude actualizar last_check en caza {caza_id}: {e}")

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