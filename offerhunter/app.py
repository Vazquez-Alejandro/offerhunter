import streamlit as st
import streamlit.components.v1 as components
import base64
import requests
from bs4 import BeautifulSoup
import subprocess
import sys
import os
from auth.auth_supabase import supa_signup, supa_login, supa_reset_password
from auth.supabase_client import supabase
from db.database import obtener_cazas, guardar_caza
from config import PLAN_LIMITS


BASE_DIR = os.path.dirname(__file__)
WOLF_PATH = os.path.join(BASE_DIR, "assets", "wolf.mp3")

from dotenv import load_dotenv
load_dotenv()

DEBUG = os.getenv('DEBUG', '0') == '1'


from auth.auth_supabase import (
    supa_login,
    supa_signup,
    supa_reset_password,
)

from scraper.scraper_pro import hunt_offers as rastrear_busqueda
from engine import start_engine

from urllib.parse import urlparse

def _domain_from_url(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower().strip()
        if host.startswith("www."):
            host = host[4:]
        return host or "unknown"
    except Exception:
        return "unknown"

def _infer_source_from_url(url: str) -> str:
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

# ✅ Admin por email (seguro)

def get_user_profile(user_id: str | None):
    if not user_id:
        return {}
    res = (
        supabase
        .table("profiles")
        .select("plan, role, username")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else {}




from auth.supabase_client import supabase

DEFAULT_SOURCE = "mercadolibre"


def guardar_caza(user_id, producto, url, precio_max, frecuencia, tipo_alerta, plan, source=DEFAULT_SOURCE):
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

        # Normalizar
        plan = (plan or "omega").strip().lower()
        estado = "activa"
        source = (source or DEFAULT_SOURCE).strip().lower()

        # 1) Contar cazas activas del usuario (para límite)
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

        # 2) Insertar caza
        payload = {
            "user_id": user_id,
            "producto": (producto or "").strip(),
            "link": (url or "").strip(),
            "precio_max": precio_max,
            "frecuencia": (frecuencia or "").strip(),
            "tipo_alerta": (tipo_alerta or "piso").strip().lower(),
            "plan": plan,
            "estado": estado,
            "source": source,          # ✅ NUEVO
            "last_check": None,
        }

        ins = supabase.table("cazas").insert(payload).execute()

        return True if getattr(ins, "data", None) else False

    except Exception as e:
        print("[guardar_caza] error:", e)
        return False

# --- CONFIGURACIÓN ---
st.set_page_config(
    page_title="OfferHunter 🐺", 
    layout="wide", 
    page_icon="🐺"
)

if "busquedas" not in st.session_state:
    st.session_state["busquedas"] = []

if "forms_extra" not in st.session_state:
    st.session_state["forms_extra"] = 0   

if "ws_vinculado" not in st.session_state:
    st.session_state["ws_vinculado"] = False

def get_base64_logo(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except:
        return ""
    
# CSS extra SOLO para pantalla de login/registro
if not st.session_state.get("user_logged"):
    st.markdown("""
    <style>
      .block-container{
        max-width: 760px !important;
        padding-top: 2.2rem !important;
      }
    </style>
    """, unsafe_allow_html=True)

# --- CSS GLOBAL ---
st.markdown("""
    <style>
        .contenedor-logo { display: flex; justify-content: center; }
        .aura { width: 250px; transform: scale(0.85); -webkit-mask-image: radial-gradient(circle, black 40%, rgba(0,0,0,0) 70%); }
        .plan-card {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 25px;
            min-height: 380px;
            display: flex;
            flex-direction: column;
            transition: transform 0.3s;
        }
        .plan-card:hover {
            transform: translateY(-5px);
            border-color: #4da3ff;
        }
        .plan-title { color: #4da3ff; text-align: center; margin-bottom: 15px; }
        .plan-price { font-size: 24px; font-weight: bold; text-align: center; margin-bottom: 20px; }
        .plan-features { list-style: none; padding: 0; flex-grow: 1; }
        .plan-features li { margin-bottom: 10px; font-size: 14px; }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
.logo-wrap{
  display:flex;
  justify-content:center;
  margin: 0.5rem 0 1rem 0;
}

/* círculo blanco + difuminado */
.logo-bg{
  width: 220px;
  height: 220px;
  border-radius: 999px;
background: radial-gradient(circle,
  rgba(255,255,255,1)    0%,
  rgba(255,255,255,0.95) 40%,
  rgba(255,255,255,0.75) 60%,
  rgba(255,255,255,0.40) 75%,
  rgba(255,255,255,0.00) 90%
);
  display:flex;
  align-items:center;
  justify-content:center;
  /* un poquito de glow suave */
  filter: drop-shadow(0 12px 24px rgba(0,0,0,0.35));
}

.logo-img{
  width: 220px;
  height: auto;
  /* opcional: si el png tiene bordes feos, esto ayuda */
  border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
    <style>
    /* --- FIX cards planes cuando el contenedor es angosto --- */
        .plan-title{
        font-size: 1.15rem;
        line-height: 1.2;
        word-break: normal;
        }
        .plan-price{
        font-size: 1.15rem;
        }
        .plan-features li{
        font-size: 0.92rem;
        line-height: 1.25;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <style>
        /* Contenedor “angosto” (login/registro/tabs) */
        .narrow {
        max-width: 520px;
        margin: 0 auto;
        }

        /* Contenedor “ancho” (cards) */
        .wide {
        max-width: 1100px;
        margin: 0 auto;
        }
    </style>
""", unsafe_allow_html=True)

params = st.query_params

# --- RUTAS DE RECUPERACIÓN ---
# --- AUTH CALLBACKS (Supabase) ---
params = st.query_params

# Supabase suele volver con estos params cuando hacés reset desde el email
access_token = params.get("access_token", None)
refresh_token = params.get("refresh_token", None)
type_param = params.get("type", None)

# Si venimos de un reset de password, mostramos form para setear nueva pass
if type_param == "recovery" and access_token:
    st.title("🔐 Restablecer contraseña")

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
            # 1) Setear sesión temporal con tokens del callback
            supabase.auth.set_session({
                "access_token": access_token,
                "refresh_token": refresh_token or ""
            })

            # 2) Actualizar password
            supabase.auth.update_user({"password": new_pass})

            st.success("✅ Contraseña actualizada. Ya podés iniciar sesión.")
            st.stop()

        except Exception as e:
            st.error(f"Error actualizando contraseña: {e}")
            st.stop()

# --- LÓGICA DE ACCESO ---
if "user_logged" not in st.session_state:
    logo_b64 = get_base64_logo("assets/img/logo_clean.png")
    st.markdown(
    f"""
    <div class="logo-wrap">
      <div class="logo-bg">
        <img src="data:image/png;base64,{logo_b64}" class="logo-img">
      </div>
    </div>
    """,
    unsafe_allow_html=True
)
    
    _, col_main, _ = st.columns([1, 2, 1])
    # --- LOGIN / REGISTER ---
    t1, t2 = st.tabs(["🔑 Iniciar Sesión", "🐺 Unirse a la Jauría"])

    with t1:
        _, col_main, _ = st.columns([1, 2, 1])
        with col_main:

            u = st.text_input("Usuario o Email", key="l_u")
            p = st.text_input("Contraseña", type="password", key="l_p")

            # LOGIN
            if st.button("Entrar", width='stretch', type="primary", key="l_submit"):
                user, err = supa_login(u, p)

                if user:
                    st.session_state["user_logged"] = user
                    st.rerun()
                else:
                    st.error(f"❌ {err}")

            # RESET PASSWORD
            if st.button("Olvidé mi contraseña", width='stretch', key="l_reset"):
                if "@" in u:
                    ok = supa_reset_password(u)
                    if ok:
                        st.success("📩 Te enviamos un email para restablecer la contraseña.")
                    else:
                        st.error("No se pudo enviar el email.")
                else:
                    st.warning("Ingresá tu EMAIL arriba para restablecer la contraseña.")
    with t2:
        if "plan_elegido" not in st.session_state:
            # 🔥 Solo en la vista de planes: más ancho para que entren 3 cards
            st.markdown("""
            <style>
            .block-container{
                max-width: 1100px !important;
            }
            </style>
            """, unsafe_allow_html=True)

            st.subheader("Elegí tu rango en la manada")
            c1, c2, c3 = st.columns(3, gap="large")

            with c1:
                st.markdown("""<div class="plan-card">
                    <h3 class="plan-title">Omega 🐾</h3>
                    <p class="plan-price">$5 / mes</p>
                    <ul class="plan-features">
                        <li>✅ 2 búsquedas activas</li>
                        <li>✅ Alertas por precio piso</li>
                        <li>✅ Notificaciones básicas</li>
                    </ul></div>""", unsafe_allow_html=True)
                if st.button("Elegir Omega", width='stretch'):
                    st.session_state["plan_elegido"] = "omega"
                    st.rerun()

            with c2:
                st.markdown("""<div class="plan-card" style="border-color: #4da3ff;">
                    <h3 class="plan-title">Beta 🐺</h3>
                    <p class="plan-price">$10 / mes</p>
                    <ul class="plan-features">
                        <li>✅ 5 búsquedas activas</li>
                        <li>✅ Alertas precio y %</li>
                        <li>✅ Email y WhatsApp</li>
                        <li>✅ Historial de cazas</li>
                    </ul></div>""", unsafe_allow_html=True)
                if st.button("Elegir Beta", width='stretch'):
                    st.session_state["plan_elegido"] = "beta"
                    st.rerun()

            with c3:
                st.markdown("""<div class="plan-card" style="background: rgba(77, 163, 255, 0.1);">
                    <h3 class="plan-title">Alfa 👑</h3>
                    <p class="plan-price">$15 / mes</p>
                    <ul class="plan-features">
                        <li>✅ 10 búsquedas activas</li>
                        <li>✅ Errores de tarifa</li>
                        <li>✅ Tiempo real 24/7</li>
                        <li>✅ Comparador dinámico</li>
                    </ul></div>""", unsafe_allow_html=True)
                if st.button("Elegir Alfa", width='stretch'):
                    st.session_state["plan_elegido"] = "alfa"
                    st.rerun()

        else:
            # Registro (angosto)
            _, col_main, _ = st.columns([1, 2, 1])
            with col_main:
                st.info(f"Registrando nuevo miembro · Rango {st.session_state['plan_elegido'].capitalize()}")

                nu = st.text_input("Usuario", key="r_user")  # por ahora no se usa en Supabase Auth
                em = st.text_input("Email", key="r_email")
                np = st.text_input("Contraseña", type="password", key="r_pass")

            if st.button("Finalizar Registro", width='stretch', key="r_submit"):

                user, err = supa_signup(
                    em,
                    np,
                    nu,
                    st.session_state["plan_elegido"]
                )

                if user:
                    st.success("✅ Cuenta creada. Revisá tu email para confirmar.")
                else:
                    st.error(f"❌ {err}")

# --- PANEL PRINCIPAL ---
else:
    user = st.session_state["user_logged"]

    email = (getattr(user, "email", None) or "").strip()

    user_id = getattr(user, "id", None)
    if not user_id:
        st.session_state.pop("user_logged", None)
        st.warning("⚠ Tu sesión no es válida. Volvé a iniciar sesión.")
        st.rerun()
    profile = get_user_profile(user_id)

    plan_real = (profile.get("plan") or "omega").lower().strip()
    role = (profile.get("role") or "user").lower().strip()
    nick = (profile.get("username") or "").strip()

    display_name = nick if nick else (email.split("@")[0] if "@" in email else "usuario")

    es_admin = (role == "admin")

    # ✅ Plan "vista" (por defecto, plan real)
    plan_vista = plan_real

    # --- SIDEBAR ---
    with st.sidebar:

        st.markdown("### 🧰 Utilidades")
        # Sonido del lobo (preferencia)
        if "sound_enabled" not in st.session_state:
            st.session_state["sound_enabled"] = True
        st.session_state["sound_enabled"] = st.checkbox("🔊 Sonido del lobo", value=st.session_state["sound_enabled"])

        # Conectar MercadoLibre (captcha/login) - guarda sessions/ml_state.json
        if st.button("🔑 Conectar MercadoLibre (resolver captcha/login)"):
            try:
                # Ejecuta el script y muestra output
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
        st.subheader("🧭 Sesión")
        st.caption(f"Usuario: `{display_name}`")
        st.caption(f"Plan real: **{plan_real.capitalize()}**")

        st.divider()

        if es_admin:
            st.subheader("🛠️ Panel de Admin")

            # Botón refresh rápido (solo rerun)
            if st.button("🔄 Refrescar panel", width='stretch'):
                st.rerun()

            plan_simulado = st.radio(
                "Simular vista de rango:",
                ["Omega", "Beta", "Alfa"],
                index=2 if plan_real == "alfa" else (1 if plan_real == "beta" else 0),
                key="admin_plan_sim"
            )
            plan_vista = plan_simulado.lower()
            st.info(f"Viendo como: {plan_simulado}")

            st.divider()



# --------------------
# 👥 Usuarios (top 30)
# --------------------
            st.divider()
            st.subheader("👥 Usuarios (últimos 30)")

            try:
                from auth.supabase_client import supabase

                res = (
                    supabase
                    .table("profiles")
                    .select("user_id, username, email, plan, role, created_at")
                    .order("created_at", desc=True)
                    .limit(30)
                    .execute()
                )

                rows = res.data or []

                if not rows:
                    st.caption("No hay usuarios.")
                else:
                    st.dataframe(
                        rows,
                        width='stretch',
                        hide_index=True,
                        column_config={
                            "user_id": "ID",
                            "username": "Nick",
                            "email": "Email",
                            "plan": "Plan",
                            "role": "Rol",
                            "created_at": "Creado"
                        }
                    )

            except Exception as e:
                st.error(f"Error cargando usuarios: {e}")

    # ✅ IMPORTANTÍSIMO: de acá en adelante usá plan_vista para límites/UI
    plan = plan_vista
    user_id = getattr(user, "id", None)
    # ✅carga las búsquedas
    st.session_state.busquedas = obtener_cazas(user_id, plan)

    st.title(f"Panel de {display_name} - Plan {plan.capitalize()} 🐺")
    # --- Indicador de uso del plan ---
    from auth.supabase_client import supabase

    def contar_cazas_activas(user_id: str) -> int:
        if not user_id:
            return 0

        try:
            res = (
                supabase
                .table("cazas")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .eq("estado", "activa")
                .execute()
            )

            return int(res.count or 0)

        except Exception as e:
            print("[contar_cazas_activas] error:", e)
            return 0

    limite_plan = PLAN_LIMITS.get(plan, 2)
    cazas_activas = contar_cazas_activas(user_id)
    restantes = limite_plan - cazas_activas

    col1, col2 = st.columns(2)

    with col1:
        st.info(f"🐺 Estás usando {cazas_activas} de {limite_plan} cazas disponibles.")

    with col2:
        if restantes > 0:
            st.success(f"🔓 Te quedan {restantes} disponibles.")
        else:
            st.warning("⚠️ Has alcanzado el límite de tu plan.")

    # Configuración de límites
    if plan == "alfa":
        limit = 10
        freq_options = ["15 min", "30 min", "45 min", "1 h"]
    elif plan == "beta":
        limit = 5
        freq_options = ["30 min", "1 h", "1.5 h", "2 h", "2.5 h"]
    else:
        limit = 2
        freq_options = ["1 h", "2 h", "3 h", "4 h"]

    # --- Sección WhatsApp (Solo Alfa y Beta) ---
    if plan in ["alfa", "beta"]:
        with st.expander("📲 Sincronizar WhatsApp", expanded=not st.session_state.ws_vinculado):
            if not st.session_state.ws_vinculado:
                link_wa = "https://wa.me/5491100000000?text=Vincular%20Cuenta"
                st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={link_wa}")
                if st.button("Confirmar Vinculación ✅"):
                    st.session_state.ws_vinculado = True
                    st.rerun()
            else:
                st.success("✅ WhatsApp Activo")

    # --- Lógica de Cacerías (Respetando el límite del plan) ---
    total_ocupado = len(st.session_state.busquedas)
    
    if total_ocupado < limit:
        with st.expander("➕ Configurar nueva cacería"):
            n_url = st.text_input("URL")
            n_key = st.text_input("Palabra clave")
            
            tipo_alerta = st.radio("Estrategia:", ["Precio Piso", "Descuento %"], horizontal=True)
            
            if tipo_alerta == "Precio Piso":
                n_price = st.number_input(
                    "Precio Máximo ($)",
                    min_value=0,
                    value=500000,
                    step=1000,
                    key="price_piso"
                )
                tipo_db = "piso"
            else:
                n_price = st.slider(
                    "Porcentaje deseado (%)",
                    5, 90, 35,
                    key="price_desc"
                )
                tipo_db = "descuento"

            # ⚠️ FRECUENCIA SIEMPRE DEFINIDA ANTES DEL BOTÓN
            n_freq = st.selectbox("Frecuencia", freq_options)
            # DEBUG UI + TERMINAL (activar con DEBUG=1)
            if DEBUG:
                debug_ui = f"DEBUG UI | tipo_db={tipo_db} | n_price={n_price} | type={type(n_price)}"
                st.caption(debug_ui)
               

            if st.button("Lanzar"):
                user_id = getattr(user, "id", None)

                try:
                    precio_max = int(float(n_price))
                except Exception:
                    precio_max = 0
                if DEBUG:
                    debug_lanzar = (
                        f"DEBUG LANZAR | user_id={user_id} | tipo_db={tipo_db} | "
                        f"precio_max={precio_max} | freq={n_freq} | plan={plan}"
                    )
                    st.info(debug_lanzar)
               

                if tipo_db == "piso" and precio_max <= 0:
                    st.error("El precio máximo debe ser mayor a 0.")
                    print("ABORT: precio_max inválido para piso")
                    st.stop()

                resultado = guardar_caza(
                    user_id,
                    n_key,
                    n_url,
                    precio_max,
                    n_freq,
                    tipo_db,
                    plan
                )

                if resultado is True:
                    st.success("Caza lanzada 🐺")
                    st.rerun()
                elif resultado == "limite":
                    st.warning("⚠️ Alcanzaste el límite de tu plan.")
                else:
                    st.error("Error al guardar la caza.")
    else:
        st.warning(f"Has alcanzado el límite de {limit} búsquedas de tu plan {plan.capitalize()}.")

    # --- LISTADO DE BÚSQUEDAS ACTIVAS ---
    status_slot = st.empty()

    # Mensaje de la última búsqueda (persistente entre reruns)
    last = st.session_state.get("last_updated_rid")
    if last is not None:
        n = len(st.session_state.get(f"last_res_{last}", []))
        status_slot.success(f"✅ Última búsqueda: {n} resultados")
        st.session_state["last_updated_rid"] = None

    if st.session_state.busquedas:
        st.subheader(f"Mis Cacerías ({plan.capitalize()} 🐺)")

        for i, b in enumerate(st.session_state.busquedas):
            rid = b.get("id", i)

            with st.container(border=True):
                col_info, col_btns = st.columns([3, 1])

                # -------------------------
                # IZQUIERDA: info
                # -------------------------
                with col_info:
                    precio_meta = b.get("precio_max", 0)
                    tipo = (b.get("tipo_alerta") or "piso").strip().lower()
                    label_precio = (
                        f"Máx: ${int(precio_meta):,}"
                        if tipo == "piso"
                        else f"Objetivo: {precio_meta}% desc."
                    )

                    kw = (
                        b.get("keyword")
                        or b.get("producto")
                        or b.get("palabra_clave")
                        or b.get("palabra clave")
                        or ""
                    )

                    st.markdown(f"**🎯 {kw}** ({tipo.capitalize()})")
                    url = (b.get("url") or b.get("link") or "")
                    st.caption(f"📍 {url}")
                    st.write(f"💰 {label_precio} | ⏱️ {b.get('frecuencia','')}")

                # -------------------------
                # DERECHA: botones (solo botones)
                # -------------------------
                with col_btns:
                    if st.button("Olfatear 🐺", key=f"olf_{rid}", width="stretch"):
                        with st.spinner("Rastreando..."):
                            kw2 = b.get("keyword") or b.get("producto") or ""
                            url2 = b.get("url") or b.get("link") or ""
                            precio2 = int(b.get("precio_max") or 0)

                            try:
                                from urllib.parse import urlparse
                                host = urlparse(str(url2)).netloc.lower().strip()

                                if "mercadolibre" in host:
                                    from scraper.scraper_pro import hunt_offers as hunt_offers_ml
                                    resultados = hunt_offers_ml(url2, kw2, precio2)
                                else:
                                    from scraper.generic import hunt_offers_generic
                                    resultados = hunt_offers_generic(url2, kw2, precio2)

                            except Exception as e:
                                st.warning(f"Error al rastrear: {e}")
                                resultados = []

                            st.session_state[f"last_res_{rid}"] = resultados or []
                            st.session_state["last_updated_rid"] = rid

                            # Feedback inmediato (sin toast ni rerun)
                            status_slot.success(f"✅ Última búsqueda: {len(resultados)} resultados")

                            if resultados:
                                st.session_state["sound_tick"] = int(st.session_state.get("sound_tick", 0)) + 1

                    if st.button("🗑 Eliminar", key=f"del_{rid}", width="stretch"):
                        try:
                            from auth.supabase_client import supabase
                            supabase.table("cazas").delete().eq("id", b["id"]).eq("user_id", user_id).execute()
                        except Exception as e:
                            st.error(f"Error eliminando caza: {e}")
                        else:
                            # Refresco local sin st.rerun (evita crashes de DOM)
                            st.session_state.busquedas = [
                                x for x in st.session_state.busquedas
                                if str(x.get("id")) != str(b.get("id"))
                            ]
                            st.session_state.pop(f"last_res_{rid}", None)
                            status_slot.info("🗑 Caza eliminada")

                # -------------------------
                # RESULTADOS (debajo de columnas, full width)
                # -------------------------
                res = st.session_state.get(f"last_res_{rid}", [])
                # Dedup results by link/title to avoid repeated cards
                if res:
                    seen = set()
                    uniq = []
                    for item in res:
                        key = (str(item.get('link') or ''), str(item.get('titulo') or ''), str(item.get('precio') or ''))
                        if key in seen:
                            continue
                        seen.add(key)
                        uniq.append(item)
                    res = uniq
                if res:
                    with st.expander(f"✅ Resultados ({len(res)})", expanded=True):
                        for r in res[:10]:
                            c1, c2 = st.columns([3, 1])
                            with c1:
                                titulo = " ".join(str(r.get('titulo','')).split())
                                if len(titulo) > 90:
                                    titulo = titulo[:87] + "…"
                                st.write(titulo)
                                try:
                                    st.caption(f"${int(r.get('precio', 0)):,}".replace(",", "."))
                                except Exception:
                                    st.caption(f"${r.get('precio','')}")
                            with c2:
                                st.link_button("Ver", r.get("link", "#"), width="stretch")

    # --- SONIDO (al final para que suene en el mismo click) ---
    if st.session_state.get("play_sound"):
        try:
            # Render hidden autoplay audio (no controls bar)
            with open(WOLF_PATH, "rb") as f:
                audio_bytes = f.read()
            b64 = base64.b64encode(audio_bytes).decode()
            components.html(
                f"""
                <audio autoplay style='display:none;'>
                  <source src='data:audio/mp3;base64,{b64}' type='audio/mp3'>
                </audio>
                """,
                height=0,
            )
        except Exception:
            # fallback silencioso
            pass
        st.session_state["play_sound"] = False

    # Si no hay cacerías, mostrar mensaje
    if not st.session_state.busquedas:
        st.info("Todavía no tenés cacerías activas. Cargá una arriba y apretá 'Lanzar'.")