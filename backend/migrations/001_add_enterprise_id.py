"""
Add enterprise_id column to all business tables.

Idempotent — safe to run multiple times.
Run: python backend/migrations/001_add_enterprise_id.py
"""

import os
import sys
import sqlite3

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _add_column_if_missing(conn, table, column="enterprise_id", col_type="INTEGER"):
    """Add a column if it doesn't exist."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cursor.fetchall()}
    if column not in existing:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        return True
    return False


def _add_index_if_missing(conn, table, column, index_name=None):
    """Create an index if it doesn't exist."""
    if index_name is None:
        index_name = f"idx_{table}_{column}"
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name=?", (index_name,))
    if not cursor.fetchone():
        cursor.execute(f"CREATE INDEX {index_name} ON {table}({column})")
        return True
    return False


def migrate(db_path, tables):
    """Add enterprise_id to the given tables in the given database."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        for table in tables:
            added = _add_column_if_missing(conn, table)
            indexed = _add_index_if_missing(conn, table, "enterprise_id", index_name=f"idx_{table}_enterprise")
            if added:
                print(f"  [{db_path}] {table}: added enterprise_id column")
            else:
                print(f"  [{db_path}] {table}: enterprise_id already exists")
        conn.commit()
    finally:
        conn.close()


def report_unresolved(base):
    """Report records that couldn't have enterprise_id inferred."""
    unresolved = []

    # Check tasks with NULL enterprise_id
    task_db = os.path.join(base, "task_store.db")
    if os.path.exists(task_db):
        conn = sqlite3.connect(task_db)
        cursor = conn.cursor()
        cursor.execute("SELECT task_id, pdf_name, library_key FROM tasks WHERE enterprise_id IS NULL")
        for row in cursor.fetchall():
            unresolved.append(("tasks", row[0], row[2] or "", "cannot infer enterprise_id"))
        conn.close()

    # Check vector tables with NULL enterprise_id
    try:
        from backend.vector_map_rag import DB_PATH
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'vectors_%'")
            for (table,) in cursor.fetchall():
                cursor.execute(f"SELECT id, prefix FROM {table} WHERE enterprise_id IS NULL")
                for row in cursor.fetchall():
                    unresolved.append((table, row[0], "", "cannot infer enterprise_id"))
            conn.close()
    except Exception:
        pass

    if unresolved:
        print(f"\n=== UNRESOLVED RECORDS ({len(unresolved)}) ===")
        print("These records have NULL enterprise_id and are invisible to enterprise users.")
        print("table, primary_key, library_key, reason")
        for rec in unresolved:
            print(f"{rec[0]}, {rec[1]}, {rec[2]}, {rec[3]}")

    return unresolved


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # task_store.db
    task_db = os.path.join(base, "task_store.db")
    if os.path.exists(task_db):
        print(f"Migrating {task_db}...")
        migrate(task_db, ["tasks"])

    # vectors.db (library)
    from backend.vector_map_rag import DB_PATH
    if os.path.exists(DB_PATH):
        print(f"Migrating {DB_PATH}...")
        # 先获取所有需要迁移的 vector 表名
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'vectors_%'")
            vector_tables = [row[0] for row in cursor.fetchall()]
            # 加上 kb_library_scopes 和 kb_import_batches
            scope_tables = ["kb_library_scopes", "kb_import_batches"]
            all_tables = scope_tables + vector_tables
            migrate(DB_PATH, all_tables)
        finally:
            conn.close()

    print("Migration complete.")

    # Report unresolved records (NULL enterprise_id that could not be backfilled)
    report_unresolved(base)


if __name__ == "__main__":
    main()
