import sqlite3
import uuid
import os

DB_NAME = "offerhunter.db"

# --- INICIALIZACIÓN DE TABLAS ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nick TEXT UNIQUE,
            nombre TEXT,
            email TEXT UNIQUE,
            nacimiento TEXT,
            password TEXT,
            plan TEXT,
            telegram_id TEXT,
            whatsapp_id TEXT,
            verified INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_ref TEXT,
            token TEXT,
            type TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- ENVÍO DE MAILS ---
import os
import requests

def send_email(to_email: str, subject: str, html_body: str) -> bool:
    api_key = os.getenv("RESEND_API_KEY")
    from_email = os.getenv("RESEND_FROM_EMAIL")

    if not api_key or not from_email:
        print("[EMAIL] Missing RESEND_API_KEY or RESEND_FROM_EMAIL")
        return False

    try:
        r = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": from_email,
                "to": [to_email],
                "subject": subject,
                "html": html_body,
            },
            timeout=20,
        )

        if r.status_code >= 300:
            print("[EMAIL] Resend error", r.status_code, r.text)
            return False

        print("[EMAIL] Resend ok", r.json())
        return True

    except Exception as e:
        print("[EMAIL] Exception", e)
        return False

# --- LOGIN ---
def login_user(u_or_email, p):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM usuarios 
            WHERE (nick=? OR email=?) AND password=? AND verified=1
        """, (u_or_email, u_or_email, p))
        user = cursor.fetchone()
        conn.close()
        return user
    except Exception as e:
        print("Error login:", e)
        return None

# --- REGISTRO ---
def register_user(nick, nombre, e, b, p, plan="basic"):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO usuarios (nick, nombre, email, nacimiento, password, plan, verified)
            VALUES (?,?,?,?,?,?,0)
        """, (nick, nombre, e, b, p, plan))

        token = str(uuid.uuid4())

        cursor.execute("""
            INSERT INTO tokens (user_ref, token, type)
            VALUES (?,?,?)
        """, (nick, token, "verify"))

        conn.commit()
        conn.close()

        # 🔥 Link dinámico según entorno
        base_url = os.getenv("APP_BASE_URL", "http://localhost:8501")
        verify_link = f"{base_url}/?verify={token}"

        email_sent = send_email(
            e,
            "Verificá tu cuenta en OfferHunter",
            f"""
            <h2>Bienvenido a la manada 🐺</h2>
            <p>Para activar tu cuenta hacé clic acá:</p>
            <p><a href="{verify_link}">Verificar cuenta</a></p>
            """
        )

        if not email_sent:
            print("[REGISTER] Usuario creado pero falló el envío de email", {"email": e})

        return True
    except sqlite3.IntegrityError as err:
        msg = str(err).lower()
        if "usuarios.email" in msg:
            print("Error registro: email ya registrado")
        elif "usuarios.nick" in msg:
            print("Error registro: nick ya registrado")
        else:
            print("Error registro:", err)
        return False

# --- VERIFICACIÓN ---
def verify_user(token):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_ref
            FROM tokens
            WHERE token=? AND type='verify'
        """, (token,))

        row = cursor.fetchone()

        if not row:
            conn.close()
            return False

        nick = row[0]

        cursor.execute("""
            UPDATE usuarios
            SET verified=1
            WHERE nick=?
        """, (nick,))

        cursor.execute("""
            DELETE FROM tokens
            WHERE token=?
        """, (token,))

        conn.commit()
        conn.close()

        return True

    except Exception as err:
        print("Error verify:", err)
        return False

# --- RESET Y RECUPERACIÓN (Los que faltaban) ---
def create_reset_token(email):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT nick FROM usuarios WHERE email=?", (email,))
        row = cursor.fetchone()
        if row:
            token = str(uuid.uuid4())
            cursor.execute("INSERT INTO tokens (user_ref, token, type) VALUES (?,?,?)", (row[0], token, "reset"))
            conn.commit()
            conn.close()
            send_email(email, "Reset", f"Token: {token}")
            return True
        conn.close()
        return False
    except: return False

def reset_password(token, new_pass):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT user_ref FROM tokens WHERE token=? AND type='reset'", (token,))
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE usuarios SET password=? WHERE nick=?", (new_pass, row[0]))
            cursor.execute("DELETE FROM tokens WHERE token=?", (token,))
            conn.commit()
            conn.close()
            return True
        conn.close()
        return False
    except: return False

def send_username(email):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT nick FROM usuarios WHERE email=?", (email,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return send_email(email, "Usuario", f"Tu nick es: {row[0]}")
        return False
    except: return False