import os
import sqlite3
from contextlib import contextmanager
from typing import List, Dict
import hashlib          
import secrets         
from datetime import datetime, timedelta   
from typing import Optional  

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
       # Таблица пользователей
        # UNIQUE значит, что два одинаковых username нельза создать
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,  
                email TEXT UNIQUE NOT NULL,     
                password_hash TEXT NOT NULL,    
                salt TEXT NOT NULL,             
                created_at TEXT NOT NULL
            )
        """)
        
        # Таблица сессий (кто сейчас онлайн)
        # expires_at - когда сессия протухнет (через 7 дней)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,        
                token TEXT UNIQUE NOT NULL,     
                expires_at TEXT NOT NULL,       
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # ВСТАВЛЯЕМ ЭТОТ КОД ПОСЛЕ СОЗДАНИЯ ТАБЛИЦ И ПЕРЕД МИГРАЦИЕЙ DOCUMENTS
        # ===== ДОБАВЛЯЕМ ПОЛЕ role В ТАБЛИЦУ users =====

        # Проверяем, нужно ли добавить поле role
        cur.execute("PRAGMA table_info(users)")
        user_columns = cur.fetchall()
        user_column_names = [col[1] for col in user_columns]

        if 'role' not in user_column_names:
            print("Добавляем поле role в таблицу users...")
            # Добавляем поле role со значением по умолчанию 'user'
            cur.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
            print("Поле role добавлено!")
        # Убираем else, чтобы не писать "Поле role уже существует" при каждом запуске       

# ===== НОВЫЙ КОД: МИГРАЦИЯ БАЗЫ ДАННЫХ =====
        # Проверяем, нужно ли обновить структуру таблицы documents
        
        # Получаем информацию о таблице documents
        cur.execute("PRAGMA table_info(documents)")
        columns = cur.fetchall()
        column_names = [col[1] for col in columns]
        
        # Если user_id все еще TEXT, нужно создать новую таблицу и перенести данные
        if 'user_id' in column_names:
            # Проверяем тип колонки user_id
            for col in columns:
                if col[1] == 'user_id' and col[2].upper() == 'TEXT':
                    print("Обновляем структуру таблицы documents...")
                    
                    # Создаем временную таблицу с правильной структурой
                    cur.execute("""
                        CREATE TABLE documents_new (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            name TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                        )
                    """)
                    
                    # Создаем временную таблицу для chunks
                    cur.execute("""
                        CREATE TABLE chunks_new (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            document_id INTEGER NOT NULL,
                            text TEXT NOT NULL,
                            FOREIGN KEY (document_id) REFERENCES documents_new(id) ON DELETE CASCADE
                        )
                    """)
                    
                    # Переносим данные (создаем пользователя 'default' если его нет)
                    cur.execute("SELECT id FROM users WHERE username = 'default'")
                    default_user = cur.fetchone()
                    
                    if not default_user:
                        # Создаем пользователя default для существующих документов
                        salt, pwd_hash = hash_password("default_password")
                        cur.execute("""
                            INSERT INTO users (username, email, password_hash, salt, created_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, ("default", "default@local.host", pwd_hash, salt, datetime.now().isoformat()))
                        default_user_id = cur.lastrowid
                    else:
                        default_user_id = default_user[0]
                    
                    # Переносим документы
                    cur.execute("""
                        INSERT INTO documents_new (id, user_id, name, created_at)
                        SELECT id, ?, name, created_at FROM documents
                    """, (default_user_id,))
                    
                    # Переносим чанки
                    cur.execute("""
                        INSERT INTO chunks_new (id, document_id, text)
                        SELECT id, document_id, text FROM chunks
                    """)
                    
                    # Удаляем старые таблицы
                    cur.execute("DROP TABLE documents")
                    cur.execute("DROP TABLE chunks")
                    
                    # Переименовываем новые таблицы
                    cur.execute("ALTER TABLE documents_new RENAME TO documents")
                    cur.execute("ALTER TABLE chunks_new RENAME TO chunks")
                    
                    print("Миграция завершена!")
                    break

        
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


