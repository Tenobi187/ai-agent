# Основная логика агента
import os
from typing import List, Dict, Optional
from langchain_groq import ChatGroq
from langchain_core.tools import tool

from config import SUPPORTED_EXTENSIONS, MAX_SEARCH_RESULTS, MESSAGES
from utils import extract_sources_from_results, should_skip_file
from prompts import SEARCH_AGENT_PROMPT
from document_reader import read_document, semantic_search
from schemas import ResearchReport
from db import get_user_documents


@tool
def search_in_notes(query: str) -> str:
    """
    Умный поиск информации в заметках к книге.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    
    all_results = []
    
    for filename in os.listdir(parent_dir):
        file_path = os.path.join(parent_dir, filename)
        
        if os.path.isdir(file_path) or should_skip_file(filename):
            continue
            
        ext = os.path.splitext(filename)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue
            
        content = read_document(file_path)
        if not content:
            continue
        
        file_results = semantic_search(query, content, filename)
        all_results.extend(file_results)
    
    if not all_results:
        return f"ИНФОРМАЦИЯ: {MESSAGES['no_info']}"
    
    all_results.sort(key=lambda x: x["relevance_score"], reverse=True)
    
    top_results = all_results[:MAX_SEARCH_RESULTS]

    structured_results = []
    for i, result in enumerate(top_results, 1):
        structured_result = f"""
РЕЗУЛЬТАТ {i}:
Файл: {result['filename']}
Релевантность: {result['relevance_score']}
---
{result['context']}
---"""
        structured_results.append(structured_result)
    
    return "\n".join(structured_results)


def search_in_user_storage(query: str, user_id: str) -> str:
    """
    Поиск информации в загруженных пользователем документах (через БД).
    Формат результата такой же, как у search_in_notes.
    """
    all_results: List[Dict] = []

    docs = get_user_documents(user_id)
    for doc in docs:
        filename = doc["filename"]
        content = doc["content"] or ""
        if not content:
            continue

        file_results = semantic_search(query, content, filename)
        all_results.extend(file_results)

    if not all_results:
        return f"ИНФОРМАЦИЯ: {MESSAGES['no_info']}"

    all_results.sort(key=lambda x: x["relevance_score"], reverse=True)
    top_results = all_results[:MAX_SEARCH_RESULTS]

    structured_results = []
    for i, result in enumerate(top_results, 1):
        structured_result = f"""
РЕЗУЛЬТАТ {i}:
Файл: {result['filename']}
Релевантность: {result['relevance_score']}
---
{result['context']}
---"""
        structured_results.append(structured_result)
    
    return "\n".join(structured_results)


def create_agent_model():
    """Создает модель агента"""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("Ошибка: Установите переменную окружения GROQ_API_KEY")
        return None
    
    model = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.1,
        groq_api_key=api_key
    )
    
    return model


def analyze_and_synthesize(question: str, search_results: str, model):
    """Анализирует результаты поиска и синтезирует ответ"""
    
    prompt = SEARCH_AGENT_PROMPT.format(
        question=question,
        search_results=search_results
    )
    
    try:
        response = model.invoke(prompt)
        if hasattr(response, 'content'):
            response_text = response.content
        elif isinstance(response, dict) and 'content' in response:
            response_text = response['content']
        elif isinstance(response, str):
            response_text = response
        else:
            response_text = str(response)
    except Exception as e:
        response_text = f"Ошибка при генерации ответа: {str(e)}"
    
    return response_text


def process_question(question: str, model, user_id: Optional[str] = None) -> ResearchReport:
    """
    Обрабатывает один вопрос:
    - выполняет поиск по заметкам
    - анализирует результаты с помощью модели
    - возвращает структурированный ResearchReport
    """
    if user_id:
        search_results = search_in_user_storage(question, user_id)
    else:
        search_results = search_in_notes.invoke(question)

    response = analyze_and_synthesize(question, search_results, model)
    sources = extract_sources_from_results(search_results)

    return ResearchReport(
        topic=question,
        answer=response,
        sources=sources
    )


def run_agent():
    """Запускает основной цикл агента"""
    model = create_agent_model()
    if not model:
        return
    
    print(MESSAGES["welcome"])
    print("\n" + MESSAGES["features"])
    print("\n" + MESSAGES["agent_ready"])
    print("=" * 60)
    
    while True:
        try:
            question = input("\nВаш вопрос: ").strip()
            
            if question.lower() in ['выход', 'quit', 'exit', 'q']:
                print("\n" + MESSAGES["goodbye"])
                break
            
            if not question:
                continue
            
            print(MESSAGES["searching"])
            report = process_question(question, model)
            
            print(f"\nОТВЕТ НА ВОПРОС: '{question}'")
            print("=" * 60)
            print(report.answer)
            print("=" * 60)
            
            print("\n" + MESSAGES["sources"])
            if report.sources:
                for i, source in enumerate(report.sources, 1):
                    print(f"  {i}. {source}")
            else:
                print("  " + MESSAGES["no_sources"])
            
        except KeyboardInterrupt:
            print("\n" + MESSAGES["interrupted"])
            break
        except Exception as e:
            print(f"\n{MESSAGES['error']} {e}")