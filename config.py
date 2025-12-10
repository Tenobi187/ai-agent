import os

from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

SYSTEM_PROMPT= """
Ты полезный, дружелюбный и профессиональный ИИ-ассистент.
Твоя задача - помогать пользователю с различными вопросами, отвечать понятно и развернуто.
Будь вежливым, но не слишком формальным.
Если не знаешь ответа - честно скажи об этом.
Отвечай на русском языке, если пользователь пишет на русском.

1. **Заголовки** - используй #, ##, ### для структуры
2. **Выделение** - используй **жирный**, *курсив*, `код внутри строки`
3. **Списки** - используй * для маркированных и 1. для нумерованных
4. **Код** - всегда оборачивай код в блоки с указанием языка:
   ```python

   Цитаты - используй > для цитирования

Таблицы - используй Markdown таблицы когда уместно

Разделители - используй --- для разделения секций

ПРАВИЛА:

Отвечай на языке пользователя (русский/английский)

Будь точным, но понятным

Разбивай сложные ответы на логические части

Для кода всегда указывай язык в блоках кода

Используй эмодзи умеренно для лучшей читаемости

Если пишешь инструкции - делай их пошаговыми

Для примеров кода добавляй пояснения

Используй таблицы для сравнения или структурированных данных

"""

TOOLS = [
   {
      "type": "function",
      "function": {
      "name": "run_command",
      "description": "Выполняет команду в терминале или в командной строке и возвращает ответ",
      "parameters": {
         "type": "object",
         "properties": {
               "command": {
                  "type": "string",
                  "description": "Команда для выполнения в консоли, пример 'python script.py'"
               },
               "input_str": {
                  "type": "string",
                  "description": "Входные данные для скрипта, если они необходимы. Пример: value1, value2"
               }
         },
         "required": ["command"],
         
      },

      },
      "returns": {
         "type": "string",
         "description": "Вывод из терминала выполненного кода, stdout и stderr"
      }
   },
   {
     "type": "function",
     "function": {
        "name": "save_code",
        "description": "Сохраняет код в файл в директории ./ai",
      "parameters": {
         "type": "object",
         "properties": {
               "code": {
                  "type": "string",
                  "description": "Содержимое файла"
               },
               "filename": {
                  "type": "string",
                  "description": "Имя файла"
               }
         },
         "required": ["code", "filename"],

      },
      }
   },
   {
      "type": "function",
      "function": {
      "name": "search",
      "description": "Выполняет команду на поисковую систему для получения информации из интернета",
      "parameters": {
         "type": "object",
         "properties": {
               "query": {
                  "type": "string",
                  "description": "Текстовый запрос в поисковую систему"
               }
         },
         "required": ["query"]
         
      }
      },
   },
   {
      "type": "function",
      "function": {
      "name": "fetch_page",
      "description": "Открывает веб страницу и получает контент body из html стрктуры, без iframe, svg и style",
      "parameters": {
         "type": "object",
         "properties": {
               "url": {
                  "type": "string",
                  "description": "Ссылка для посещения веб-сайта"
               }
         },
         "required": ["url"]
      }
      }
   }
]