# ИЗМЕНЯЕМ функцию save_document - теперь user_id это int
def save_document(user_id: int, name: str, chunks: List[str], created_at: str) -> int:
    """
    Сохраняет документ и его чанки, возвращает id документа.
    user_id теперь INTEGER (ID пользователя из таблицы users)
    """
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

# ИЗМЕНЯЕМ функцию get_user_documents - теперь user_id это int
def get_user_documents(user_id: int) -> List[Dict]:
    """
    Возвращает список документов пользователя с объединённым текстом чанков.
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT d.id, d.name, GROUP_CONCAT(c.text, '\n') as content
            FROM documents d
            JOIN chunks c ON c.document_id = d.id
            WHERE d.user_id = ?
            GROUP BY d.id, d.name
            """,
            (user_id,),
        )
        rows = cur.fetchall()
        
        # Преобразуем в список словарей
        result = []
        for row in rows:
            result.append({
                "id": row[0],
                "filename": row[1],
                "content": row[2] or ""
            })
        return result

# ИЗМЕНЯЕМ функцию list_documents - теперь user_id это int
def list_documents(user_id: int) -> List[Dict]:
    """Возвращает список документов пользователя без содержимого."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, created_at FROM documents WHERE user_id = ? ORDER BY id",
            (user_id,),
        )
        rows = cur.fetchall()

    return [
        {"id": row[0], "name": row[1], "created_at": row[2]}
        for row in rows
    ]

# ИЗМЕНЯЕМ функцию delete_document - теперь user_id это int
def delete_document(user_id: int, document_id: int) -> bool:
    """Удаляет документ пользователя."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM documents WHERE id = ? AND user_id = ?",
            (document_id, user_id),
        )
        deleted = cur.rowcount > 0
        conn.commit()
    return deleted

# ИЗМЕНЯЕМ функцию delete_all_documents - теперь user_id это int
def delete_all_documents(user_id: int) -> int:
    """Удаляет все документы пользователя."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM documents WHERE user_id = ?",
            (user_id,),
        )
        deleted_count = cur.rowcount
        conn.commit()
    return deleted_count

# ============================================
# ФУНКЦИИ ДЛЯ ШИФРОВАНИЯ ПАРОЛЕЙ
# ============================================

def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """
    Превращает пароль "12345" в непонятный набор букв и цифр.
    
    """
    # Если соль не дали - создаем случайную
    if salt is None:
        salt = secrets.token_hex(16)  # например: "4f7d3a9b1c5e2f8a"
    
    # PBKDF2 - стандартный алгоритм шифрования
    key = hashlib.pbkdf2_hmac(
        'sha256',                    # алгоритм хеширования
        password.encode('utf-8'),    # пароль в байты
        salt.encode('utf-8'),         # соль в байты
        100000                        # 100 тысяч итераций (чем больше, тем надежнее)
    )
    
    return salt, key.hex()  # возвращаем соль и хеш

def verify_password(password: str, salt: str, password_hash: str) -> bool:
    """
    Проверяет, правильный ли пароль ввел пользователь.
    
    """
    _, new_hash = hash_password(password, salt)
    return new_hash == password_hash

# ============================================
# ФУНКЦИИ ДЛЯ СОЗДАНИЯ ПОЛЬЗОВАТЕЛЕЙ
# ============================================

def create_user(username: str, email: str, password: str) -> int:
    """
    Создает нового пользователя в БД.

    """
    # Шифруем пароль
    salt, password_hash = hash_password(password)
    
    # Текущее время в формате ISO
    created_at = datetime.now().isoformat()  # например: "2024-01-15T10:30:45"
    
    # Подключаемся к БД и добавляем пользователя
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO users (username, email, password_hash, salt, created_at, role)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (username, email, password_hash, salt, created_at, 'user'))
            conn.commit()
            return cur.lastrowid  # возвращаем ID нового пользователя
            
        except sqlite3.IntegrityError as e:
            # Обрабатываем ошибки (пользователь уже существует)
            if "username" in str(e):
                raise ValueError("Имя пользователя уже занято")
            elif "email" in str(e):
                raise ValueError("Email уже зарегистрирован")
            raise

def get_user_by_username(username: str) -> Optional[Dict]:
    """
    Ищет пользователя по логину.

    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        
        if row:
            # Превращаем результат в словарь (чтобы обращаться по именам)
            columns = [description[0] for description in cur.description]
            return dict(zip(columns, row))
        return None

