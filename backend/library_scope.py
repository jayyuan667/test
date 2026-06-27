import os
import re
import sqlite3
from datetime import datetime

try:
    from .vector_map_rag import DB_PATH
except ImportError:
    try:
        from backend.vector_map_rag import DB_PATH
    except ImportError:
        from vector_map_rag import DB_PATH

PUBLIC_LIBRARY_KEY = "public"
PUBLIC_LIBRARY_NAME = "公共工艺库"
PUBLIC_SCOPE_TYPE = "public"
PUBLIC_VECTOR_TABLE = "vectors_v2"
PUBLIC_FEATURE_TABLE = "drawing_features"


def is_public_library(library_key: str | None) -> bool:
    """Check whether a library_key refers to the public library."""
    return (library_key or "").strip() == PUBLIC_LIBRARY_KEY


def is_public_scope_type(scope_type: str | None) -> bool:
    """Check whether a scope_type value is public."""
    return (scope_type or "").strip() == PUBLIC_SCOPE_TYPE


def ensure_import_tracking_tables():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS kb_import_batches (
                batch_id TEXT PRIMARY KEY,
                zip_name TEXT,
                conflict_mode TEXT,
                total_files INTEGER DEFAULT 0,
                pdf_count INTEGER DEFAULT 0,
                xlsx_count INTEGER DEFAULT 0,
                matched_pairs INTEGER DEFAULT 0,
                imported_count INTEGER DEFAULT 0,
                skipped_count INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                finished_at TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS kb_import_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT,
                prefix TEXT,
                pdf_name TEXT,
                xlsx_name TEXT,
                status TEXT,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()

        # Migration: add enterprise_id column to kb_import_batches
        cursor.execute("PRAGMA table_info(kb_import_batches)")
        if "enterprise_id" not in {r[1] for r in cursor.fetchall()}:
            cursor.execute("ALTER TABLE kb_import_batches ADD COLUMN enterprise_id INTEGER")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_batches_enterprise ON kb_import_batches(enterprise_id)")
        conn.commit()
    finally:
        conn.close()


def sanitize_identifier(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", (value or "").strip().lower()).strip("_")
    if not cleaned:
        cleaned = f"lib_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    if cleaned[0].isdigit():
        cleaned = f"lib_{cleaned}"
    return cleaned[:48]


def ensure_scope_registry():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS kb_library_scopes (
                library_key TEXT PRIMARY KEY,
                library_name TEXT NOT NULL,
                scope_type TEXT NOT NULL,
                vector_table TEXT NOT NULL,
                feature_table TEXT NOT NULL,
                seed_source TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_batch_id TEXT DEFAULT ''
            )
            """
        )
        cursor.execute(
            """
            INSERT OR IGNORE INTO kb_library_scopes
            (library_key, library_name, scope_type, vector_table, feature_table, seed_source, last_batch_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                PUBLIC_LIBRARY_KEY,
                PUBLIC_LIBRARY_NAME,
                "public",
                PUBLIC_VECTOR_TABLE,
                PUBLIC_FEATURE_TABLE,
                "system",
                "",
            ),
        )

        # Migration: add enterprise_id column
        cursor.execute("PRAGMA table_info(kb_library_scopes)")
        if "enterprise_id" not in {r[1] for r in cursor.fetchall()}:
            cursor.execute("ALTER TABLE kb_library_scopes ADD COLUMN enterprise_id INTEGER")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scopes_enterprise ON kb_library_scopes(enterprise_id)")

        conn.commit()
    finally:
        conn.close()


def ensure_vector_table(table_name: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prefix TEXT NOT NULL,
                vector BLOB,
                content TEXT,
                product_type TEXT,
                process_summary TEXT,
                key_features TEXT,
                materials TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tech_requirement TEXT DEFAULT '',
                real INTEGER DEFAULT 0,
                context TEXT,
                source_type TEXT DEFAULT '',
                source_task_id TEXT DEFAULT '',
                preview_task_id TEXT DEFAULT '',
                preview_total_pages INTEGER DEFAULT 0,
                preview_image_urls TEXT DEFAULT '',
                feature_report_text TEXT DEFAULT '',
                feature_report_path TEXT DEFAULT '',
                blank_type TEXT,
                overall_length_min REAL,
                overall_length_max REAL,
                main_diameter_min REAL,
                main_diameter_max REAL,
                tolerance_levels TEXT DEFAULT '[]',
                thread_specs TEXT DEFAULT '[]',
                hole_specs TEXT DEFAULT '[]',
                roughness TEXT DEFAULT '[]',
                heat_treatment TEXT,
                inspection_standards TEXT,
                special_requirements TEXT DEFAULT '',
                vector_content TEXT DEFAULT ''
            )
            """
        )
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_prefix ON {table_name}(prefix)")
        cursor.execute(
            f"""
            DELETE FROM {table_name}
            WHERE COALESCE(real, 1) = 1
              AND id NOT IN (
                  SELECT MAX(id)
                  FROM {table_name}
                  WHERE COALESCE(real, 1) = 1
                  GROUP BY UPPER(prefix)
              )
            """
        )
        cursor.execute(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_{table_name}_prefix_real_unique
            ON {table_name}(prefix)
            WHERE COALESCE(real, 1) = 1
            """
        )

        # Migration: add enterprise_id column
        cursor.execute(f"PRAGMA table_info({table_name})")
        if "enterprise_id" not in {r[1] for r in cursor.fetchall()}:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN enterprise_id INTEGER")
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_enterprise ON {table_name}(enterprise_id)")

        conn.commit()
    finally:
        conn.close()


