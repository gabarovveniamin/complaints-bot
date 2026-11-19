import os
import sqlite3
from pathlib import Path
from datetime import datetime

# На Vercel доступен для записи только /tmp
if os.getenv("VERCEL"):
    DB_PATH = Path("/tmp/appeals.db")
else:
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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_states (
                user_id INTEGER PRIMARY KEY,
                state TEXT NOT NULL
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


def set_user_state(user_id: int, state: str | None):
    """Устанавливает или сбрасывает текущее состояние пользователя."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        if state is None:
            cursor.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
        else:
            cursor.execute("""
                INSERT INTO user_states (user_id, state) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET state = excluded.state
            """, (user_id, state))
        conn.commit()


def get_user_state(user_id: int) -> str | None:
    """Возвращает текущее состояние пользователя."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT state FROM user_states WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row[0] if row else None
