import sqlite3

DB_NAME = "offerhunter.db"

def update_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Crear tabla usuarios con todas las columnas necesarias
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nick TEXT UNIQUE,
                nombre TEXT,
                email TEXT UNIQUE,
                nacimiento TEXT,
                password TEXT,
                plan TEXT DEFAULT 'omega', -- ahora usamos omega/beta/alfa
                telegram_id TEXT,
                whatsapp_id TEXT,
                verified INTEGER DEFAULT 0
            )
        """)
        print("✅ Tabla usuarios creada o ya existente.")
    except Exception as e:
        print("❌ Error creando tabla usuarios:", e)

    # Crear tabla tokens
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                token TEXT,
                type TEXT, -- 'verify' o 'reset'
                FOREIGN KEY(user_id) REFERENCES usuarios(id)
            )
        """)
        print("✅ Tabla tokens creada o ya existente.")
    except Exception as e:
        print("❌ Error creando tabla tokens:", e)

    # Crear tabla cazas
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cazas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                producto TEXT NOT NULL,
                estado TEXT CHECK(estado IN ('activa','exitosa')) DEFAULT 'activa',
                link TEXT,
                FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
            )
        """)
        print("✅ Tabla cazas creada o ya existente.")
    except Exception as e:
        print("❌ Error creando tabla cazas:", e)

    # Crear tabla historial
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                caza_id INTEGER NOT NULL,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                pagina TEXT,
                resultado TEXT CHECK(resultado IN ('exito','fallo')),
                detalle_error TEXT,
                FOREIGN KEY(caza_id) REFERENCES cazas(id)
            )
        """)
        print("✅ Tabla historial creada o ya existente.")
    except Exception as e:
        print("❌ Error creando tabla historial:", e)

    conn.commit()
    conn.close()
    print("🎉 Base de datos actualizada correctamente.")

if __name__ == "__main__":
    update_db()
