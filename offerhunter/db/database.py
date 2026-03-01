from __future__ import annotations

from urllib.parse import urlparse

from auth.supabase_client import supabase
from config import PLAN_LIMITS


def _infer_source_from_url(url: str) -> str:
    try:
        host = urlparse(str(url)).netloc.lower().strip()
        if host.startswith("www."):
            host = host[4:]
    except Exception:
        host = ""

    if "mercadolibre" in host:
        return "mercadolibre"
    if "fravega" in host:
        return "fravega"
    if "garbarino" in host:
        return "garbarino"
    if "tiendamia" in host:
        return "tiendamia"
    if "temu" in host:
        return "temu"
    if "tripstore" in host:
        return "tripstore"
    return "unknown"


def guardar_caza(user_id, producto, url, precio_max, frecuencia, tipo_alerta, plan, source=None):
    """Guarda una caza en Supabase (tabla public.cazas) respetando límites por plan.

    Devuelve:
      - True si guardó
      - "limite" si alcanzó el límite del plan
      - False si error
    """
    try:
        if not user_id:
            return False

        plan = (plan or "omega").strip().lower()
        estado = "activa"

        # fuente: si no viene explícita, inferimos por URL
        source = (source or "").strip().lower()
        if not source or source == "unknown":
            source = _infer_source_from_url(url)

        # Límite por plan
        limite = PLAN_LIMITS.get(plan, 2)

        count_res = (
            supabase.table("cazas")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("estado", "activa")
            .execute()
        )
        activas = int(getattr(count_res, "count", 0) or 0)
        if activas >= limite:
            return "limite"

        payload = {
            "user_id": user_id,
            "producto": (producto or "").strip(),
            "link": (url or "").strip(),
            "precio_max": precio_max,
            "frecuencia": (frecuencia or "").strip(),
            "tipo_alerta": (tipo_alerta or "piso").strip().lower(),
            "plan": plan,
            "estado": estado,
            "source": source,
            "last_check": None,
        }

        ins = supabase.table("cazas").insert(payload).execute()
        return True if getattr(ins, "data", None) else False

    except Exception as e:
        print("[guardar_caza] error:", e)
        return False


def obtener_cazas(user_id: str, plan: str):
    """Trae las cazas del usuario desde Supabase."""
    if not user_id:
        return []

    try:
        res = (
            supabase.table("cazas")
            .select("id, producto, link, precio_max, frecuencia, plan, estado, source, tipo_alerta, created_at, last_check")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return getattr(res, "data", None) or []
    except Exception as e:
        print("[obtener_cazas] error:", e)
        return []