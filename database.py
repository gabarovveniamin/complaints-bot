import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent / "appeals.db"

def init_db():
    """Инициализация базы данных и создание таблиц."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS appeals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                created_at TEXT NOT NULL,
                content_type TEXT NOT NULL,
                preview_text TEXT,
                status TEXT DEFAULT 'new'
            )
        """)
        conn.commit()

def create_appeal(user_id: int, content_type: str, preview_text: str | None = None) -> int:
    """Создает запись о новой жалобе и возвращает её порядковый номер."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO appeals (user_id, created_at, content_type, preview_text)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, now_str, content_type, preview_text)
        )
        conn.commit()
        return cursor.lastrowid
