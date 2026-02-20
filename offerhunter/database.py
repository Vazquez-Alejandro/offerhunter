import sqlite3

DB_NAME = "offerhunter.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Usuarios
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            whatsapp_id TEXT,
            plan TEXT DEFAULT 'free',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Cazas activas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cazas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            producto TEXT,
            url TEXT,
            precio_max REAL,
            estado TEXT DEFAULT 'activa',
            frecuencia INTEGER DEFAULT 15,
            last_check TIMESTAMP,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        )
    """)

    conn.commit()
    conn.close()