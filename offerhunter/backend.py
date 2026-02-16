import requests
from flask import Flask, request
import sqlite3
from alertas import notificar_caceria_iniciada  # Importamos las funciones de alertas

DB_NAME = "offerhunter.db"
VERIFY_TOKEN = "offerhunter_token"

app = Flask(__name__)

# --- FUNCIONES DE BASE DE DATOS ---

def guardar_caza(usuario_id, producto, estado="activa", link=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO cazas (usuario_id, producto, estado, link)
        VALUES (?, ?, ?, ?)
    """, (usuario_id, producto, estado, link))
    conn.commit()
    conn.close()
    print(f"✅ Caza guardada: {producto} para usuario {usuario_id}")

def obtener_usuario_id(wa_id, nombre):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM usuarios WHERE whatsapp_id = ?", (wa_id,))
    row = cursor.fetchone()

    if row:
        usuario_id = row[0]
        print(f"ℹ️ Usuario existente: {usuario_id} ({nombre})")
    else:
        cursor.execute("""
            INSERT INTO usuarios (nombre, whatsapp_id, verified, plan)
            VALUES (?, ?, 0, 'basic')
        """, (nombre, wa_id))
        usuario_id = cursor.lastrowid
        print(f"🆕 Usuario creado: {usuario_id} ({nombre})")

    conn.commit()
    conn.close()
    return usuario_id

# --- WEBHOOK ---

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Token inválido", 403

    if request.method == "POST":
        data = request.get_json()
        print("📩 Webhook recibido")

        try:
            entry = data["entry"][0]["changes"][0]["value"]

            if "messages" in entry:
                contacts = entry.get("contacts", [])
                nombre = contacts[0].get("profile", {}).get("name", "Usuario") if contacts else "Usuario"
                
                wa_id = entry["messages"][0]["from"]  # Ej: 5491158210746
                texto = entry["messages"][0]["text"]["body"]
                
                print(f"👉 Mensaje de {nombre}: {texto}")

                usuario_id = obtener_usuario_id(wa_id, nombre)
                guardar_caza(usuario_id, texto)

                # Disparar notificación de inicio de caza
                notificar_caceria_iniciada(usuario_id, texto)

        except Exception as e:
            print("⚠️ Error procesando webhook:", e)

        return "EVENT_RECEIVED", 200

if __name__ == "__main__":
    app.run(port=5000, debug=True)
