# Основной файл запуска системы
import json
import uvicorn
import db
from datetime import datetime
import os

from fastapi import FastAPI, WebSocket, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from dotenv import load_dotenv
from agent import create_agent_model, process_question
from schemas import ResearchReport
from db import init_db, save_document, list_documents, delete_document, delete_all_documents, get_all_users, delete_user_by_id, get_all_documents_admin, delete_any_document
from utils import extract_semantic_chunks

# Добавьте эти строки к существующим импортам
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import HTMLResponse
from schemas import UserCreate, UserLogin, UserResponse, TokenResponse

load_dotenv()

init_db()


app = FastAPI()

app = FastAPI()

# Это обработчик для токенов
# Он будет автоматически доставать токен из заголовка Authorization
security = HTTPBearer()

# Функция, которая будет проверять токен и возвращать пользователя
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Эта функция вызывается перед каждым защищенным эндпоинтом.
    Если пользователь не авторизован - выдаст ошибку 401.
    """
    # credentials.credentials - это сам токен
    token = credentials.credentials
    
    # Ищем пользователя по токену
    user = db.get_user_by_token(token)
    if not user:
        # Если не нашли или токен протух - ошибка
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не авторизован"
        )
    return user

# ===== НОВАЯ ЗАВИСИМОСТЬ ДЛЯ АДМИНА =====
async def get_current_admin(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Проверяет, что текущий пользователь - администратор.
    Используется для защиты admin-эндпоинтов.
    """
    if current_user.get('role') != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещен. Требуются права администратора."
        )
    return current_user





