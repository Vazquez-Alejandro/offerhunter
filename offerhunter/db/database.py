from auth.supabase_client import supabase
from config import PLAN_LIMITS

DEFAULT_SOURCE = "mercadolibre"

def guardar_caza(user_id, producto, url, precio_max, frecuencia, tipo_alerta, plan, source=DEFAULT_SOURCE):
    try:
        if not user_id:
            return False

        plan = (plan or "omega").strip().lower()
        estado = "activa"
        source = (source or DEFAULT_SOURCE).strip().lower()

        limite = PLAN_LIMITS.get(plan, 2)

        count_res = (
            supabase
            .table("cazas")
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
    if not user_id:
        return []
    try:
        res = (
            supabase
            .table("cazas")
            .select("id, producto, link, precio_max, frecuencia, plan, estado, source, created_at, last_check")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return getattr(res, "data", None) or []
    except Exception as e:
        print("[obtener_cazas] error:", e)
        return []
