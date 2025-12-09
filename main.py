import uvicorn
import json
import re

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from openai import AsyncOpenAI
from loguru import logger

from config import GROQ_API_KEY, SYSTEM_PROMPT

app = FastAPI()

# Инициализация клиента OpenAI для Groq
openai_client = AsyncOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY
)

def clean_response(text: str) -> str:
    """Очистка и форматирование ответа от лишних символов"""
    # Убираем лишние пробелы и переносы
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Убираем маркеры начала/конца от ИИ (если есть)
    text = re.sub(r'^(AI:|Ассистент:|Bot:)\s*', '', text, flags=re.IGNORECASE)
    return text.strip()

@app.get("/")
async def index():
    """Отдаем HTML-страницу"""
    with open("index.html", "r", encoding="UTF-8") as f:
        html = f.read()
    return HTMLResponse(html)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket-эндпоинт для общения с ИИ"""
    await websocket.accept()
    
    # История диалога начинается с системного промпта
    chat_history = [{
        "role": "system",
        "content": SYSTEM_PROMPT
    }]

    try:
        while True:
            # Получаем сообщение от пользователя
            user_input = await websocket.receive_text()
            logger.info(f"Получено сообщение от пользователя: {user_input[:100]}...")
            
            # Добавляем в историю
            chat_history.append({
                "role": "user",
                "content": user_input
            })

            # Получаем ответ от Groq API
            logger.info("Отправляем запрос в Groq API...")
            
            try:
                ai_response = await openai_client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=chat_history,
                    temperature=0.7,
                    max_tokens=1024,
                    top_p=0.9,
                    frequency_penalty=0.1,
                    presence_penalty=0.1
                )

                # Извлекаем текст ответа
                ai_message = ai_response.choices[0].message.content
                ai_message = clean_response(ai_message)
                
                logger.info(f"Получен ответ от ИИ длиной {len(ai_message)} символов")
                
                # Добавляем ответ в историю
                chat_history.append({
                    "role": "assistant",
                    "content": ai_message
                })

                # Отправляем ответ пользователю
                await websocket.send_text(json.dumps({
                    "role": "assistant",
                    "content": ai_message
                }))
                logger.info("Ответ отправлен пользователю")
                
            except Exception as api_error:
                logger.error(f"Ошибка Groq API: {api_error}")
                error_message = f"**⚠️ Ошибка API**\n\nПроизошла ошибка при обращении к ИИ:\n```\n{str(api_error)}\n```\n\nПожалуйста, попробуйте еще раз."
                
                await websocket.send_text(json.dumps({
                    "role": "assistant",
                    "content": error_message
                }))

    except WebSocketDisconnect:
        logger.info("Клиент отключился от WebSocket")
    except Exception as e:
        logger.error(f"Ошибка в WebSocket: {e}")
        try:
            await websocket.send_text(json.dumps({
                "role": "assistant",
                "content": f"**❌ Системная ошибка**\n\n```\n{str(e)}\n```"
            }))
        except:
            pass

if __name__ == "__main__":
    logger.info("Запуск сервера на localhost:8000")
    uvicorn.run(
        "main:app",
        host="localhost",
        port=8000,
        reload=True,
        log_level="info"
    )