def ensure_feature_table(table_name: str):
    # Structured filter columns are now part of the vector table.
    # This function is kept as a no-op so existing callers don't break.
    pass


def initialize_library_storage():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    ensure_scope_registry()
    ensure_vector_table(PUBLIC_VECTOR_TABLE)
    ensure_import_tracking_tables()


def copy_public_baseline(target_vector_table: str, target_feature_table: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {target_vector_table}")
        existing = int(cursor.fetchone()[0] or 0)
        if existing <= 0:
            cursor.execute(
                f"""
                INSERT INTO {target_vector_table}
                SELECT * FROM {PUBLIC_VECTOR_TABLE}
                WHERE COALESCE(real, 1) = 1
                  AND id IN (
                      SELECT MAX(id)
                      FROM {PUBLIC_VECTOR_TABLE}
                      WHERE COALESCE(real, 1) = 1
                      GROUP BY UPPER(prefix)
                  )
                """
            )
        conn.commit()
    finally:
        conn.close()


def ensure_scope(library_key: str, library_name: str, scope_type: str = "private", seed_public: bool = False, last_batch_id: str = "", enterprise_id: int | None = None):
    ensure_scope_registry()
    normalized_key = sanitize_identifier(library_key)
    vector_table = f"vectors_{normalized_key}"
    feature_table = f"drawing_features_{normalized_key}"
    ensure_vector_table(vector_table)
    ensure_feature_table(feature_table)
    if seed_public:
        copy_public_baseline(vector_table, feature_table)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT OR REPLACE INTO kb_library_scopes
            (library_key, library_name, scope_type, vector_table, feature_table, seed_source, last_batch_id, enterprise_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_key,
                library_name or normalized_key,
                scope_type,
                vector_table,
                feature_table,
                "public" if seed_public else "empty",
                last_batch_id or "",
                enterprise_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "library_key": normalized_key,
        "library_name": library_name or normalized_key,
        "scope_type": scope_type,
        "vector_table": vector_table,
        "feature_table": feature_table,
        "seed_source": "public" if seed_public else "empty",
        "last_batch_id": last_batch_id or "",
    }


def resolve_scope(library_key: str | None = None):
    ensure_scope_registry()
    key = sanitize_identifier(library_key) if library_key and library_key != PUBLIC_LIBRARY_KEY else PUBLIC_LIBRARY_KEY
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT library_key, library_name, scope_type, vector_table, feature_table, seed_source, created_at, last_batch_id, enterprise_id
            FROM kb_library_scopes WHERE library_key = ?
            """,
            (key,),
        )
        row = cursor.fetchone()
    finally:
        conn.close()

    if not row:
        return None

    return {
        "library_key": row[0],
        "library_name": row[1],
        "scope_type": row[2],
        "vector_table": row[3],
        "feature_table": row[4],
        "seed_source": row[5],
        "created_at": row[6],
        "last_batch_id": row[7] or "",
        "enterprise_id": row[8],
    }


def list_scopes():
    ensure_scope_registry()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT library_key, library_name, scope_type, vector_table, feature_table, seed_source, created_at, last_batch_id, enterprise_id
            FROM kb_library_scopes
            ORDER BY CASE WHEN library_key = ? THEN 0 ELSE 1 END, created_at DESC
            """,
            (PUBLIC_LIBRARY_KEY,),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    return [
        {
            "library_key": row[0],
            "library_name": row[1],
            "scope_type": row[2],
            "vector_table": row[3],
            "feature_table": row[4],
            "seed_source": row[5],
            "created_at": row[6],
            "last_batch_id": row[7] or "",
            "enterprise_id": row[8],
        }
        for row in rows
    ]


def mark_scope_batch(library_key: str, batch_id: str):
    ensure_scope_registry()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE kb_library_scopes SET last_batch_id = ? WHERE library_key = ?",
            (batch_id or "", PUBLIC_LIBRARY_KEY if library_key == PUBLIC_LIBRARY_KEY else sanitize_identifier(library_key)),
        )
        conn.commit()
    finally:
        conn.close()


def browse_unlock_status():
    ensure_scope_registry()
    ensure_import_tracking_tables()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM kb_import_batches WHERE imported_count > 0")
        imported_batches = int(cursor.fetchone()[0] or 0)
    finally:
        conn.close()
    return {"can_browse": imported_batches > 0, "imported_batches": imported_batches}
