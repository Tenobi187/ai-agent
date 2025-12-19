# Основной файл запуска системы
import json
import uvicorn
from datetime import datetime
import os

from fastapi import FastAPI, WebSocket, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from dotenv import load_dotenv
from agent import create_agent_model, process_question
from schemas import ResearchReport
from db import init_db, save_document, list_documents, delete_document, delete_all_documents
from utils import extract_semantic_chunks

load_dotenv()

init_db()

app = FastAPI()
agent_model = create_agent_model()

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    with open("index.html", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Form("default"),
):
    """
    Загрузка документа в хранилище.
    Пока используем одного пользователя по умолчанию: user_id = 'default'.
    """
    
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
    doc_id = save_document(user_id=user_id, name=file.filename, chunks=chunks, created_at=created_at)

    return {
        "status": "ok",
        "document_id": doc_id,
        "chunks": len(chunks),
        "filename": file.filename,
    }


@app.get("/documents")
async def get_documents(user_id: str = "default"):
    """Список загруженных документов пользователя."""
    docs = list_documents(user_id)
    return {"user_id": user_id, "documents": docs}


@app.delete("/documents/{document_id}")
async def remove_document(document_id: int, user_id: str = "default"):
    """Удаление одного документа пользователя по id."""
    ok = delete_document(user_id, document_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return {"status": "ok", "deleted_id": document_id}

@app.delete("/documents")
async def remove_all_documents(user_id: str = "default"):
    """
    Полная очистка документов пользователя.
    Используется для сброса контекста и предотвращения конфликтов.
    """
    deleted_count = delete_all_documents(user_id)

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
    chat_history = []

    try:
        if agent_model is None:
            await ws.send_text(json.dumps({
                "content": "Ошибка: модель агента не инициализирована. Проверьте переменную окружения GROQ_API_KEY."
            }))
            return

        while True:
            question = await ws.receive_text()

            report = process_question(question, agent_model, user_id="default")
           
            chat_history.append({
                "question": question,
                "answer": report.answer
            })

            await ws.send_text(json.dumps({
                "content": report_to_markdown(report)
            }))

    except Exception as e:
        await ws.send_text(json.dumps({
            "content": f"Ошибка: {e}"
        }))

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="localhost",
        port=8000,
        reload=True
    )
