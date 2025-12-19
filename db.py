import os
import sqlite3
from contextlib import contextmanager
from typing import List, Dict

DB_PATH = "data.db"


def init_db() -> None:
    """Создаёт таблицы, если их ещё нет."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        conn.close()


def save_document(user_id: str, name: str, chunks: List[str], created_at: str) -> int:
    """Сохраняет документ и его чанки, возвращает id документа."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO documents (user_id, name, created_at) VALUES (?, ?, ?)",
            (user_id, name, created_at),
        )
        doc_id = cur.lastrowid

        cur.executemany(
            "INSERT INTO chunks (document_id, text) VALUES (?, ?)",
            [(doc_id, ch) for ch in chunks],
        )
        conn.commit()

    return doc_id


def get_user_documents(user_id: str) -> List[Dict]:
    """
    Возвращает список документов пользователя с объединённым текстом чанков.
    Формат: {"filename": str, "content": str}
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT d.id, d.name, GROUP_CONCAT(c.text, '\n')
            FROM documents d
            JOIN chunks c ON c.document_id = d.id
            WHERE d.user_id = ?
            GROUP BY d.id, d.name
            """,
            (user_id,),
        )
        rows = cur.fetchall()

    docs: List[Dict] = []
    for _doc_id, name, content in rows:
        docs.append({"filename": name, "content": content or ""})
    return docs


def list_documents(user_id: str) -> List[Dict]:
    """Возвращает список документов пользователя без содержимого."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, created_at FROM documents WHERE user_id = ? ORDER BY id",
            (user_id,),
        )
        rows = cur.fetchall()

    return [
        {"id": doc_id, "name": name, "created_at": created_at}
        for doc_id, name, created_at in rows
    ]


def delete_document(user_id: str, document_id: int) -> bool:
    """Удаляет документ пользователя (вместе с чанками). Возвращает True, если что-то удалили."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM documents WHERE id = ? AND user_id = ?",
            (document_id, user_id),
        )
        deleted = cur.rowcount > 0
        conn.commit()
    return deleted

def delete_all_documents(user_id: str) -> int:
    """
    Удаляет все документы пользователя.
    Возвращает количество удалённых документов.
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM documents WHERE user_id = ?",
            (user_id,),
        )
        deleted_count = cur.rowcount
        conn.commit()

    return deleted_count




