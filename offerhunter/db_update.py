import sqlite3

DB_NAME = "offerhunter.db"

def update_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Tabla Usuarios
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nick TEXT UNIQUE,
                nombre TEXT,
                email TEXT UNIQUE,
                nacimiento TEXT,
                password TEXT,
                plan TEXT DEFAULT 'omega',
                telegram_id TEXT,
                whatsapp_id TEXT,
                verified INTEGER DEFAULT 0
            )
        """)
        print("✅ Tabla usuarios lista.")
    except Exception as e:
        print("❌ Error en usuarios:", e)

    # 2. Tabla Tokens
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                token TEXT,
                type TEXT,
                FOREIGN KEY(user_id) REFERENCES usuarios(id)
            )
        """)
        print("✅ Tabla tokens lista.")
    except Exception as e:
        print("❌ Error en tokens:", e)

    # 3. Tabla Cazas (Incluyendo Frecuencia)
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cazas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                producto TEXT NOT NULL,
                estado TEXT CHECK(estado IN ('activa','exitosa')) DEFAULT 'activa',
                link TEXT,
                frecuencia INTEGER DEFAULT 60,
                FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
            )
        """)
        
        # Por si ya tenías la tabla creada, intentamos agregar la columna frecuencia
        try:
            cursor.execute("ALTER TABLE cazas ADD COLUMN frecuencia INTEGER DEFAULT 60")
            print("✅ Columna 'frecuencia' agregada a cazas.")
        except:
            pass # Ya existía la columna
            
        print("✅ Tabla cazas lista.")
    except Exception as e:
        print("❌ Error en cazas:", e)

    # 4. Tabla Historial
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
        print("✅ Tabla historial lista.")
    except Exception as e:
        print("❌ Error en historial:", e)

    conn.commit()
    conn.close()
    print("\n🎉 Base de datos actualizada con éxito.")

if __name__ == "__main__":
    update_db()