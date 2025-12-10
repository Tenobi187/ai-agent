import uvicorn
import json
import re

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from openai import AsyncOpenAI
from loguru import logger

from config import GROQ_API_KEY, SYSTEM_PROMPT, TOOLS
from functions import run_comand, save_code, search, fetch_page

app = FastAPI()

openai_client = AsyncOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY
)

def clean_response(text: str) -> str:
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'^(AI:|Ассистент:|Bot:)\s*', '', text, flags=re.IGNORECASE)
    return text.strip()

@app.get("/")
async def index():
    with open("index.html", "r", encoding="UTF-8") as f:
        html = f.read()
    return HTMLResponse(html)

@app.get("/styles.css")
async def get_styles():
    with open("styles.css", "r", encoding="UTF-8") as f:
        return HTMLResponse(f.read(), media_type="text/css")

@app.get("/chat.js")
async def get_chat_js():
    with open("chat.js", "r", encoding="UTF-8") as f:
        return HTMLResponse(f.read(), media_type="application/javascript")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    chat_history = [{
        "role": "system",
        "content": SYSTEM_PROMPT
    }]

    try:
        while True:
            user_input = await websocket.receive_text()
            logger.info(f"Получено сообщение от пользователя: {user_input[:100]}...")
            
            chat_history.append({
                "role": "user",
                "content": user_input
            })

            logger.info("Отправляем запрос в Groq API...")
            
            try:
                ai_response = await openai_client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=chat_history,
                    tools=TOOLS,
                    tool_choice="auto",
                    temperature=0.7,
                    max_tokens=1024,
                    top_p=0.9,
                    frequency_penalty=0.1,
                    presence_penalty=0.1
                )

                ai_message = ai_response.choices[0].message
                
                chat_history.append({
                    "role": "assistant",
                    "content": ai_message.content or "",
                    "tool_calls": ai_message.tool_calls
                })

                if ai_message.tool_calls:
                    tool_results = []
                    
                    for tool_call in ai_message.tool_calls:
                        func_name = tool_call.function.name
                        args = json.loads(tool_call.function.arguments)
                        result = ""

                        try:
                            if func_name == "run_command":
                                if "input_str" in args:
                                    result = run_comand(args["command"], args["input_str"])
                                else:
                                    result = run_comand(args["command"])
                            elif func_name == "save_code":
                                result = save_code(args["code"], args["filename"])
                            elif func_name == "search":
                                result = search(args["query"])
                            elif func_name == "fetch_page":
                                result = await fetch_page(args["url"])
                            else:
                                result = f"Неизвестная функция {func_name}"
                        except Exception as e:
                            result = f"Ошибка вызова функции {func_name}: {str(e)}"
                        
                        tool_results.append(result)
                        
                        chat_history.append({
                            "role": "tool",
                            "content": result,
                            "tool_call_id": tool_call.id
                        })

                    final_response = await openai_client.chat.completions.create(
                        model="llama-3.1-8b-instant",
                        messages=chat_history,
                        temperature=0.7,
                        max_tokens=1024
                    )

                    final_message = final_response.choices[0].message.content
                    final_message = clean_response(final_message)
                    
                    chat_history.append({
                        "role": "assistant",
                        "content": final_message
                    })

                    await websocket.send_text(json.dumps({
                        "role": "assistant",
                        "content": final_message
                    }))
                    
                else:
                    ai_message_content = ai_message.content or ""
                    ai_message_content = clean_response(ai_message_content)
                    
                    chat_history[-1]["content"] = ai_message_content
                    
                    await websocket.send_text(json.dumps({
                        "role": "assistant",
                        "content": ai_message_content
                    }))
                
                logger.info(f"Ответ отправлен пользователю")
                
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