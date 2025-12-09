import os
from dotenv import load_dotenv
load_dotenv()

print("OpenAI ключ:", "найден" if os.getenv("OPENAI_API_KEY") else "отсутствует")
print("Tavily ключ:", "найден" if os.getenv("TAVILY_API_KEY") else "отсутствует")
