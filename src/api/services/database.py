import sqlite3
import os
from pathlib import Path
from datetime import datetime

# ── Portable path resolution ─────────────────────────────────────────────────
# services/ → api/ → src/ → project root
_BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DB_PATH = str(_BASE_DIR / "data" / "transcriptosense.db")

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transcriptions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            filename        TEXT    NOT NULL,
            language        TEXT,
            transcription   TEXT,
            model_used      TEXT    DEFAULT 'whisper-small',
            file_size       TEXT,
            duration_sec    REAL    DEFAULT 0,
            speakers_count  INTEGER DEFAULT 0,
            has_diarization INTEGER DEFAULT 0,
            created_at      TEXT    DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # Gracefully add columns for users upgrading from older schemas
    for col, definition in [
        ("duration_sec",    "REAL DEFAULT 0"),
        ("speakers_count",  "INTEGER DEFAULT 0"),
        ("has_diarization", "INTEGER DEFAULT 0"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE transcriptions ADD COLUMN {col} {definition}")
        except Exception:
            pass  # Column already exists — fine

    conn.commit()
    conn.close()
    print(f"[DB] Initialized: {DB_PATH}")


def save_transcription(
    filename: str,
    language: str,
    transcription: str,
    model_used: str = "whisper-small",
    file_size: str = "",
    duration_sec: float = 0.0,
    speakers_count: int = 0,
    has_diarization: bool = False,
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO transcriptions
            (filename, language, transcription, model_used, file_size, duration_sec, speakers_count, has_diarization)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (filename, language, transcription, model_used, file_size, duration_sec,
          speakers_count, int(has_diarization)))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    print(f"[DB] Saved ID={new_id} — {filename} [{model_used}]")
    return new_id


def get_all_transcriptions():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, filename, language, transcription, model_used, file_size,
               duration_sec, speakers_count, has_diarization, created_at
        FROM transcriptions
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_transcription_by_id(transcription_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, filename, language, transcription, model_used, file_size,
               duration_sec, speakers_count, has_diarization, created_at
        FROM transcriptions WHERE id = ?
    """, (transcription_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_transcription(transcription_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transcriptions WHERE id = ?", (transcription_id,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def clear_all_transcriptions() -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transcriptions")
    conn.commit()
    count = cursor.rowcount
    conn.close()
    print(f"[DB] Cleared {count} transcription(s).")
    return count


def search_transcriptions(query: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, filename, language, transcription, model_used, file_size,
               duration_sec, speakers_count, has_diarization, created_at
        FROM transcriptions
        WHERE transcription LIKE ? OR filename LIKE ?
        ORDER BY created_at DESC
    """, (f"%{query}%", f"%{query}%"))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