def get_user_by_id(user_id: int) -> Optional[Dict]:
    """
    Ищет пользователя по ID (без пароля и соли).
    Используется, когда пользователь уже залогинился.
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, email, created_at, role 
            FROM users WHERE id = ?
        """, (user_id,))
        row = cur.fetchone()
        
        if row:
            columns = [description[0] for description in cur.description]
            return dict(zip(columns, row))
        return None



def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """
    Проверяет логин и пароль при входе.
    """
    # Сначала находим пользователя по логину
    user = get_user_by_username(username)
    if not user:
        return None
    
    # Проверяем пароль
    if verify_password(password, user['salt'], user['password_hash']):
        # Возвращаем данные без пароля и соли, НО С РОЛЬЮ
        return {
            'id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'created_at': user['created_at'],
            'role': user['role']
        }
    return None

# ============================================
# ФУНКЦИИ ДЛЯ СЕССИЙ (КТО ЗАЛОГИНЕН)
# ============================================

def create_session(user_id: int) -> str:
    """
    Создает сессию для пользователя.

    """
    # Создаем случайный токен (как номер пропуска)
    token = secrets.token_urlsafe(32)  # например: "x8f9a3kD2pL5vN7..."
    
    # Сессия действует 7 дней
    expires_at = (datetime.now() + timedelta(days=7)).isoformat()
    
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sessions (user_id, token, expires_at)
            VALUES (?, ?, ?)
        """, (user_id, token, expires_at))
        conn.commit()
    
    return token

def get_user_by_token(token: str) -> Optional[Dict]:
    """
    По токену находит пользователя.
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT u.id, u.username, u.email, u.created_at, u.role
            FROM users u
            JOIN sessions s ON s.user_id = u.id
            WHERE s.token = ? AND s.expires_at > datetime('now')
        """, (token,))
        
        row = cur.fetchone()
        if row:
            columns = [description[0] for description in cur.description]
            return dict(zip(columns, row))
        return None

def delete_session(token: str) -> bool:
    """
    Удаляет сессию по токену.
    Возвращает True, если что-то удалили.
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM sessions WHERE token = ?", (token,))
        deleted = cur.rowcount > 0  # сколько строк удалено
        conn.commit()
    return deleted


# ============================================
# НОВЫЕ ФУНКЦИИ ДЛЯ АДМИН-ПАНЕЛИ
# ============================================

def get_all_users() -> List[Dict]:
    """
    ПОЛУЧИТЬ ВСЕХ ПОЛЬЗОВАТЕЛЕЙ (для админа)
    
    Возвращает список всех пользователей с информацией:
    - id, username, email, role, created_at
    - количество документов у каждого пользователя
    """
    with get_conn() as conn:
        cur = conn.cursor()
        
        # Получаем всех пользователей + считаем их документы
        cur.execute("""
            SELECT 
                u.id, 
                u.username, 
                u.email, 
                u.role, 
                u.created_at,
                COUNT(d.id) as documents_count
            FROM users u
            LEFT JOIN documents d ON d.user_id = u.id
            GROUP BY u.id
            ORDER BY u.id
        """)
        
        rows = cur.fetchall()
        
        # Превращаем в список словарей
        columns = [description[0] for description in cur.description]
        users = []
        for row in rows:
            user_dict = dict(zip(columns, row))
            users.append(user_dict)
        
        return users

