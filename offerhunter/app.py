import os
import sys
import base64
import subprocess
from urllib.parse import urlparse

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from auth.auth_supabase import supa_signup, supa_login, supa_reset_password
from auth.supabase_client import supabase
from db.database import obtener_cazas  # tu función local de lectura (ya la usás)

# OJO: tu config hoy tiene PLAN_LIMITS como int por plan.
# Este app.py es compatible con eso, y también con PLAN_LIMITS dict.
from config import PLAN_LIMITS

load_dotenv()
DEBUG = os.getenv("DEBUG", "0") == "1"

BASE_DIR = os.path.dirname(__file__)
WOLF_PATH = os.path.join(BASE_DIR, "assets", "wolf.mp3")
LOGO_PATH = os.path.join(BASE_DIR, "assets", "img", "logo.png")
DEFAULT_SOURCE = "mercadolibre"


# -----------------------------
# Helpers: dominio / source
# -----------------------------
def domain_from_url(url: str) -> str:
    try:
        host = urlparse(str(url)).netloc.lower().strip()
        if host.startswith("www."):
            host = host[4:]
        return host or "unknown"
    except Exception:
        return "unknown"


def infer_source_from_url(url: str) -> str:
    d = domain_from_url(url)
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


# -----------------------------
# Plan limits (compat)
# -----------------------------
def get_plan_limits(plan: str) -> dict:
    """
    Compatible con:
    - PLAN_LIMITS = {"omega": 2, "beta": 5, "alfa": 10}
    - PLAN_LIMITS = {"trial": {...}, "revendedor": {...}, "empresa": {...}}
    """
    plan = (plan or "omega").strip().lower()

    raw = PLAN_LIMITS.get(plan)
    # Si no existe el plan, fallback a "omega" o primer plan del dict
    if raw is None:
        raw = PLAN_LIMITS.get("omega", None)
        if raw is None and isinstance(PLAN_LIMITS, dict) and PLAN_LIMITS:
            raw = next(iter(PLAN_LIMITS.values()))

    # Caso numérico (tu config actual)
    if isinstance(raw, (int, float)):
        max_cazas = int(raw)
        # Frecuencias default por plan viejo
        if plan == "alfa":
            freq_options = ["15 min", "30 min", "45 min", "1 h"]
        elif plan == "beta":
            freq_options = ["30 min", "1 h", "1.5 h", "2 h", "2.5 h"]
        else:
            freq_options = ["1 h", "2 h", "3 h", "4 h"]

        return {
            "max_cazas_activas": max_cazas,
            "freq_options": freq_options,
            "features": {},
            "stores": ["mercadolibre", "generic"],
        }

    # Caso dict (nuevo modelo)
    if isinstance(raw, dict):
        max_cazas = int(raw.get("max_cazas_activas", 2))
        freq_options = raw.get("freq_options") or ["1 h", "2 h", "4 h", "12 h"]
        features = raw.get("features") or {}
        stores = raw.get("stores") or ["mercadolibre", "generic"]
        return {
            "max_cazas_activas": max_cazas,
            "freq_options": freq_options,
            "features": features,
            "stores": stores,
        }

    # Fallback ultra seguro
    return {
        "max_cazas_activas": 2,
        "freq_options": ["1 h", "2 h", "3 h", "4 h"],
        "features": {},
        "stores": ["mercadolibre", "generic"],
    }


import time

def contar_cazas_activas(user_id: str) -> int:
    if not user_id:
        return 0

    for attempt in range(2):
        try:
            res = (
                supabase.table("cazas")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .eq("estado", "activa")
                .execute()
            )
            return int(res.count or 0)
        except Exception as e:
            if attempt == 0:
                time.sleep(0.5)
                continue
            print("[contar_cazas_activas] error:", e)
            return 0

def normalize_plan(plan: str) -> str:
    return (plan or "omega").strip().lower()


import re

def parse_price_to_int(value) -> int:
    """
    Convierte precios a int de forma robusta.
    Acepta: int, float, None, "$ 1.234.567", "1.234.567", "1200000.0", "1,200,000"
    """
    if value is None:
        return 0

    # Si ya es número
    if isinstance(value, (int,)):
        return int(value)

    if isinstance(value, (float,)):
        # 1200000.0 -> 1200000
        return int(value)

    s = str(value).strip()
    if not s:
        return 0

    # Caso típico: "1200000.0" (string de float)
    # Si hay un punto decimal final corto, cortamos antes del punto.
    if re.fullmatch(r"\d+\.\d{1,2}", s):
        s = s.split(".", 1)[0]

    # Dejamos solo dígitos
    digits = re.sub(r"[^\d]", "", s)
    if not digits:
        return 0

    try:
        return int(digits)
    except Exception:
        return 0


