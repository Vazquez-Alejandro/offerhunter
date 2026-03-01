import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from apscheduler.schedulers.background import BackgroundScheduler

from auth.supabase_client import supabase

# Scraper actual (MercadoLibre)
from scraper.scraper_pro import hunt_offers as hunt_offers_ml
from scraper.generic import hunt_offers_generic

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


def _infer_source_from_url(url: str) -> str:
    """
    Fallback por dominio (por si el usuario eligió mal la fuente).
    Devuelve un "source" canónico o 'unknown'.
    """
    d = _domain_from_url(url)

    if "mercadolibre" in d:
        return "mercadolibre"
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


def _parse_dt_utc(value) -> datetime | None:
    """
    Supabase suele devolver ISO string (a veces con Z o +00:00) o datetime.
    Retorna datetime timezone-aware en UTC, o None si no hay/parsea.
    """
    if not value:
        return None

    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip()
        # normalizar Z a offset explícito
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(s)
        except Exception:
            return None

    # si viene naive, asumimos UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt


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


def _safe_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


# =========================
# SCRAPER ROUTER
# =========================
def _scrape_by_source(source: str, link: str, producto: str, precio_max: float, tipo_alerta: str):
    """
    Devuelve lista de ofertas o lanza excepción controlada si no soportado.
    Hoy solo soportamos MercadoLibre con hunt_offers_ml.
    """
    source = (source or "").strip().lower()
    tipo_alerta = (tipo_alerta or "piso").strip().lower()

    SCRAPER_BY_SOURCE = {
        "mercadolibre": hunt_offers_ml,
        "generic": hunt_offers_generic,
    }
    fn = SCRAPER_BY_SOURCE.get(source)

    # Si no hay scraper específico, usar generic
    if not fn:
        fn = SCRAPER_BY_SOURCE.get("generic")

    if not fn:
        raise ValueError("Tienda no soportada todavía, estamos trabajando en ello.")

    # Firma actual: hunt_offers(link, producto, precio_max)
    # Si en el futuro necesitás tipo_alerta, lo pasás cuando el scraper lo soporte.
    return fn(link, producto, precio_max)


# =========================
# MAIN LOOP
# =========================
def vigilar_ofertas():
    print("🐺 Vigilando ofertas...")

    # IMPORTANTE: usar datetime aware en UTC (evita naive/aware mismatch)
    now = datetime.now(timezone.utc)

    # Traer cazas activas desde Supabase
    res = (
        supabase
        .table("cazas")
        .select("id, user_id, producto, link, precio_max, frecuencia, plan, last_check, source, tipo_alerta")
        .eq("estado", "activa")
        .execute()
    )
    cazas = res.data or []
    print(f"📦 Total cazas activas: {len(cazas)}")

    # Tope anti-spam por corrida (cuando actives notificaciones)
    try:
        max_alerts_global = int(os.getenv("MAX_ALERTS_PER_RUN", "1"))
    except Exception:
        max_alerts_global = 1

    for c in cazas:
        caza_id = c.get("id")
        user_id = c.get("user_id")
        producto = (c.get("producto") or "").strip()
        link = (c.get("link") or "").strip()
        precio_max = _safe_float(c.get("precio_max"), 0.0)
        frecuencia = c.get("frecuencia") or ""
        plan = (c.get("plan") or "omega").lower().strip()
        last_check = c.get("last_check")

        source = (c.get("source") or "").strip().lower()
        tipo_alerta = (c.get("tipo_alerta") or "piso").strip().lower()

        if not caza_id or not user_id or not link:
            continue

        mins = _freq_to_minutes(frecuencia)
        mins = _clamp_minutes_by_plan(plan, mins)

        last_dt = _parse_dt_utc(last_check)
        if last_dt and (now - last_dt) < timedelta(minutes=mins):
            continue

        domain = _domain_from_url(link)

        # ---------
        # ROUTING PROFESIONAL (guardrails)
        # ---------
        inferred = _infer_source_from_url(link)

        # Si no pudimos inferir, marcamos como unsupported para evitar ejecutar ML por error
        inferred_or_unsupported = inferred if inferred != "unknown" else "generic"

        # 1) Si source viene vacío/unknown -> usar inferred (o unsupported)
        if not source or source == "unknown":
            source = inferred_or_unsupported

        # 2) Si source no coincide con el dominio inferido:
        #    - si inferred es conocido => priorizar inferred
        #    - si inferred es unknown => NO ejecutar ML si el dominio no es ML
        else:
            if inferred != "unknown" and inferred != source:
                print(
                    f"⚠ Source mismatch en caza {caza_id}: source='{source}' pero dominio sugiere '{inferred}'. Usando '{inferred}'."
                )
                source = inferred
            elif source == "mercadolibre" and "mercadolibre" not in domain:
                # Guardrail clave: NUNCA correr scraper ML fuera de ML
                print(
                    f"⚠ Guardrail: source='mercadolibre' pero dominio='{domain}'. Marcando como '{inferred_or_unsupported}' para evitar timeout."
                )
                source = inferred_or_unsupported

        print(
            f"🔎 Caza #{caza_id} | {producto} | max ${precio_max} | {domain} | source={source} | tipo={tipo_alerta} | cada {mins} min"
        )

        try:
            if source == "mercadolibre" and "mercadolibre" not in domain:
                source = inferred if inferred != "unknown" else "generic"

            resultados = _scrape_by_source(source, link, producto, precio_max, tipo_alerta)
            items_found = len(resultados) if resultados else 0
            print(f"   📊 Resultados scraper: {items_found}")

            # 🔕 Notificaciones desactivadas por ahora (alertas.py sigue en SQLite)
            # Cuando migremos alertas a Supabase, activamos aquí.

        except ValueError as ve:
            # Tienda no soportada
            print(f"🚫 {ve} | caza {caza_id} | {link}")

        except Exception as e:
            print(f"⚠ Error en caza {caza_id}: {e}")

        finally:
            # Siempre actualizamos last_check para evitar loops infinitos si algo falla
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
    _scheduler.add_job(vigilar_ofertas, "interval", minutes=1, max_instances=1, coalesce=True)
    _scheduler.start()

    print("🚀 Motor OfferHunter iniciado (tick 1 min, frecuencia por caza)")


if __name__ == "__main__":
    start_engine(run_once=True)