def delete_user_by_id(user_id: int) -> bool:
    """
    УДАЛИТЬ ПОЛЬЗОВАТЕЛЯ ПО ID (для админа)
    
    Благодаря ON DELETE CASCADE в таблицах:
    - sessions (удалятся все сессии пользователя)
    - documents (удалятся все документы пользователя)
    - chunks (удалятся через documents)
    
    Возвращает True, если пользователь был удален
    """
    with get_conn() as conn:
        cur = conn.cursor()
        
        # Сначала проверим, есть ли такой пользователь
        cur.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        if not cur.fetchone():
            return False
        
        # Удаляем пользователя (всё остальное удалится каскадно)
        cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        
        return cur.rowcount > 0

def get_all_documents_admin() -> List[Dict]:
    """
    ПОЛУЧИТЬ ВСЕ ДОКУМЕНТЫ (для админа)
    
    Возвращает список всех документов с информацией:
    - id документа, имя файла, дата загрузки
    - кто загрузил (id, username)
    - количество чанков в документе
    """
    with get_conn() as conn:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                d.id,
                d.name,
                d.created_at,
                u.id as user_id,
                u.username as username,
                COUNT(c.id) as chunks_count
            FROM documents d
            JOIN users u ON u.id = d.user_id
            LEFT JOIN chunks c ON c.document_id = d.id
            GROUP BY d.id
            ORDER BY d.id DESC
        """)
        
        rows = cur.fetchall()
        
        # Превращаем в список словарей
        columns = [description[0] for description in cur.description]
        documents = []
        for row in rows:
            doc_dict = dict(zip(columns, row))
            documents.append(doc_dict)
        
        return documents

def delete_any_document(document_id: int) -> bool:
    """
    УДАЛИТЬ ЛЮБОЙ ДОКУМЕНТ (для админа)
    
    Удаляет документ независимо от того, кому он принадлежит.
    Чанки удалятся автоматически благодаря ON DELETE CASCADE.
    """
    with get_conn() as conn:
        cur = conn.cursor()
        
        # Проверяем, есть ли такой документ
        cur.execute("SELECT id FROM documents WHERE id = ?", (document_id,))
        if not cur.fetchone():
            return False
        
        # Удаляем документ (чанки удалятся каскадно)
        cur.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        conn.commit()
        
        return cur.rowcount > 0

def change_user_role(user_id: int, new_role: str) -> bool:
    """
    ИЗМЕНИТЬ РОЛЬ ПОЛЬЗОВАТЕЛЯ (для админа)
    
    new_role может быть 'user' или 'admin'
    """
    if new_role not in ['user', 'admin']:
        raise ValueError("Роль может быть только 'user' или 'admin'")
    
    with get_conn() as conn:
        cur = conn.cursor()
        
        # Проверяем, есть ли такой пользователь
        cur.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        if not cur.fetchone():
            return False
        
        # Меняем роль
        cur.execute("""
            UPDATE users 
            SET role = ? 
            WHERE id = ?
        """, (new_role, user_id))
        
        conn.commit()
        return cur.rowcount > 0

def get_user_stats(user_id: int) -> Dict:
    """
    ПОЛУЧИТЬ СТАТИСТИКУ ПОЛЬЗОВАТЕЛЯ (для админки)
    
    Сколько документов, сколько чанков, когда последний вход и т.д.
    """
    with get_conn() as conn:
        cur = conn.cursor()
        
        # Получаем статистику по документам
        cur.execute("""
            SELECT 
                COUNT(DISTINCT d.id) as documents_count,
                COUNT(c.id) as chunks_count,
                MAX(d.created_at) as last_upload
            FROM users u
            LEFT JOIN documents d ON d.user_id = u.id
            LEFT JOIN chunks c ON c.document_id = d.id
            WHERE u.id = ?
        """, (user_id,))
        
        stats_row = cur.fetchone()
        
        # Получаем последнюю сессию
        cur.execute("""
            SELECT MAX(expires_at) as last_session
            FROM sessions
            WHERE user_id = ? AND expires_at > datetime('now')
        """, (user_id,))
        
        session_row = cur.fetchone()
        
        columns = [description[0] for description in cur.description]
        stats = dict(zip(columns, stats_row))
        
        if session_row and session_row[0]:
            stats['last_active'] = session_row[0]
        else:
            stats['last_active'] = None
            
        return stats

