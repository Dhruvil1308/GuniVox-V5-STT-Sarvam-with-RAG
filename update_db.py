import sqlite3

def run():
    conn = sqlite3.connect('gunivox.db')
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            phone_number TEXT PRIMARY KEY,
            stage TEXT,
            last_call_sid TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()
    print("Added leads table")

run()
