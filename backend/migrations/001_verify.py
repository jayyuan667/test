"""
Verify that all business tables have the enterprise_id column.
Run: python backend/migrations/001_verify.py
Exit code 0 = all good, 1 = missing columns.
"""

import os
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def verify_table(conn, table, db_label):
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    columns = {row[1] for row in cursor.fetchall()}
    if "enterprise_id" not in columns:
        print(f"ERROR: [{db_label}] {table} missing enterprise_id column")
        return False
    print(f"  OK: [{db_label}] {table}.enterprise_id")
    return True


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ok = True

    # task_store.db
    task_db = os.path.join(base, "task_store.db")
    if os.path.exists(task_db):
        conn = sqlite3.connect(task_db)
        try:
            ok &= verify_table(conn, "tasks", "task_store.db")
        finally:
            conn.close()

    # vectors.db
    from backend.vector_map_rag import DB_PATH
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        try:
            ok &= verify_table(conn, "kb_library_scopes", "vectors.db")
            ok &= verify_table(conn, "kb_import_batches", "vectors.db")
            # Check all vector tables
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'vectors_%'")
            for (table,) in cursor.fetchall():
                ok &= verify_table(conn, table, "vectors.db")
        finally:
            conn.close()

    if ok:
        print("\nAll tables have enterprise_id column.")
        sys.exit(0)
    else:
        print("\nSome tables are missing enterprise_id column!")
        sys.exit(1)


if __name__ == "__main__":
    main()
