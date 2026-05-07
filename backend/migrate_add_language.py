import sqlite3

def add_language_column():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE projects ADD COLUMN language VARCHAR(20) DEFAULT 'English'")
        print("Column 'language' added to projects table.")
    except sqlite3.OperationalError as e:
        print(f"Error (column might already exist): {e}")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    add_language_column()
