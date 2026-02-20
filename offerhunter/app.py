import sqlite3
import streamlit as st
import base64
import requests
from bs4 import BeautifulSoup

from auth import (
    login_user,
    register_user,
    reset_password,
    create_reset_token,
    verify_user,
    send_username
)

from scraper_pro import hunt_offers as rastrear_busqueda
from engine import start_engine

if "play_sound" not in st.session_state:
    st.session_state["play_sound"] = False

if st.session_state.get("play_sound"):
    with open("wolf.mp3", "rb") as f:
        audio_bytes = f.read()
        b64 = base64.b64encode(audio_bytes).decode()

    st.markdown(
        f"""
        <audio autoplay style="display:none;">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
        """,
        unsafe_allow_html=True,
    )

    st.session_state["play_sound"] = False

PLAN_LIMITS = {
    "omega": 2,
    "beta": 5,
    "alfa": 10
}

# --- FUNCIONES DE BASE DE DATOS ---

def guardar_caza(usuario_id, producto, url, precio_max, frecuencia, tipo_alerta, plan):
    conn = sqlite3.connect("offerhunter.db")
    cursor = conn.cursor()

    # Obtener plan real del usuario (backup)
    cursor.execute("SELECT plan FROM usuarios WHERE id = ?", (usuario_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return False

    plan_usuario = row[0].lower()

    # Si viene plan vacío, usamos el de la DB
    if not plan:
        plan = plan_usuario

    # Contar cazas actuales
    cursor.execute("""
        SELECT COUNT(*) FROM cazas
        WHERE usuario_id = ? AND plan = ?
    """, (usuario_id, plan))

    cantidad = cursor.fetchone()[0]

    limite = PLAN_LIMITS.get(plan, 2)

    if cantidad >= limite:
        conn.close()
        return "limite"

    # Insertar caza
    cursor.execute("""
        INSERT INTO cazas 
        (usuario_id, producto, link, precio_max, frecuencia, tipo_alerta, plan)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        usuario_id,
        producto,
        url,
        precio_max,
        frecuencia,
        tipo_alerta,
        plan
    ))

    conn.commit()
    conn.close()

    return True


def obtener_cazas(usuario_id, plan):
    conn = sqlite3.connect("offerhunter.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, producto, link, precio_max, frecuencia, tipo_alerta, plan
        FROM cazas
        WHERE usuario_id = ?
          AND plan = ?
    """, (usuario_id, plan))

    rows = cursor.fetchall()
    conn.close()

    cazas = []
    for r in rows:
        cazas.append({
            "id": r[0],
            "keyword": r[1],
            "url": r[2],          # en DB se llama link, pero en tu app lo usás como url
            "max_price": r[3],
            "frecuencia": r[4],
            "tipo_alerta": r[5],
            "plan": r[6]
        })

    return cazas

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="OfferHunter 🐺", layout="wide", page_icon="🐺")

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

params = st.query_params

# --- RUTAS DE RECUPERACIÓN ---
if "verify" in params:
    if verify_user(params["verify"]):
        st.success("✅ Email verificado")
    else:
        st.error("❌ Token inválido")
    st.stop()
elif "reset-password" in params:
    st.title("Nueva contraseña")
    p1 = st.text_input("Nueva contraseña", type="password")
    if st.button("Guardar"):
        if reset_password(params["reset-password"], p1):
            st.success("✅ Contraseña actualizada")
        else:
            st.error("❌ Error o token expirado")
    st.stop()

# --- LÓGICA DE ACCESO ---
if "user_logged" not in st.session_state:
    logo_b64 = get_base64_logo("img/logo.png")
    st.markdown(f'<div class="contenedor-logo"><img src="data:image/png;base64,{logo_b64}" class="aura"></div>', unsafe_allow_html=True)
    
    _, col_main, _ = st.columns([1, 2, 1])
    with col_main:
        t1, t2 = st.tabs(["🔑 Iniciar Sesión", "🐺 Unirse a la Jauría"])
        
        with t1:
            u = st.text_input("Usuario o Email", key="l_u")
            p = st.text_input("Contraseña", type="password", key="l_p")
            if st.button("Entrar", use_container_width=True, type="primary"):
                user = login_user(u, p)
                if user: 
                    st.session_state["user_logged"] = user
                    st.rerun()
                else:
                    st.error("❌ Usuario/contraseña incorrectos.")
        
        with t2:
            if "plan_elegido" not in st.session_state:
                st.subheader("Elegí tu rango en la manada")
                c1, c2, c3 = st.columns(3)
                
                with c1:
                    st.markdown("""<div class="plan-card">
                        <h3 class="plan-title">Omega 🐾</h3>
                        <p class="plan-price">$5 / mes</p>
                        <ul class="plan-features">
                            <li>✅ 2 búsquedas activas</li>
                            <li>✅ Alertas por precio piso</li>
                            <li>✅ Notificaciones básicas</li>
                        </ul></div>""", unsafe_allow_html=True)
                    if st.button("Elegir Omega", use_container_width=True):
                        st.session_state["plan_elegido"] = "omega"; st.rerun()

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
                    if st.button("Elegir Beta", use_container_width=True):
                        st.session_state["plan_elegido"] = "beta"; st.rerun()

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
                    if st.button("Elegir Alfa", use_container_width=True):
                        st.session_state["plan_elegido"] = "alfa"; st.rerun()
            else:
                st.info(f"Registrando nuevo miembro Rango {st.session_state['plan_elegido'].capitalize()}")
                nu = st.text_input("Usuario")
                em = st.text_input("Email")
                np = st.text_input("Contraseña", type="password")
                if st.button("Finalizar Registro", use_container_width=True):
                    if register_user(nu, nu, em, "2000-01-01", np, st.session_state["plan_elegido"]):
                        st.success("¡Bienvenido! Verificá tu email para entrar.")
                    else:
                        st.error("Error al registrar.")

# --- PANEL PRINCIPAL ---
# --- PANEL PRINCIPAL ---
else:
    user = st.session_state["user_logged"]
    es_admin = user[1].lower() == "ale"

    # --- DEFINIR PLAN PRIMERO ---
    if es_admin:
        with st.sidebar:
            st.divider()
            st.subheader("🛠️ Panel de Admin")
            plan_simulado = st.radio(
                "Simular vista de rango:",
                ["Omega", "Beta", "Alfa"],
                index=2 if str(user[5]).lower().strip() == "alfa"
                else (1 if str(user[5]).lower().strip() == "beta" else 0)
            )
            plan = plan_simulado.lower()
            st.info(f"Viendo como: {plan.capitalize()}")
            st.divider()
    else:
        plan = str(user[5]).lower().strip()

    # ✅carga las búsquedas
    st.session_state.busquedas = obtener_cazas(user[0], plan)

    st.title(f"Panel de {user[1]} - Rango {plan.capitalize()} 🐺")
    # --- Indicador de uso del plan ---
    conn = sqlite3.connect("offerhunter.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) FROM cazas
        WHERE usuario_id = ? AND plan = ?
    """, (user[0],plan))

    cazas_activas = cursor.fetchone()[0]
    conn.close()

    limite_plan = PLAN_LIMITS.get(plan, 2)
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
                n_price = st.number_input("Precio Máximo ($)", min_value=0, value=500000)
                tipo_db = "piso"
            else:
                n_price = st.slider("Porcentaje deseado (%)", 5, 90, 35)
                tipo_db = "descuento"
            
            n_freq = st.selectbox("Frecuencia", freq_options)

            if st.button("Lanzar"):
                resultado = guardar_caza(
                    user[0],
                    n_key,
                    n_url,
                    n_price,
                    n_freq,
                    tipo_db,
                    plan
                )

                if resultado == "limite":
                    st.error(f"🐺 Has alcanzado el límite de tu plan {plan.capitalize()}.")
                elif resultado:
                    st.success(f"🐺 ¡Sabueso apostado en modo {tipo_db}!")
                    st.rerun()
                else:
                    st.error("Error al guardar la cacería.")
    else:
        st.warning(f"Has alcanzado el límite de {limit} búsquedas de tu plan {plan.capitalize()}.")

    # --- LISTADO DE BÚSQUEDAS ACTIVAS ---
    if st.session_state.busquedas:
        st.subheader(f"Mis Cacerías ({plan.capitalize()} 🐺)")
        
        for i, b in enumerate(st.session_state.busquedas):
            with st.container(border=True):
                col_info, col_btns = st.columns([3, 1])
                
                with col_info:
                    precio_meta = b.get('max_price', 0)
                    tipo = b.get('tipo_alerta', 'piso')
                    label_precio = f"Máx: ${precio_meta:,}" if tipo == 'piso' else f"Objetivo: {precio_meta}% desc."
                    
                    st.markdown(f"**🎯 {b['keyword']}** ({tipo.capitalize()})")
                    st.caption(f"📍 {b['url'][:50]}...")
                    st.write(f"💰 {label_precio} | ⏱️ {b['frecuencia']}")
                
                    with col_btns:

                        # 🐺 BOTÓN OLFATEAR
                        if st.button("Olfatear 🐺", key=f"olf_{i}", use_container_width=True):
                            with st.spinner("Rastreando..."):

                                from scraper_pro import hunt_offers

                                resultados = hunt_offers(
                                    b['url'],
                                    b['keyword'],
                                    b['max_price']
                                )

                                res_key = f"last_res_{i}"
                                st.session_state[res_key] = resultados

                                if resultados:
                                    st.session_state["play_sound"] = True

                                st.rerun()

                        # 🗑 BOTÓN ELIMINAR
                        if st.button("🗑 Eliminar", key=f"del_{i}", use_container_width=True):

                            conn = sqlite3.connect("offerhunter.db")
                            cursor = conn.cursor()

                            cursor.execute("DELETE FROM cazas WHERE id = ?", (b["id"],))
                            conn.commit()
                            conn.close()

                            st.success("Caza eliminada 🐺")
                            st.rerun()                   
            # --- MOSTRAR RESULTADOS ---
            res_key = f"last_res_{i}"
            if res_key in st.session_state and st.session_state[res_key]:
                ofertas = st.session_state[res_key]
                st.caption(f"DEBUG: {len(ofertas)} presas pasaron el filtro de nombre.")

                for r in ofertas:
                    if isinstance(r, dict) and 'titulo' in r:
                        precio_item = int(str(r.get('precio', 0)).replace('.', ''))
                        precio_maximo = int(b.get('max_price', 0))

                        if precio_item <= precio_maximo:
                            with st.expander(f"🍖 {r['titulo']} - ${precio_item:,}", expanded=True):
                                st.markdown(f"[Ver oferta en la web]({r.get('link', '#')})")
                                
                                if plan in ["alfa", "beta"] and st.session_state.ws_vinculado:
                                    msg = f"🐺 *¡PRESA!*%0A*Producto:* {r['titulo']}%0A*Precio:* ${precio_item}%0A*Link:* {r.get('link')}"
                                    st.markdown(f"""<a href="https://wa.me/?text={msg}" target="_blank">
                                        <button style="background-color:#25D366; color:white; border:none; padding:8px 12px; border-radius:5px; cursor:pointer;">
                                            📲 Avisar por WhatsApp
                                        </button></a>""", unsafe_allow_html=True)
                    else:
                        st.warning("Se detectó una oferta pero el formato es incompatible.")

    # --- FOOTER / BOTÓN DE TESTEO ---
    st.sidebar.write("---")
    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state["user_logged"]
        st.rerun()
