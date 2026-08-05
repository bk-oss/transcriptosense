import sqlite3
import os
from pathlib import Path

# ── Portable path resolution ───────────────────────────────────
_BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH   = str(_BASE_DIR.parent / "data" / "transcriptosense.db")

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

print(f"[DB] Database path: {DB_PATH}")


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn   = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transcriptions (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            filename         TEXT    NOT NULL,
            language         TEXT,
            transcription    TEXT,
            cleaned_text     TEXT,
            translated_text  TEXT,
            summary          TEXT,
            segments         TEXT,
            model_used       TEXT    DEFAULT 'deepgram-nova-2',
            file_size        TEXT,
            duration_sec     REAL    DEFAULT 0,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ✅ Add new columns if upgrading from old DB
    new_columns = [
        ("cleaned_text",    "TEXT"),
        ("translated_text", "TEXT"),
        ("summary",         "TEXT"),
        ("segments",        "TEXT"),
        ("duration_sec",    "REAL DEFAULT 0"),
    ]
    for col_name, col_type in new_columns:
        try:
            cursor.execute(
                f"ALTER TABLE transcriptions ADD COLUMN {col_name} {col_type}"
            )
        except Exception:
            pass

    conn.commit()
    conn.close()
    print("[DB] Database initialized successfully.")


def save_transcription(
    filename:         str,
    language:         str,
    transcription:    str,
    file_size:        str   = "",
    duration_sec:     float = 0.0,
    cleaned_text:     str   = None,
    translated_text:  str   = None,
    summary:          str   = None,
    segments:         str   = None,
    model_used:       str   = "deepgram-nova-2",
) -> int:
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO transcriptions
            (filename, language, transcription, cleaned_text,
             translated_text, summary, segments,
             model_used, file_size, duration_sec)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            filename, language, transcription,
            cleaned_text, translated_text, summary, segments,
            model_used, file_size, duration_sec,
        ),
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    print(f"[DB] Saved transcription id={new_id} filename={filename}")
    return new_id


def get_all_transcriptions():
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, filename, language, transcription,
               cleaned_text, translated_text, summary, segments,
               model_used, file_size, duration_sec, created_at
        FROM transcriptions
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_transcription_by_id(transcription_id: int):
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, filename, language, transcription,
               cleaned_text, translated_text, summary, segments,
               model_used, file_size, duration_sec, created_at
        FROM transcriptions WHERE id = ?
        """,
        (transcription_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_transcription(transcription_id: int) -> bool:
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM transcriptions WHERE id = ?",
        (transcription_id,)
    )
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def clear_all_transcriptions() -> int:
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transcriptions")
    conn.commit()
    count = cursor.rowcount
    conn.close()
    return count


def search_transcriptions(query: str):
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, filename, language, transcription,
               cleaned_text, translated_text, summary, segments,
               model_used, file_size, duration_sec, created_at
        FROM transcriptions
        WHERE transcription LIKE ? OR filename LIKE ?
        ORDER BY created_at DESC
        """,
        (f"%{query}%", f"%{query}%"),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
