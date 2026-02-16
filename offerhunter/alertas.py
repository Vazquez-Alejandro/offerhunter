import requests
import sqlite3

# --- CONFIGURACIONES ---
DB_NAME = "offerhunter.db"

# Token de Telegram
TOKEN_TELEGRAM = "7778005982:AAGksBoeO0fNzmI_PsF-tAUdZ6krLGGso58"

# Token de WhatsApp (Meta)
ACCESS_TOKEN = "EAAdoMd1LDlEBQt3EirJLNe4bvI1uzLyhDd3W7EBZBiazB3Fhc9wvBk6M0hwlwpBxGROZA1On8KTECfWp8ljaQ7EOU5P0J0C2tbdeFvG6gW6HYrwZCxxIctZAMATT2SNjWSZBeZCDeWl5pXZBijBekknzvaifM7pggbbKZCNQdzJhCC0dJUE3PcPaDxzqqnSzX92yOZBaZAhKNq0Tt8YTWRtXXT5TF8LkGTZCWhpn5hAyFSpOZCydb5ZCHjPAVYgRNs9axudF53GbhvetbgTJWCuWE8tVw1QZDZD"


# --- TELEGRAM ---
def enviar_alerta_premium_telegram(chat_id, producto, precio):
    """
    Envía una alerta premium por Telegram.
    """
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage"
    mensaje = f"🔥 *¡OFERTA PREMIUM DETECTADA!* 🔥\n\n📦 {producto}\n💰 Precio: ${precio}"
    payload = {"chat_id": chat_id, "text": mensaje, "parse_mode": "Markdown"}
    response = requests.post(url, json=payload)
    print(f"📤 Telegram enviado a {chat_id} | Respuesta: {response.status_code}")


# --- WHATSAPP ---
def responder_mensaje(wa_id, texto):
    """
    Envía un mensaje por WhatsApp usando la API de Meta.
    Normaliza el número para Argentina.
    """
    wa_id = wa_id.replace("+", "").replace(" ", "")
    if wa_id.startswith("54911"):
        wa_id = "541115" + wa_id[5:]
    elif wa_id.startswith("5411") and not wa_id.startswith("541115"):
        wa_id = "541115" + wa_id[4:]

    url = "https://graph.facebook.com/v20.0/1008815155644140/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": wa_id,
        "type": "text",
        "text": {"body": texto}
    }
    response = requests.post(url, headers=headers, json=data)
    print(f"📤 WhatsApp enviado a: {wa_id} | Respuesta: {response.status_code} | {response.json()}")


def notificar_caceria_iniciada(usuario_id, producto):
    """
    Notifica al usuario premium que su cacería fue iniciada.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT whatsapp_id, plan FROM usuarios WHERE id = ?", (usuario_id,))
    row = cursor.fetchone()
    conn.close()

    if row and row[1] == "premium":
        responder_mensaje(row[0], f"🎯 Cacería iniciada para '{producto}'. Notificaciones activadas.")


def notificar_caceria_exitosa(usuario_id, producto, link):
    """
    Notifica al usuario premium que su cacería fue exitosa y envía el link.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT whatsapp_id, plan FROM usuarios WHERE id = ?", (usuario_id,))
    row = cursor.fetchone()
    conn.close()

    if row and row[1] == "premium":
        responder_mensaje(row[0], f"🏆 Cacería exitosa: '{producto}' encontrada 👉 {link}")
