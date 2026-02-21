import sqlite3

DB_NAME = "offerhunter.db"


def _tiene_columna(cursor, tabla: str, col: str) -> bool:
    cursor.execute(f"PRAGMA table_info({tabla});")
    return col.lower() in [r[1].lower() for r in cursor.fetchall()]


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # =========================
    # 1) USUARIOS (compatible con auth.py)
    # =========================
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

    # Si la tabla existía con otro esquema, agregamos columnas faltantes
    # (SQLite permite ALTER TABLE ADD COLUMN sin perder datos)
    if not _tiene_columna(cursor, "usuarios", "nick"):
        cursor.execute("ALTER TABLE usuarios ADD COLUMN nick TEXT")
    if not _tiene_columna(cursor, "usuarios", "nombre"):
        cursor.execute("ALTER TABLE usuarios ADD COLUMN nombre TEXT")
    if not _tiene_columna(cursor, "usuarios", "nacimiento"):
        cursor.execute("ALTER TABLE usuarios ADD COLUMN nacimiento TEXT")
    if not _tiene_columna(cursor, "usuarios", "password"):
        cursor.execute("ALTER TABLE usuarios ADD COLUMN password TEXT")
    if not _tiene_columna(cursor, "usuarios", "plan"):
        cursor.execute("ALTER TABLE usuarios ADD COLUMN plan TEXT DEFAULT 'omega'")
    if not _tiene_columna(cursor, "usuarios", "telegram_id"):
        cursor.execute("ALTER TABLE usuarios ADD COLUMN telegram_id TEXT")
    if not _tiene_columna(cursor, "usuarios", "whatsapp_id"):
        cursor.execute("ALTER TABLE usuarios ADD COLUMN whatsapp_id TEXT")
    if not _tiene_columna(cursor, "usuarios", "verified"):
        cursor.execute("ALTER TABLE usuarios ADD COLUMN verified INTEGER DEFAULT 0")

    # =========================
    # 2) CAZAS (tu esquema actual + opcionales engine)
    # =========================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cazas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            producto TEXT,
            link TEXT,
            precio_max INTEGER,
            frecuencia TEXT,
            tipo_alerta TEXT DEFAULT 'piso',
            plan TEXT,
            estado TEXT DEFAULT 'activa',
            last_check TIMESTAMP,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        )
    """)

    # Si existía con tu esquema, agregamos lo que falte
    if not _tiene_columna(cursor, "cazas", "tipo_alerta"):
        cursor.execute("ALTER TABLE cazas ADD COLUMN tipo_alerta TEXT DEFAULT 'piso'")
    if not _tiene_columna(cursor, "cazas", "plan"):
        cursor.execute("ALTER TABLE cazas ADD COLUMN plan TEXT")
    if not _tiene_columna(cursor, "cazas", "estado"):
        cursor.execute("ALTER TABLE cazas ADD COLUMN estado TEXT DEFAULT 'activa'")
    if not _tiene_columna(cursor, "cazas", "last_check"):
        cursor.execute("ALTER TABLE cazas ADD COLUMN last_check TIMESTAMP")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("✅ DB lista y migrada")