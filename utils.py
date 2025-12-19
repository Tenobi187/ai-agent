# Вспомогательные функции

import re
from typing import List, Set
from config import IGNORED_PREFIXES, RELATED_CONCEPTS


def extract_semantic_chunks(text: str, chunk_size: int = 500) -> List[str]:
    """Разбивает текст на смысловые чанки"""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    chunks = []
    current_chunk = []
    current_length = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        sentence_length = len(sentence)
        
        if current_length == 0 or current_length + sentence_length < chunk_size:
            current_chunk.append(sentence)
            current_length += sentence_length
        else:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
            current_chunk = [sentence]
            current_length = sentence_length
    
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    return chunks


def extract_sources_from_results(search_results: str) -> List[str]:
    """Извлекает список источников из результатов поиска"""
    sources = set()
    lines = search_results.split('\n')
    
    for line in lines:
        if line.startswith("Файл: "):
            filename = line.replace("Файл: ", "").strip()
            sources.add(filename)
    
    return sorted(sources)


def should_skip_file(filename: str) -> bool:
    """Проверяет, нужно ли пропускать файл"""
    for prefix in IGNORED_PREFIXES:
        if filename.startswith(prefix):
            return True
    return False


def extract_keywords(question: str) -> List[str]:
    """Извлекает ключевые слова из вопроса"""
    normalized = question.lower()
    normalized = re.sub(r"[^a-zа-я0-9ё\s]", " ", normalized)

    stop_words = {
        "кто", "что", "где", "когда", "почему", "как",
        "какая", "какой", "какие", "чем", "зачем",
        "откуда", "куда", "чему", "на", "в", "о", "об", "про",
        "за", "до", "из", "по", "при", "там", "тут", "этот", "эта", "это",
    }

    words = normalized.split()
    base_keywords = [word for word in words if word not in stop_words and len(word) > 2]

    expanded_keywords: List[str] = []
    for kw in base_keywords:
        expanded_keywords.append(kw)
        for key, related_list in RELATED_CONCEPTS.items():
            if kw == key or kw in related_list:
                expanded_keywords.extend(related_list)

    seen: Set[str] = set()
    result: List[str] = []
    for kw in expanded_keywords:
        if kw not in seen:
            seen.add(kw)
            result.append(kw)

    return result or base_keywords