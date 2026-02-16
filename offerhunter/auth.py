import sqlite3
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

DB_NAME = "offerhunter.db"

# --- envío de mails ---
def send_email(to_email, subject, body):
    from_email = "vazquezale82@gmail.com"
    password = "REDACTED"  # clave de aplicación SIN espacios extra

    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(from_email, password)
        server.sendmail(from_email, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print("Error enviando mail:", e)
        return False

# --- login flexible (usuario o email) ---
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
        print("Error en login:", e)
        return None

# --- registro ---
def register_user(nick, nombre, e, b, p, plan="basic"):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO usuarios (nick, nombre, email, nacimiento, password, plan, telegram_id, whatsapp_id, verified)
            VALUES (?,?,?,?,?,?,NULL,NULL,0)
        """, (nick, nombre, e, b, p, plan))
        token = str(uuid.uuid4())
        cursor.execute("INSERT INTO tokens (user_ref, token, type) VALUES (?,?,?)", (nick, token, "verify"))
        conn.commit()
        conn.close()
        send_email(
            e,
            "Verifica tu cuenta",
            f"<p>Haz clic para verificar: <a href='http://localhost:8501/?verify={token}'>Verificar</a></p>"
        )
        return True
    except Exception as e:
        print("Error registrando usuario:", e)
        return False

# --- verificación de email ---
def verify_user(token):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT user_ref FROM tokens WHERE token=? AND type='verify'", (token,))
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE usuarios SET verified=1 WHERE nick=?", (row[0],))
            cursor.execute("DELETE FROM tokens WHERE token=?", (token,))
            conn.commit()
            conn.close()
            return True
        conn.close()
        return False
    except Exception as e:
        print("Error verificando usuario:", e)
        return False

# --- reset de contraseña ---
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
            send_email(
                email,
                "Resetear contraseña",
                f"<p>Haz clic para resetear: <a href='http://localhost:8501/?reset-password={token}'>Resetear</a></p>"
            )
            return True
        conn.close()
        return False
    except Exception as e:
        print("Error creando token de reset:", e)
        return False

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
    except Exception as e:
        print("Error reseteando contraseña:", e)
        return False

# --- recuperar usuario ---
def send_username(email):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT nick FROM usuarios WHERE email=?", (email,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return send_email(
                email,
                "Recuperar usuario",
                f"<p>Tu usuario registrado es: <b>{row[0]}</b></p>"
            )
        return False
    except Exception as e:
        print("Error recuperando usuario:", e)
        return False