# -----------------------------
# Supabase profile
# -----------------------------
def get_user_profile(user_id: str | None):
    if not user_id:
        return {}
    try:
        res = (
            supabase.table("profiles")
            .select("plan, role, username, email")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else {}
    except Exception as e:
        print("[get_user_profile] error:", e)
        return {}


# -----------------------------
# Guardar caza (Supabase)
# -----------------------------
def guardar_caza_supabase(
    user_id: str,
    producto: str,
    url: str,
    precio_max,
    frecuencia: str,
    tipo_alerta: str,
    plan: str,
    source: str | None = None,
):
    """
    Guarda una caza en Supabase (tabla public.cazas) respetando límites por plan.

    Devuelve:
      - True si guardó
      - "limite" si alcanzó el límite del plan
      - False si error
    """
    try:
        if not user_id:
            return False

        plan = normalize_plan(plan)
        source = normalize_plan(source or DEFAULT_SOURCE)

        limits = get_plan_limits(plan)
        max_cazas = int(limits["max_cazas_activas"])

        activas = contar_cazas_activas(user_id)
        if activas >= max_cazas:
            return "limite"

        precio_int = parse_price_to_int(precio_max)
        print("DEBUG guardar_caza_supabase raw precio_max:", repr(precio_max), type(precio_max))
        print("DEBUG guardar_caza_supabase parsed precio_int:", precio_int, type(precio_int))

        payload = {
            "user_id": user_id,
            "producto": (producto or "").strip(),
            "link": (url or "").strip(),
            "precio_max": precio_int,
            "frecuencia": (frecuencia or "").strip(),
            "tipo_alerta": (tipo_alerta or "piso").strip().lower(),
            "plan": plan,
            "estado": "activa",
            "source": source,
            "last_check": None,
        }
        print("DEBUG payload precio_max:", payload["precio_max"], type(payload["precio_max"]))
        ins = supabase.table("cazas").insert(payload).execute()
        return True if getattr(ins, "data", None) else False

    except Exception as e:
        print("[guardar_caza_supabase] error:", e)
        return False


# -----------------------------
# UI helpers
# -----------------------------
def get_base64_logo(path: str) -> str:
    try:
        with open(path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except Exception:
        return ""


def play_wolf_sound():
    try:
        with open(WOLF_PATH, "rb") as f:
            audio_bytes = f.read()
        b64 = base64.b64encode(audio_bytes).decode()
        # tick para forzar re-render del html
        tick = int(st.session_state.get("sound_tick", 0))
        components.html(
            f"""
            <audio autoplay="true" style="display:none" id="wolf_{tick}">
              <source src="data:audio/mp3;base64,{b64}" type="audio/mp3" />
            </audio>
            """,
            height=0,
        )
    except Exception:
        pass


# -----------------------------
# Streamlit config
# -----------------------------
st.set_page_config(page_title="OfferHunter", layout="wide", page_icon="🐺")

if "busquedas" not in st.session_state:
    st.session_state["busquedas"] = []
if "forms_extra" not in st.session_state:
    st.session_state["forms_extra"] = 0
if "ws_vinculado" not in st.session_state:
    st.session_state["ws_vinculado"] = False
if "sound_enabled" not in st.session_state:
    st.session_state["sound_enabled"] = True
if "sound_tick" not in st.session_state:
    st.session_state["sound_tick"] = 0


# -----------------------------
# Password recovery (Supabase callback)
# -----------------------------
params = st.query_params
access_token = params.get("access_token", None)
refresh_token = params.get("refresh_token", None)
type_param = params.get("type", None)

if type_param == "recovery" and access_token:
    st.title("🔑 Restablecer contraseña")
    new_pass = st.text_input("Nueva contraseña", type="password")
    new_pass2 = st.text_input("Repetir nueva contraseña", type="password")

    if st.button("Guardar nueva contraseña"):
        if not new_pass or len(new_pass) < 6:
            st.error("La contraseña debe tener al menos 6 caracteres.")
            st.stop()
        if new_pass != new_pass2:
            st.error("Las contraseñas no coinciden.")
            st.stop()
        try:
            supabase.auth.set_session(
                {
                    "access_token": access_token,
                    "refresh_token": refresh_token or "",
                }
            )
            supabase.auth.update_user({"password": new_pass})
            st.success("✅ Contraseña actualizada. Ya podés iniciar sesión.")
            st.stop()
        except Exception as e:
            st.error(f"Error actualizando contraseña: {e}")
            st.stop()


# -----------------------------
# Auth / Login / Register
# -----------------------------
if "user_logged" not in st.session_state:
    logo_b64 = get_base64_logo(LOGO_PATH)

    st.markdown(
        f"""
        <div style="display:flex;justify-content:center;margin-top:36px;margin-bottom:20px;">
          <div style="
                width:190px;
                height:190px;
                border-radius:50%;
                overflow:hidden;
                display:flex;
                align-items:center;
                justify-content:center;
                background:#ffffff;
                border:12px solid #050505;
                box-shadow:
                    0 0 0 6px rgba(255,255,255,0.05),
                    0 0 26px rgba(255,255,255,0.22),
                    0 0 70px rgba(255,255,255,0.14),
                    0 0 120px rgba(255,255,255,0.08);
          ">
            <img src="data:image/png;base64,{logo_b64}" style="width:100%;height:100%;object-fit:cover;display:block;transform:scale(1.02);" />
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    t1, t2 = st.tabs(["🔐 Iniciar Sesión", "🐾 Unirse a la Jauría"])

    with t1:
        _, col_main, _ = st.columns([1.25, 1.5, 1.25])
        with col_main:
            u = st.text_input("Usuario o Email", key="l_u")
            p = st.text_input("Contraseña", type="password", key="l_p")

            if st.button("Entrar", use_container_width=True, type="primary", key="l_submit"):
                user, err = supa_login(u, p)
                if user:
                    st.session_state["user_logged"] = user
                    st.rerun()
                else:
                    st.error(f"❌ {err}")

            if st.button("Olvidé mi contraseña", use_container_width=True, key="l_reset"):
                if "@" in (u or ""):
                    ok = supa_reset_password(u)
                    if ok:
                        st.success("📩 Te enviamos un email para restablecer la contraseña.")
                    else:
                        st.error("No se pudo enviar el email.")
                else:
                    st.warning("Ingresá tu EMAIL arriba para restablecer la contraseña.")

    with t2:
        if "plan_elegido" not in st.session_state:
            st.subheader("Elegí tu rango en la manada")

            c1, c2, c3 = st.columns(3, gap="large")
            with c1:
                st.markdown(
                    """
                    ### Omega
                    $5 / mes

                    * ✅ 2 búsquedas activas
                    * ✅ Alertas por precio piso
                    * ✅ Notificaciones básicas
                    """,
                    unsafe_allow_html=True,
                )
                if st.button("Elegir Omega", use_container_width=True, key="choose_omega"):
                    st.session_state["plan_elegido"] = "omega"
                    st.rerun()

            with c2:
                st.markdown(
                    """
                    ### Beta
                    $10 / mes

                    * ✅ 5 búsquedas activas
                    * ✅ Alertas precio y %
                    * ✅ Email y WhatsApp
                    * ✅ Historial de cazas
                    """,
                    unsafe_allow_html=True,
                )
                if st.button("Elegir Beta", use_container_width=True, key="choose_beta"):
                    st.session_state["plan_elegido"] = "beta"
                    st.rerun()

            with c3:
                st.markdown(
                    """
                    ### Alfa
                    $15 / mes

                    * ✅ 10 búsquedas activas
                    * ✅ Tiempo real 24/7
                    * ✅ Comparador dinámico
                    """,
                    unsafe_allow_html=True,
                )
                if st.button("Elegir Alfa", use_container_width=True, key="choose_alfa"):
                    st.session_state["plan_elegido"] = "alfa"
                    st.rerun()

        else:
            _, col_main, _ = st.columns([1.25, 1.5, 1.25])
            with col_main:
                plan = st.session_state["plan_elegido"]
                st.info(f"Registrando nuevo miembro · Rango {plan.capitalize()}")

                nu = st.text_input("Usuario", key="r_user")
                em = st.text_input("Email", key="r_email")
                np = st.text_input("Contraseña", type="password", key="r_pass")

                if st.button("Finalizar Registro", use_container_width=True, key="r_submit"):
                    user, err = supa_signup(em, np, nu, plan)
                    if user:
                        st.success("✅ Cuenta creada. Revisá tu email para confirmar.")
                        st.stop()
                    else:
                        st.error(f"❌ {err}")

    st.stop()

# -----------------------------
# Main panel
# -----------------------------
user = st.session_state["user_logged"]
email = (getattr(user, "email", None) or "").strip()
user_id = getattr(user, "id", None)

if not user_id:
    st.session_state.pop("user_logged", None)
    st.warning("⚠ Tu sesión no es válida. Volvé a iniciar sesión.")
    st.rerun()

profile = get_user_profile(user_id)
plan_real = normalize_plan(profile.get("plan") or "omega")
role = normalize_plan(profile.get("role") or "user")
nick = (profile.get("username") or "").strip()

display_name = nick if nick else (email.split("@")[0] if "@" in email else "usuario")
es_admin = role == "admin"
plan_vista = plan_real  # puede ser simulado por admin


# Sidebar
with st.sidebar:
    st.markdown("### Utilidades")

    st.session_state["sound_enabled"] = st.checkbox(
        "🔊 Sonido del lobo",
        value=st.session_state["sound_enabled"],
    )

    if st.button("🧩 Conectar MercadoLibre (resolver captcha/login)", use_container_width=True):
        try:
            proc = subprocess.run(
                [sys.executable, "scripts/ml_connect.py"],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode == 0:
                st.success("✅ Sesión de MercadoLibre guardada/actualizada.")
            else:
                st.error("❌ No se pudo guardar la sesión de MercadoLibre.")
            if (proc.stdout or "").strip():
                st.code(proc.stdout.strip())
            if (proc.stderr or "").strip():
                st.code(proc.stderr.strip())
        except Exception as e:
            st.error(f"Error ejecutando ml_connect.py: {e}")

    st.divider()
    st.subheader("👤 Sesión")
    st.caption(f"Usuario: `{display_name}`")
    st.caption(f"Plan real: **{plan_real.capitalize()}**")

    if es_admin:
        st.divider()
        st.subheader("🛠️ Panel de Admin")

        if st.button("🔄 Refrescar panel", use_container_width=True):
            st.rerun()

        # Mantengo simulación de planes vieja (omega/beta/alfa) porque tu config hoy es esa
        plan_simulado = st.radio(
            "Simular vista de rango:",
            ["Omega", "Beta", "Alfa"],
            index=2 if plan_real == "alfa" else (1 if plan_real == "beta" else 0),
            key="admin_plan_sim",
        )
        plan_vista = plan_simulado.lower()
        st.info(f"Viendo como: {plan_simulado}")

        st.divider()
        st.subheader("👥 Usuarios (últimos 30)")
        try:
            res = (
                supabase.table("profiles")
                .select("user_id, username, email, plan, role, created_at")
                .order("created_at", desc=True)
                .limit(30)
                .execute()
            )
            rows = res.data or []
            if not rows:
                st.caption("No hay usuarios.")
            else:
                st.dataframe(rows, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Error cargando usuarios: {e}")


# A partir de acá, usamos plan_vista para límites/UI
plan = plan_vista

# cargar búsquedas
st.session_state["busquedas"] = obtener_cazas(user_id, plan)

st.title(f"Panel de {display_name} · Plan {plan.capitalize()}")

limits = get_plan_limits(plan)
limite_plan = int(limits["max_cazas_activas"])
cazas_activas = contar_cazas_activas(user_id)
restantes = limite_plan - cazas_activas

col1, col2 = st.columns(2)
with col1:
    st.info(f"📦 Estás usando {cazas_activas} de {limite_plan} cazas disponibles.")
with col2:
    if restantes > 0:
        st.success(f"✅ Te quedan {restantes} disponibles.")
    else:
        st.warning("⚠️ Has alcanzado el límite de tu plan.")


# Frecuencias segun plan (desde limits)
freq_options = limits["freq_options"]

# WhatsApp (solo beta/alfa en tu modelo actual)
if plan in ["alfa", "beta"]:
    with st.expander("📲 Sincronizar WhatsApp", expanded=not st.session_state.get("ws_vinculado", False)):
        if not st.session_state["ws_vinculado"]:
            link_wa = "https://wa.me/5491100000000?text=Vincular%20Cuenta"
            st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={link_wa}")
            if st.button("Confirmar Vinculación ✅"):
                st.session_state["ws_vinculado"] = True
                st.rerun()
        else:
            st.success("✅ WhatsApp Activo")


# -----------------------------
# Crear nueva caza
# -----------------------------
total_ocupado = len(st.session_state["busquedas"])
if total_ocupado < limite_plan:
    with st.expander("➕ Configurar nueva cacería"):
        n_url = st.text_input("URL")
        n_key = st.text_input("Palabra clave")

        tipo_alerta_ui = st.radio("Estrategia:", ["Precio Piso", "Descuento %"], horizontal=True)
        if tipo_alerta_ui == "Precio Piso":
            n_price = st.number_input(
                "Precio Máximo ($)",
                min_value=0,
                value=500000,
                step=1000,
                key="price_piso",
            )
            tipo_db = "piso"
        else:
            n_price = st.slider("Porcentaje deseado (%)", 5, 90, 35, key="price_desc")
            tipo_db = "descuento"

        n_freq = st.selectbox("Frecuencia", freq_options)

        if DEBUG:
            st.caption(f"DEBUG UI | tipo_db={tipo_db} | n_price={n_price} | type={type(n_price)}")

        if st.button("Lanzar", use_container_width=True):
            if not n_url.strip():
                st.error("Ingresá una URL.")
                st.stop()
            if not n_key.strip():
                st.error("Ingresá una palabra clave.")
                st.stop()

            precio_max = parse_price_to_int(n_price)

            if DEBUG:
                st.info(
                    f"DEBUG LANZAR | user_id={user_id} | tipo_db={tipo_db} | "
                    f"precio_max={precio_max} | freq={n_freq} | plan={plan}"
                )

            if tipo_db == "piso" and precio_max <= 0:
                st.error("El precio máximo debe ser mayor a 0.")
                st.stop()

            src = infer_source_from_url(n_url)
            if src == "unknown":
                src = DEFAULT_SOURCE

            resultado = guardar_caza_supabase(
                user_id=user_id,
                producto=n_key,
                url=n_url,
                precio_max=precio_max,
                frecuencia=n_freq,
                tipo_alerta=tipo_db,
                plan=plan,
                source=src,
            )

            if resultado is True:
                # refrescar lista desde DB para no quedar con session_state viejo
                try:
                    from db.database import obtener_cazas  # o el import que ya uses
                    st.session_state["busquedas"] = obtener_cazas(st.session_state.get("user_id"), plan) or []
                except Exception as e:
                    print("DEBUG refresh busquedas error:", e)

                st.success("✅ Caza guardada")
                st.rerun()           

            if resultado is True:
                st.success("✅ Caza lanzada")
                st.rerun()
            elif resultado == "limite":
                st.warning("⚠️ Alcanzaste el límite de tu plan.")
            else:
                st.error("❌ Error al guardar la caza.")
else:
    st.warning(f"Has alcanzado el límite de {limite_plan} búsquedas de tu plan {plan.capitalize()}.")


# -----------------------------
# Listado de búsquedas + Olfatear
# -----------------------------
status_slot = st.empty()

# Mensaje persistente del último olfateo
last = st.session_state.get("last_updated_rid")
if last is not None:
    last = str(last)  # ✅ esto es lo nuevo
    n = len(st.session_state.get(f"last_res_{last}", []))
    status_slot.success(f"✅ Última búsqueda: {n} resultados")
    st.session_state["last_updated_rid"] = None

if st.session_state["busquedas"]:
    st.subheader(f"Mis Cacerías ({plan.capitalize()})")

    for i, b in enumerate(st.session_state["busquedas"]):
        rid = str(b.get("id", i))

        with st.container(border=True):
            col_info, col_btns = st.columns([3, 1])

            # Info
            with col_info:
                precio_meta = b.get("precio_max", 0)
                tipo = (b.get("tipo_alerta") or "piso").strip().lower()

                if tipo == "piso":
                    try:
                        label_precio = f"Máx: ${int(precio_meta):,}".replace(",", ".")
                    except Exception:
                        label_precio = f"Máx: ${precio_meta}"
                else:
                    label_precio = f"Objetivo: {precio_meta}% desc."

                kw = (
                    b.get("keyword")
                    or b.get("producto")
                    or b.get("palabra_clave")
                    or b.get("palabra clave")
                    or ""
                )
                st.markdown(f"**🐺 {kw}** ({tipo.capitalize()})")

                url = b.get("url") or b.get("link") or ""
                st.caption(f"🔗 {url}")
                st.write(f"🎯 {label_precio} | ⏱️ {b.get('frecuencia', '')}")

            # Botones
            with col_btns:
                if st.button("Olfatear 👃", key=f"olf_{rid}", use_container_width=True):
                    with st.spinner("Rastreando..."):
                        kw2 = b.get("keyword") or b.get("producto") or ""
                        url2 = b.get("url") or b.get("link") or ""
                        precio2 = parse_price_to_int(b.get("precio_max"))

                        try:
                            host = domain_from_url(url2)

                            # -----------------------------
                            # MERCADOLIBRE
                            # -----------------------------
                            if "mercadolibre" in host:
                                from scraper.scraper_pro import hunt_offers

                                resultados = hunt_offers(url2, kw2, precio2) or []

                                if not resultados:
                                    st.info(
                                        "MercadoLibre está bloqueando búsquedas automatizadas desde esta red (captcha/403). "
                                        "Por ahora probá con tiendas genéricas."
                                    )

                            # -----------------------------
                            # DESPEGAR
                            # -----------------------------
                            elif "despegar" in host:
                                from scraper.scraper_pro import hunt_offers

                                resultados = hunt_offers(url2, kw2, precio2) or []

                                if resultados and resultados[0].get("blocked"):
                                    st.info(
                                        "✈️ Despegar está bloqueando búsquedas automáticas desde esta red.\n\n"
                                        "La detección funciona correctamente. Más adelante se resolverá "
                                        "con una estrategia especial para vuelos."
                                    )
                                    resultados = []

                            # -----------------------------
                            # GENERIC STORES
                            # -----------------------------
                            else:
                                from scraper.generic import hunt_offers_generic
                                resultados = hunt_offers_generic(url2, kw2, precio2)

                        except Exception as e:
                            st.warning(f"Error al rastrear: {e}")
                            resultados = []

                        st.session_state[f"last_res_{rid}"] = resultados or []
                        st.session_state["last_updated_rid"] = rid
                        status_slot.success(f"✅ Última búsqueda: {len(resultados)} resultados")

                        if resultados and st.session_state.get("sound_enabled", True):
                            st.session_state["sound_tick"] += 1
                            st.session_state["play_sound"] = True

                        # st.rerun()

                if st.button("🗑️ Eliminar", key=f"del_{rid}", use_container_width=True):
                    try:
                        supabase.table("cazas").delete().eq("id", b["id"]).eq("user_id", user_id).execute()
                        # refresco local
                        st.session_state["busquedas"] = [
                            x for x in st.session_state["busquedas"] if str(x.get("id")) != str(b.get("id"))
                        ]
                        st.session_state.pop(f"last_res_{rid}", None)
                        status_slot.info("🧹 Caza eliminada")
                    except Exception as e:
                        st.error(f"Error eliminando caza: {e}")

             
                # Resultados
                res = st.session_state.get(f"last_res_{rid}", []) or []

                if res:
                    seen = set()
                    uniq = []

                    for item in res:
                        key = (
                            str(item.get("url") or item.get("link") or ""),
                            str(item.get("title") or item.get("titulo") or ""),
                            str(item.get("price") or item.get("precio") or ""),
                        )
                        if key in seen:
                            continue
                        seen.add(key)
                        uniq.append(item)

                    res = uniq

                # ordenar por precio ascendente
                def _safe_price(x):
                    try:
                        return int(x.get("price") or x.get("precio") or 999999999)
                    except Exception:
                        return 999999999

                res = sorted(res, key=_safe_price)                    

                with st.expander(f"✅ Resultados ({len(res)})", expanded=True):
                    for r in res[:5]:
                        c1, c2 = st.columns([3, 1])

                        with c1:
                            titulo = " ".join(str(r.get("title") or r.get("titulo") or "").split())
                            if len(titulo) > 90:
                                titulo = titulo[:87] + "…"
                            st.write(titulo)

                            precio = r.get("price") or r.get("precio") or 0
                            try:
                                st.caption(f"${int(precio):,}".replace(",", "."))
                            except Exception:
                                st.caption(f"${precio}")

                        with c2:
                            link = r.get("url") or r.get("link") or ""
                            if link:
                                st.link_button("Ver", link, width="stretch")
                            else:
                                st.button("Sin link", disabled=True, width="stretch")

# Sonido (al final, mismo rerun)
if st.session_state.get("play_sound"):
    play_wolf_sound()
    st.session_state["play_sound"] = False
else:
    if not st.session_state["busquedas"]:
        st.info("Todavía no tenés cacerías activas. Creá una arriba para empezar a olfatear ofertas. 🐺")