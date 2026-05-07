"""
migrate_remove_cta.py — One-time migration to remove the `cta` column from scripts table.

SQLite does not support DROP COLUMN natively before version 3.35.0.
This script uses the table-rebuild pattern to safely remove the column on any SQLite version.

Usage:
    cd backend
    python migrate_remove_cta.py

The script is idempotent — safe to run multiple times.
"""

import sqlite3
import sys
from pathlib import Path


DB_PATH = Path(__file__).parent / "scriptforge.db"


def column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def migrate(db_path: Path) -> None:
    if not db_path.exists():
        print(f"Database not found at {db_path} — nothing to migrate.")
        return

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")

    try:
        cursor = conn.cursor()

        if not column_exists(cursor, "scripts", "cta"):
            print("Column 'cta' does not exist in 'scripts' — migration already applied or not needed.")
            return

        print("Removing 'cta' column from 'scripts' table…")

        # SQLite table-rebuild migration pattern
        conn.execute("BEGIN TRANSACTION")

        # 1. Create new table without `cta`
        conn.execute("""
            CREATE TABLE scripts_new (
                id              INTEGER PRIMARY KEY,
                project_id      INTEGER NOT NULL REFERENCES projects(id),
                version         INTEGER NOT NULL DEFAULT 1,
                hook            TEXT    NOT NULL DEFAULT '',
                body            TEXT    NOT NULL DEFAULT '',
                on_screen_notes TEXT    NOT NULL DEFAULT '',
                title_suggestions TEXT NOT NULL DEFAULT '[]',
                estimated_duration TEXT NOT NULL DEFAULT '',
                tone            TEXT    NOT NULL DEFAULT '',
                approved        BOOLEAN NOT NULL DEFAULT 0,
                created_at      DATETIME NOT NULL
            )
        """)

        # 2. Copy data (drop cta)
        conn.execute("""
            INSERT INTO scripts_new
                (id, project_id, version, hook, body, on_screen_notes,
                 title_suggestions, estimated_duration, tone, approved, created_at)
            SELECT
                id, project_id, version, hook, body, on_screen_notes,
                title_suggestions, estimated_duration, tone, approved, created_at
            FROM scripts
        """)

        # 3. Swap tables
        conn.execute("DROP TABLE scripts")
        conn.execute("ALTER TABLE scripts_new RENAME TO scripts")

        conn.execute("COMMIT")
        print("Migration complete — 'cta' column removed successfully.")

    except Exception as exc:
        conn.execute("ROLLBACK")
        print(f"Migration failed and was rolled back: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    migrate(DB_PATH)
