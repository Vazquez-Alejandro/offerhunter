import os
import requests
import sqlite3

# =========================
# CONFIGURACIÓN GENERAL
# =========================

BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # .../offerhunter
DB_PATH = os.path.join(BASE_DIR, "offerhunter.db")

TOKEN_TELEGRAM = os.getenv("TOKEN_TELEGRAM", "")

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")


# =========================
# UTILIDADES
# =========================

def _clean_wa_id(wa_id) -> str | None:
    if wa_id is None:
        return None
    s = str(wa_id).replace("+", "").replace(" ", "").strip()
    if not s:
        return None

    # AR: si viene como 54911XXXXXXXX -> convertir a 541115XXXXXXXX
    if s.startswith("54911") and len(s) >= 12:
        s = "541115" + s[5:]

    return s

# =========================
# ENVÍO WHATSAPP
# =========================

def responder_mensaje(wa_id, texto):
    wa_id = _clean_wa_id(wa_id)

    if not wa_id:
        print("📭 Sin whatsapp_id, no se envía.")
        return None

    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        print("❌ Falta WHATSAPP_TOKEN o WHATSAPP_PHONE_NUMBER_ID en variables de entorno.")
        return None

    print("📞 Enviando WhatsApp a:", wa_id)

    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }

    data = {
    "messaging_product": "whatsapp",
    "to": wa_id,
    "type": "template",
    "template": {
        "name": "hello_world",
        "language": {"code": "en_US"}
    }
}

    try:
        response = requests.post(url, headers=headers, json=data)
    except Exception as e:
        print("❌ Error de conexión con WhatsApp:", e)
        return None

    if response.status_code not in (200, 201):
        print(f"❌ WhatsApp ERROR {response.status_code}: {response.text}")
    else:
        print(f"📤 WhatsApp enviado a: {wa_id} | Status: {response.status_code}")

    try:
        return response.json()
    except Exception:
        return None


# =========================
# NOTIFICACIONES
# =========================

def notificar_caceria_iniciada(usuario_id, producto):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT whatsapp_id FROM usuarios WHERE id = ?", (usuario_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row[0]:
        print(f"📭 Usuario {usuario_id} sin whatsapp_id, no se envía cacería iniciada.")
        return

    mensaje = (
        f"🎯 ¡Cacería iniciada!\n\n"
        f"El Sabueso ya está rastreando '{producto}'.\n"
        f"Te aviso apenas baje el precio. 🐺"
    )

    responder_mensaje(row[0], mensaje)


def notificar_oferta_encontrada(usuario_id, producto_dict):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT whatsapp_id FROM usuarios WHERE id = ?", (usuario_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row[0]:
        print(f"📭 Usuario {usuario_id} sin whatsapp_id, no se envía oferta.")
        return

    precio = producto_dict.get("precio")
    titulo = producto_dict.get("titulo")
    link = producto_dict.get("link")

    if precio is None or not titulo or not link:
        return

    try:
        precio_formateado = f"{int(float(precio)):,}".replace(",", ".")
    except Exception:
        precio_formateado = str(precio)

    mensaje = (
        f"🐺 ¡PRESA ENCONTRADA! 🍖\n\n"
        f"Producto: {titulo}\n"
        f"Precio: ${precio_formateado}\n"
        f"Link: {link}\n\n"
        f"¡Corré que vuela! 🚀"
    )

    responder_mensaje(row[0], mensaje)


# =========================
# TELEGRAM (OPCIONAL)
# =========================

def enviar_alerta_premium_telegram(chat_id, producto, precio):
    if not TOKEN_TELEGRAM:
        print("❌ Falta TOKEN_TELEGRAM.")
        return

    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage"

    mensaje = (
        f"🔥 ¡OFERTA PREMIUM DETECTADA! 🔥\n\n"
        f"📦 {producto}\n"
        f"💰 Precio: ${precio}"
    )

    payload = {
        "chat_id": chat_id,
        "text": mensaje,
    }

    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("❌ Error enviando Telegram:", e)