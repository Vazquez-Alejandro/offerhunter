import sqlite3

def fix_db():
    conn = sqlite3.connect("offerhunter.db")
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS alertas")
    cursor.execute("""
        CREATE TABLE alertas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            url TEXT,
            keywords TEXT,
            precio_max REAL
        )
    """)
    conn.commit()
    conn.close()
    print("Base de datos reseteada y lista.")

if __name__ == "__main__":
    fix_db()