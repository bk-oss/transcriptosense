import sqlite3
import os
from datetime import datetime

DB_PATH = r"C:\Users\mbaklouti1\Desktop\transcriptosense\data\transcriptosense.db"

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
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            filename    TEXT    NOT NULL,
            language    TEXT,
            transcription TEXT,
            model_used  TEXT    DEFAULT 'whisper-large-v3',
            file_size   TEXT,
            created_at  TEXT    DEFAULT (datetime('now', 'localtime'))
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Database initialized successfully.")


def save_transcription(filename: str, language: str, transcription: str, file_size: str = ""):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO transcriptions (filename, language, transcription, model_used, file_size)
        VALUES (?, ?, ?, ?, ?)
    """, (filename, language, transcription, "whisper-large-v3", file_size))

    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    print(f"[DB] Saved transcription ID={new_id} for file: {filename}")
    return new_id


def get_all_transcriptions():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, filename, language, transcription, model_used, file_size, created_at
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
        SELECT id, filename, language, transcription, model_used, file_size, created_at
        FROM transcriptions
        WHERE id = ?
    """, (transcription_id,))

    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_transcription(transcription_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM transcriptions WHERE id = ?", (transcription_id,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()

    return affected > 0


def search_transcriptions(query: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, filename, language, transcription, model_used, file_size, created_at
        FROM transcriptions
        WHERE transcription LIKE ? OR filename LIKE ?
        ORDER BY created_at DESC
    """, (f"%{query}%", f"%{query}%"))

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

