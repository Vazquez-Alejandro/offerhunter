import requests
import sqlite3

# --- CONFIGURACIONES ---
DB_NAME = "offerhunter.db"

# Token de Telegram
TOKEN_TELEGRAM = "7778005982:AAGksBoeO0fNzmI_PsF-tAUdZ6krLGGso58"

# Token de WhatsApp (Meta)
ACCESS_TOKEN = "EAAdoMd1LDlEBQt3EirJLNe4bvI1uzLyhDd3W7EBZBiazB3Fhc9wvBk6M0hwlwpBxGROZA1On8KTECfWp8ljaQ7EOU5P0J0C2tbdeFvG6gW6HYrwZCxxIctZAMATT2SNjWSZBeZCDeWl5pXZBijBekknzvaifM7pggbbKZCNQdzJhCC0dJUE3PcPaDxzqqnSzX92yOZBaZAhKNq0Tt8YTWRtXXT5TF8LkGTZCWhpn5hAyFSpOZCydb5ZCHjPAVYgRNs9axudF53GbhvetbgTJWCuWE8tVw1QZDZD"

# --- WHATSAPP (MOTOR DE ENVÍO) ---
def responder_mensaje(wa_id, texto):
    """
    Envía un mensaje por WhatsApp usando la API de Meta.
    Normaliza el número para evitar errores de envío.
    """
    # Limpieza básica del número
    wa_id = str(wa_id).replace("+", "").replace(" ", "").strip()
    
    # Normalización para Argentina (ajustar según necesidad de Meta)
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
    
    try:
        response = requests.post(url, headers=headers, json=data)
        print(f"📤 WhatsApp enviado a: {wa_id} | Status: {response.status_code}")
        return response.json()
    except Exception as e:
        print(f"❌ Error enviando WhatsApp: {e}")
        return None

# --- NOTIFICACIONES DE CACERÍA ---

def notificar_caceria_iniciada(usuario_id, producto):
    """
    Avisa al usuario que su búsqueda ya está en el radar.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT whatsapp_id FROM usuarios WHERE id = ?", (usuario_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        mensaje = f"🎯 ¡Cacería iniciada! El Sabueso ya está rastreando '{producto}'. Te aviso apenas baje el precio. 🐺"
        responder_mensaje(row[0], mensaje)

def notificar_oferta_encontrada(usuario_id, producto_dict):
    """
    LA FUNCIÓN CLAVE: Se dispara cuando el backend encuentra un precio bajo.
    producto_dict debe tener: titulo, precio, link
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT whatsapp_id FROM usuarios WHERE id = ?", (usuario_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        wa_id = row[0]
        # Formateamos el precio con separador de miles para que sea legible
        precio_formateado = f"{int(producto_dict['precio']):,}".replace(",", ".")
        
        mensaje = (
            f"🐺 ¡PRESA ENCONTRADA! 🍖\n\n"
            f"🔥 *Producto:* {producto_dict['titulo']}\n"
            f"💰 *Precio:* ${precio_formateado}\n"
            f"🔗 *Link:* {producto_dict['link']}\n\n"
            f"¡Corré que vuela! 🚀"
        )
        responder_mensaje(wa_id, mensaje)

# --- TELEGRAM (OPCIONAL / PREMIUM) ---
def enviar_alerta_premium_telegram(chat_id, producto, precio):
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage"
    mensaje = f"🔥 *¡OFERTA PREMIUM DETECTADA!* 🔥\n\n📦 {producto}\n💰 Precio: ${precio}"
    payload = {"chat_id": chat_id, "text": mensaje, "parse_mode": "Markdown"}
    requests.post(url, json=payload)