import streamlit as st
import base64
import requests
from bs4 import BeautifulSoup
from auth import login_user, register_user, reset_password, create_reset_token, verify_user, send_username
from scraper_pro import check_price as rastrear_busqueda
import streamlit as st
import sqlite3
# ... tus otros imports ...

# --- FUNCIONES DE BASE DE DATOS ---
def guardar_caza(usuario_id, producto, link, frecuencia):
    try:
        conn = sqlite3.connect("offerhunter.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO cazas (usuario_id, producto, link, frecuencia)
            VALUES (?, ?, ?, ?)
        """, (usuario_id, producto, link, frecuencia))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error al guardar: {e}")
        return False

# 1. Configuración e Inicialización (Layout wide para que las cards respiren)
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
    except: return ""

# --- CSS Global ---
st.markdown("""
    <style>
        .contenedor-logo { display: flex; justify-content: center; }
        .aura { width: 250px; transform: scale(0.85); -webkit-mask-image: radial-gradient(circle, black 40%, rgba(0,0,0,0) 70%); }
        
        /* Estilo de las Cards */
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

# --- RUTAS DE RECUPERACIÓN (Sin cambios) ---
if "verify" in params:
    if verify_user(params["verify"]): st.success("✅ Email verificado")
    else: st.error("❌ Token inválido")
    st.stop()
elif "reset-password" in params:
    st.title("Nueva contraseña")
    p1 = st.text_input("Nueva contraseña", type="password")
    if st.button("Guardar"):
        if reset_password(params["reset-password"], p1): st.success("✅ Contraseña actualizada")
        else: st.error("❌ Error o token expirado")
    st.stop()

# --- LÓGICA DE ACCESO ---
if "user_logged" not in st.session_state:
    logo_b64 = get_base64_logo("img/logo.png")
    st.markdown(f'<div class="contenedor-logo"><img src="data:image/png;base64,{logo_b64}" class="aura"></div>', unsafe_allow_html=True)
    
    # Usamos columnas laterales para centrar el formulario de login pero dejar las cards anchas
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
                else: st.error("❌ Usuario/contraseña incorrectos.")
        
        with t2:
            if "plan_elegido" not in st.session_state:
                st.subheader("Elegí tu rango en la manada")
                # Aquí las columnas están dentro del tab, aprovechando el layout wide
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
                # Registro post-elección
                st.info(f"Registrando nuevo miembro Rango {st.session_state['plan_elegido'].capitalize()}")
                nu = st.text_input("Usuario")
                em = st.text_input("Email")
                np = st.text_input("Contraseña", type="password")
                if st.button("Finalizar Registro", use_container_width=True):
                    if register_user(nu, nu, em, "2000-01-01", np, st.session_state["plan_elegido"]):
                        st.success("¡Bienvenido! Verificá tu email para entrar.")
                    else: st.error("Error al registrar.")

# --- PANEL PRINCIPAL (Solo entra si está logueado) ---
else:
    user = st.session_state["user_logged"]
    
    # 1. Verificamos si sos vos (Admin)
    es_admin = user[1].lower() == "ale"  # Ajustár por nombre de usuario exacto

    # 2. Si es admin, mostramos el switch; si no, cargamos su plan real
    if es_admin:
        with st.sidebar:
            st.divider()
            st.subheader("🛠️ Panel de Admin")
            plan_simulado = st.radio(
                "Simular vista de rango:",
                ["Omega", "Beta", "Alfa"],
                index=2 if str(user[5]).lower().strip() == "alfa" else (1 if str(user[5]).lower().strip() == "beta" else 0)
            )
            plan = plan_simulado.lower()
            st.info(f"Viendo como: {plan.capitalize()}")
            st.divider()
    else:
        plan = str(user[5]).lower().strip()

    st.title(f"Panel de {user[1]} - Rango {plan.capitalize()} 🐺")

# Configuración de límites y tiempos por Plan
    if plan == "alfa":
        limit = 10
        freq_options = ["15 min", "30 min", "45 min", "1 h"]
    elif plan == "beta":
        limit = 5
        freq_options = ["30 min", "1 h", "1.5 h", "2 h", "2.5 h"]
    else: # omega
        limit = 2
        freq_options = ["1 h", "2 h", "3 h", "4 h"]

    # --- Sección WhatsApp (Solo Alfa y Beta) ---
    if plan in ["alfa", "beta"]:
        with st.expander("📲 Sincronizar WhatsApp", expanded=not st.session_state.ws_vinculado):
            if not st.session_state.ws_vinculado:
                link_wa = "https://wa.me/5491100000000?text=Vincular%20Cuenta"
                st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={link_wa}")
                if st.button("Confirmar Vinculación ✅"):
                    st.session_state.ws_vinculado = True; st.rerun()
            else:
                st.success("✅ WhatsApp Activo")


    # --- Lógica de Cacerías (Respetando el límite del plan) ---
    total_ocupado = len(st.session_state.busquedas)
    
    if total_ocupado < limit:
        with st.expander("➕ Configurar nueva cacería"):
            n_url = st.text_input("URL")
            n_key = st.text_input("Palabra clave")
            n_price = st.number_input("Precio Máximo", min_value=0)
            n_freq = st.selectbox("Frecuencia", freq_options)
            if st.button("Lanzar"):
                st.session_state.busquedas.append({"url": n_url, "keyword": n_key, "max_price": n_price, "frecuencia": n_freq})
                st.rerun()
    else:
        st.warning(f"Has alcanzado el límite de {limit} búsquedas de tu plan {plan.capitalize()}.")

    # Listado de búsquedas activas
    for i, b in enumerate(st.session_state.busquedas):
        st.info(f"🎯 {b['keyword']} - Máx: ${b['max_price']} ({b['frecuencia']})")

# --- LISTADO DE BÚSQUEDAS ACTIVAS ---
if st.session_state.busquedas:
    st.subheader(f"Mis Cacerías ({plan.capitalize()} 🐺)")
    
    for i, b in enumerate(st.session_state.busquedas):
        with st.container(border=True):
            col_info, col_btns = st.columns([3, 1])
            
            with col_info:
                st.markdown(f"**🎯 {b['keyword']}**")
                st.caption(f"📍 {b['url'][:50]}...")
                st.write(f"💰 Máx: ${b['max_price']} | ⏱️ {b['frecuencia']}")
            
            with col_btns:
                if st.button("Olfatear 🐺", key=f"olf_{i}", use_container_width=True):
                    with st.spinner("Buscando..."):
                        # 1. Rastreo inmediato (Pasamos solo URL y Precio como espera tu scraper)
                        resultados = rastrear_busqueda(b['url'], b['max_price'])
                        
                        # 2. Extraer frecuencia numérica para la BD
                        try:
                            valor_f = b.get('frecuencia', "60")
                            freq_db = int(''.join(filter(str.isdigit, str(valor_f))))
                        except:
                            freq_db = 60
                        
                        # 3. GUARDAR EN BD
                        exito = guardar_caza(
                            usuario_id=1, 
                            producto=b['keyword'], 
                            link=b['url'], 
                            frecuencia=freq_db
                        )
                        
                        if resultados:
                            st.session_state[f"last_res_{i}"] = resultados
                            if exito: st.success(f"¡Guardado! Check cada {freq_db}m")
                        else:
                            st.error("Sin rastro por ahora...")
                
                if st.button("Eliminar 🗑️", key=f"del_{i}", use_container_width=True):
                    st.session_state.busquedas.pop(i)
                    if f"last_res_{i}" in st.session_state:
                        del st.session_state[f"last_res_{i}"]
                    st.rerun()

        # --- MOSTRAR RESULTADOS (Con escudo anti-errores) ---
        res_key = f"last_res_{i}"
        if res_key in st.session_state and st.session_state[res_key]:
            for r in st.session_state[res_key]:
                # Verificamos que 'r' sea un dict válido antes de pedirle el título
                if isinstance(r, dict) and 'titulo' in r:
                    with st.expander(f"🍖 {r['titulo']} - ${r.get('precio', '???')}", expanded=True):
                        st.markdown(f"[Ver oferta en la web]({r.get('link', '#')})")
                        
                        if plan in ["alfa", "beta"] and st.session_state.ws_vinculado:
                            msg = f"🐺 *¡PRESA!*%0A*Producto:* {r['titulo']}%0A*Precio:* ${r.get('precio')}%0A*Link:* {r.get('link')}"
                            st.markdown(f"""<a href="https://wa.me/?text={msg}" target="_blank">
                                <button style="background-color:#25D366; color:white; border:none; padding:8px 12px; border-radius:5px; cursor:pointer;">
                                    📲 Avisar por WhatsApp
                                </button></a>""", unsafe_allow_html=True)
                else:
                    st.warning("Se detectó una oferta pero el formato es incompatible.")

    # --- FOOTER / BOTÓN DE TESTEO (OPCIONAL) ---
    st.sidebar.write("---")
    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state["user_logged"]
        st.rerun()