agent_model = create_agent_model()

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    with open("index.html", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Загрузка документа для ТЕКУЩЕГО пользователя.
    """
    print(f"Загрузка файла: {file.filename} от пользователя {current_user['id']}")  # для отладки
    
    uploads_dir = "uploads"
    os.makedirs(uploads_dir, exist_ok=True)
    temp_path = os.path.join(uploads_dir, file.filename)

    content_bytes = await file.read()
    with open(temp_path, "wb") as f:
        f.write(content_bytes)

    from document_reader import read_document  
    text = read_document(temp_path)
    try:
        os.remove(temp_path)
    except OSError:
        pass
    
    if not text:
        return {"status": "error", "message": "Не удалось прочитать содержимое файла"}

    chunks = extract_semantic_chunks(text)
    created_at = datetime.utcnow().isoformat()
    
    # Используем ID текущего пользователя
    doc_id = db.save_document(
        user_id=current_user['id'],
        name=file.filename,
        chunks=chunks,
        created_at=created_at
    )

    return {
        "status": "ok",
        "document_id": doc_id,
        "chunks": len(chunks),
        "filename": file.filename,
    }

# ===== ИЗМЕНЯЕМ получение документов =====
@app.get("/documents")
async def get_documents(current_user: dict = Depends(get_current_user)):
    """Список документов ТЕКУЩЕГО пользователя"""
    docs = db.list_documents(current_user['id'])  # больше нет ?user_id=
    return {"documents": docs}

# ===== ИЗМЕНЯЕМ удаление документа =====
@app.delete("/documents/{document_id}")
async def remove_document(
    document_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Удаление документа (только своего!)"""
    ok = db.delete_document(current_user['id'], document_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return {"status": "ok", "deleted_id": document_id}

# ===== ИЗМЕНЯЕМ удаление всех документов =====
@app.delete("/documents")
async def remove_all_documents(current_user: dict = Depends(get_current_user)):
    """Удаление ВСЕХ документов текущего пользователя"""
    deleted_count = db.delete_all_documents(current_user['id'])
    return {
        "status": "ok",
        "deleted_documents": deleted_count
    }
    
def report_to_markdown(report: ResearchReport) -> str:
    md = "### Ответ\n\n"
    md += report.answer.strip() + "\n\n"

    if report.sources:
        md += "### Источники\n"
        for src in report.sources:
            md += f'- <a href="{src}" target="_blank" rel="noopener noreferrer">{src}</a>\n'

    return md


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    
    # Проверяем, инициализирована ли модель
    if agent_model is None:
        await ws.send_text(json.dumps({
            "error": "Ошибка: модель агента не инициализирована. Проверьте переменную окружения GROQ_API_KEY."
        }))
        await ws.close()
        return
    
    user_id = "default"  # значение по умолчанию
    username = "Гость"
    
    # Ждем первое сообщение - в нем должен быть токен
    try:
        first_message = await ws.receive_text()
        
        # Пытаемся распарсить JSON с токеном
        try:
            data = json.loads(first_message)
            token = data.get("token")
        except json.JSONDecodeError:
            # Если не JSON, значит это просто вопрос (старый формат)
            token = None
            # Сохраняем сообщение как вопрос для обработки позже
            first_message_text = first_message
        
        if token:
            # Получаем пользователя по токену
            user = db.get_user_by_token(token)
            if user:
                user_id = str(user['id'])
                username = user['username']
                await ws.send_text(json.dumps({
                    "content": f"Соединение установлено. Добро пожаловать, {username}! Задавайте вопросы по своим документам."
                }))
            else:
                await ws.send_text(json.dumps({
                    "error": "Неавторизован. Проверьте токен."
                }))
                await ws.close()
                return
        else:
            # Режим совместимости (без токена)
            await ws.send_text(json.dumps({
                "content": "Соединение установлено в режиме совместимости (default). Задавайте вопросы!"
            }))
        
        # Основной цикл чата
        chat_history = []
        
        # Если в первом сообщении был не токен, а вопрос - обрабатываем его сразу
        if 'first_message_text' in locals():
            # Обрабатываем вопрос
            report = process_question(first_message_text, agent_model, user_id=user_id)
            
            chat_history.append({
                "question": first_message_text,
                "answer": report.answer
            })
            
            await ws.send_text(json.dumps({
                "content": report_to_markdown(report)
            }))
        
        # Продолжаем слушать следующие сообщения
        while True:
            try:
                question = await ws.receive_text()
                
                # Обрабатываем вопрос с учетом user_id
                report = process_question(question, agent_model, user_id=user_id)
                
                chat_history.append({
                    "question": question,
                    "answer": report.answer
                })
                
                await ws.send_text(json.dumps({
                    "content": report_to_markdown(report)
                }))
            except Exception as e:
                # Если клиент отключился (при выходе), просто выходим из цикла
                print(f"Клиент отключился: {e}")
                break
            
    except Exception as e:
        print(f"Ошибка WebSocket: {e}")
    finally:
        # Закрываем соединение, если оно ещё открыто
        try:
            await ws.close()
        except:
            pass

# ============================================
# ЭНДПОИНТЫ ДЛЯ АВТОРИЗАЦИИ
# ============================================

@app.post("/auth/register", response_model=UserResponse)
async def register(user_data: UserCreate):
    """
    РЕГИСТРАЦИЯ НОВОГО ПОЛЬЗОВАТЕЛЯ
    
    Как проверить в Postman:
    POST http://localhost:8080/auth/register
    Headers: Content-Type: application/json
    Body:
    {
        "username": "анна",
        "email": "anna@mail.ru",
        "password": "12345"
    }
    
    Что происходит:
        1. Получаем данные от пользователя
        2. Пытаемся создать пользователя в БД
        3. Если успешно - возвращаем его данные
        4. Если нет - возвращаем ошибку
    """
    try:
        # Создаем пользователя
        user_id = db.create_user(
            username=user_data.username,
            email=user_data.email,
            password=user_data.password
        )
        
        # Получаем созданного пользователя (без пароля)
        user = db.get_user_by_id(user_id)
        return user
        
    except ValueError as e:
        # Если пользователь уже существует
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auth/login", response_model=TokenResponse)
async def login(user_data: UserLogin):
    """
    ВХОД ПОЛЬЗОВАТЕЛЯ
    
    POST http://localhost:8080/auth/login
    Body:
    {
        "username": "анна",
        "password": "12345"
    }
    
    Что происходит:
        1. Проверяем логин и пароль
        2. Если всё ок - создаем сессию (токен)
        3. Возвращаем токен и данные пользователя
    """
    # Проверяем пароль
    user = db.authenticate_user(user_data.username, user_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Неверное имя пользователя или пароль"
        )
    
    # Создаем сессию (токен)
    token = db.create_session(user['id'])
    
    # Возвращаем токен и данные
    return {
        "access_token": token,
        "user": user
    }

@app.post("/auth/logout")
async def logout(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: dict = Depends(get_current_user)
):
    """
    Выход из системы с подробным ответом
    """
    try:
        token = credentials.credentials
        print(f"Получен токен для выхода: {token[:20]}...")  # для отладки
        
        # Удаляем сессию
        deleted = db.delete_session(token)
        
        if deleted:
            return {
                "success": True,
                "message": "Вы успешно вышли из системы",
                "deleted": True
            }
        else:
            return {
                "success": True,
                "message": "Сессия не найдена (возможно уже удалена)",
                "deleted": False
            }
    except Exception as e:
        print(f"Ошибка при выходе: {e}")
        return {
            "success": False,
            "message": "Ошибка при выходе из системы",
            "error": str(e)
        }

@app.get("/users/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """
    ПОЛУЧИТЬ ДАННЫЕ ТЕКУЩЕГО ПОЛЬЗОВАТЕЛЯ
    
    GET http://localhost:8080/users/me
    Headers: Authorization: Bearer <ваш_токен>
    
    Используется, чтобы проверить, авторизован ли пользователь
    """
    return current_user

# ============================================
# СТРАНИЧКИ ДЛЯ БРАУЗЕРА (НОВЫЕ)
# ============================================

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    """
    Страница входа
    Просто читаем файл login.html и отдаем браузеру
    """
    with open("login.html", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/register", response_class=HTMLResponse)
async def register_page():
    """
    Страница регистрации
    """
    with open("register.html", encoding="utf-8") as f:
        return HTMLResponse(f.read())

# ВАЖНО: существующие эндпоинты (/upload, /documents и т.д.) 
# ПОКА НЕ ТРОГАЕМ! Они продолжат работать с user_id="default"

@app.get("/debug-token")
async def debug_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Временный эндпоинт для проверки токена"""
    token = credentials.credentials
    user = db.get_user_by_token(token)
    if user:
        return {"valid": True, "user": user}
    else:
        return {"valid": False, "token": token[:20] + "..."}
    

# ============================================
# АДМИН-ПАНЕЛЬ (НОВЫЕ ЭНДПОИНТЫ)
# ============================================

@app.get("/admin/users")
async def admin_get_users(
    current_admin: dict = Depends(get_current_admin)
):
    """
    ПОЛУЧИТЬ ВСЕХ ПОЛЬЗОВАТЕЛЕЙ
    
    GET http://localhost:8080/admin/users
    Headers: Authorization: Bearer <токен_админа>
    
    Возвращает список всех пользователей с их документами
    """
    try:
        users = db.get_all_users()  # Эту функцию создадим в db.py
        return {"users": users}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/admin/users/{user_id}/role")
async def admin_change_role(
    user_id: int,
    new_role: str,
    current_admin: dict = Depends(get_current_admin)
):
    """
    ИЗМЕНИТЬ РОЛЬ ПОЛЬЗОВАТЕЛЯ
    
    PATCH http://localhost:8080/admin/users/5/role?new_role=admin
    """
    if new_role not in ['user', 'admin']:
        raise HTTPException(status_code=400, detail="Роль может быть только 'user' или 'admin'")
    
    # ЗАЩИТА: админ не может понизить самого себя
    if user_id == current_admin['id'] and new_role != 'admin':
        raise HTTPException(
            status_code=400,
            detail="Нельзя понизить роль самого себя"
        )
    
    try:
        updated = db.change_user_role(user_id, new_role)
        if not updated:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        return {"status": "ok", "user_id": user_id, "new_role": new_role}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/documents")
async def admin_get_documents(
    current_admin: dict = Depends(get_current_admin)
):
    """
    ПОЛУЧИТЬ ВСЕ ДОКУМЕНТЫ С ИНФОРМАЦИЕЙ О ВЛАДЕЛЬЦАХ
    
    GET http://localhost:8080/admin/documents
    """
    try:
        documents = db.get_all_documents_admin()  # Эту функцию создадим в db.py
        return {"documents": documents}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/admin/documents/{document_id}")
async def admin_delete_document(
    document_id: int,
    current_admin: dict = Depends(get_current_admin)
):
    """
    УДАЛИТЬ ЛЮБОЙ ДОКУМЕНТ (независимо от владельца)
    
    DELETE http://localhost:8080/admin/documents/10
    """
    try:
        deleted = db.delete_any_document(document_id)  # Эту функцию создадим в db.py
        if not deleted:
            raise HTTPException(status_code=404, detail="Документ не найден")
        
        return {"status": "ok", "deleted_document_id": document_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ===== ОПЦИОНАЛЬНО: изменить роль пользователя =====
@app.patch("/admin/users/{user_id}/role")
async def admin_change_role(
    user_id: int,
    new_role: str,
    current_admin: dict = Depends(get_current_admin)
):
    """
    ИЗМЕНИТЬ РОЛЬ ПОЛЬЗОВАТЕЛЯ
    
    PATCH http://localhost:8080/admin/users/5/role?new_role=admin
    
    Внимание: new_role может быть только 'user' или 'admin'
    """
    if new_role not in ['user', 'admin']:
        raise HTTPException(status_code=400, detail="Роль может быть только 'user' или 'admin'")
    
    # Не даём админу понизить самого себя
    if user_id == current_admin['id'] and new_role != 'admin':
        raise HTTPException(
            status_code=400,
            detail="Нельзя изменить роль самого себя"
        )
    
    try:
        # Эту функцию тоже создадим в db.py
        updated = db.change_user_role(user_id, new_role)
        if not updated:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        return {"status": "ok", "user_id": user_id, "new_role": new_role}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    """
    Страница админ-панели
    """
    with open("admin.html", encoding="utf-8") as f:
        return HTMLResponse(f.read())
    
@app.get("/my-documents", response_class=HTMLResponse)
async def my_documents_page():
    """
    Страница "Мои документы"
    """
    with open("my-documents.html", encoding="utf-8") as f:
        return HTMLResponse(f.read())

if __name__ == "__main__":
    import uvicorn
    import sys
    
    try:
        uvicorn.run(
            "main:app",
            host="localhost",
            port=8080,
            reload=True
        )
    except KeyboardInterrupt:
        # Перехватываем Ctrl+C и выходим чисто
        print("Сервер остановлен")
        sys.exit(0)
    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)