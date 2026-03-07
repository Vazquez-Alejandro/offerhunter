import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from apscheduler.schedulers.background import BackgroundScheduler

from auth.supabase_client import supabase
from scraper.scraper_pro import hunt_offers  # router central actual

# Evita crear mil schedulers por los reruns de Streamlit
_scheduler = None


# =========================
# HELPERS
# =========================
def _domain_from_url(url: str) -> str:
    try:
        host = urlparse(str(url)).netloc.lower().strip()
        if host.startswith("www."):
            host = host[4:]
        return host or "unknown"
    except Exception:
        return "unknown"


def _infer_source_from_url(url: str) -> str:
    d = _domain_from_url(url)

    if "mercadolibre" in d:
        return "mercadolibre"
    if "despegar" in d:
        return "despegar"
    if "fravega" in d:
        return "fravega"
    if "garbarino" in d:
        return "garbarino"
    if "tiendamia" in d:
        return "tiendamia"
    if "temu" in d:
        return "temu"
    if "tripstore" in d:
        return "tripstore"
    if "carrefour" in d:
        return "carrefour"

    return "unknown"


def _freq_to_minutes(freq: str) -> int:
    if not freq:
        return 60

    s = str(freq).strip().lower()
    s = s.replace("hs", "hora").replace("horas", "hora")
    s = s.replace("minutos", "min").replace("mins", "min")

    if "15" in s and "min" in s:
        return 15
    if "30" in s and "min" in s:
        return 30
    if "45" in s and "min" in s:
        return 45

    if "1" in s and "hora" in s:
        return 60
    if "2" in s and "hora" in s:
        return 120
    if "3" in s and "hora" in s:
        return 180
    if "4" in s and "hora" in s:
        return 240

    digits = "".join(c for c in s if c.isdigit())
    return int(digits) if digits else 60


def _parse_dt_utc(value) -> datetime | None:
    if not value:
        return None

    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(s)
        except Exception:
            return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt


def _clamp_minutes_by_plan(plan: str, mins: int) -> int:
    p = (plan or "").strip().lower()

    if p == "omega":
        return max(mins, 60)
    if p == "beta":
        return max(mins, 30)
    if p == "alfa":
        return max(mins, 15)

    return max(mins, 60)


def _safe_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _is_blocked_result(resultados) -> bool:
    if not resultados or not isinstance(resultados, list):
        return False
    first = resultados[0]
    return isinstance(first, dict) and bool(first.get("blocked"))


# =========================
# MAIN LOOP
# =========================
def vigilar_ofertas():
    print("🐺 Vigilando ofertas...")

    now = datetime.now(timezone.utc)

    res = (
        supabase.table("cazas")
        .select("id, user_id, producto, link, precio_max, frecuencia, plan, last_check, source, tipo_alerta, estado")
        .eq("estado", "activa")
        .execute()
    )
    cazas = res.data or []
    print(f"📦 Total cazas activas: {len(cazas)}")

    try:
        max_alerts_global = int(os.getenv("MAX_ALERTS_PER_RUN", "1"))
    except Exception:
        max_alerts_global = 1

    sent_global = 0
    force_run = os.getenv("FORCE_RUN", "0") == "1"

    for c in cazas:
        caza_id = c.get("id")
        user_id = c.get("user_id")
        producto = (c.get("producto") or "").strip()
        link = (c.get("link") or "").strip()
        precio_max = _safe_float(c.get("precio_max"), 0.0)
        frecuencia = c.get("frecuencia") or ""
        plan = (c.get("plan") or "omega").strip().lower()
        last_check = c.get("last_check")
        source = (c.get("source") or "").strip().lower()
        tipo_alerta = (c.get("tipo_alerta") or "piso").strip().lower()

        if not caza_id or not user_id or not link:
            continue

        mins = _freq_to_minutes(frecuencia)
        mins = _clamp_minutes_by_plan(plan, mins)

        last_dt = _parse_dt_utc(last_check)
        if (not force_run) and last_dt and (now - last_dt) < timedelta(minutes=mins):
            continue

        domain = _domain_from_url(link)
        inferred = _infer_source_from_url(link)
        inferred_or_default = inferred if inferred != "unknown" else "generic"

        if not source or source == "unknown":
            source = inferred_or_default
        else:
            if inferred != "unknown" and inferred != source:
                print(
                    f"⚠ Source mismatch en caza {caza_id}: source='{source}' pero dominio sugiere '{inferred}'. "
                    f"Usando '{inferred}'."
                )
                source = inferred
            elif source == "mercadolibre" and "mercadolibre" not in domain:
                print(
                    f"⚠ Guardrail: source='mercadolibre' pero dominio='{domain}'. "
                    f"Usando '{inferred_or_default}' para evitar scraper incorrecto."
                )
                source = inferred_or_default

        print(
            f"🔎 Caza #{caza_id} | {producto} | max ${precio_max} | "
            f"{domain} | source={source} | tipo={tipo_alerta} | cada {mins} min"
        )

        try:
            resultados = hunt_offers(link, producto, precio_max)
            items_found = len(resultados) if resultados else 0

            if _is_blocked_result(resultados):
                blocked_source = resultados[0].get("source", source)
                print(f"🧩 Fuente bloqueada para caza {caza_id}: {blocked_source}")
                items_found = 0
                resultados = []

            print(f"   📊 Resultados scraper: {items_found}")

            # =========================================================
            # ALERTAS (desactivadas por ahora)
            # Cuando quieras activarlas, este bloque ya queda preparado.
            # =========================================================
            #
            # from scraper.alertas import notificar_oferta_encontrada
            #
            # for oferta in resultados or []:
            #     if sent_global >= max_alerts_global:
            #         break
            #
            #     link_oferta = oferta.get("url") or oferta.get("link")
            #     precio = oferta.get("price") or oferta.get("precio")
            #
            #     if not link_oferta or precio is None:
            #         continue
            #
            #     try:
            #         precio_num = float(precio)
            #     except Exception:
            #         continue
            #
            #     if precio_num > float(precio_max):
            #         continue
            #
            #     notificar_oferta_encontrada(user_id, oferta)
            #     sent_global += 1

        except Exception as e:
            print(f"⚠ Error en caza {caza_id}: {e}")

        finally:
            try:
                supabase.table("cazas").update(
                    {"last_check": datetime.now(timezone.utc).isoformat()}
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
    _scheduler.add_job(
        vigilar_ofertas,
        "interval",
        minutes=1,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()

    print("🚀 Motor OfferHunter iniciado (tick 1 min, frecuencia por caza)")


if __name__ == "__main__":
    start_engine(run_once=True)