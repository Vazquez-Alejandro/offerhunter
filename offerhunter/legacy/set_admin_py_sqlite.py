import sqlite3

def convertir_en_admin(username):
    try:
        # Conectate a tu archivo de base de datos (ajustá el nombre si es distinto)
        conn = sqlite3.connect('users.db') 
        cursor = conn.cursor()

        # Primero verificamos si el usuario existe
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()

        if user:
            # Actualizamos la columna 'rol' (o 'role'). 
            # Si tu tabla no tiene esa columna, tirará error.
            cursor.execute("UPDATE users SET rol = 'admin' WHERE username = ?", (username,))
            conn.commit()
            print(f"✅ ¡Éxito! El usuario '{username}' ahora es admin.")
        else:
            print(f"❌ Error: El usuario '{username}' no existe en la base de datos.")

        conn.close()
    except Exception as e:
        print(f"⚠️ Ocurrió un error: {e}")

if __name__ == "__main__":
    convertir_en_admin("AleCodev")