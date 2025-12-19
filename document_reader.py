# Чтение документов и функции поиска
import os
import json
from typing import List, Dict
import PyPDF2
from docx import Document

from config import SUPPORTED_EXTENSIONS, CHUNK_SIZE
from utils import extract_semantic_chunks, should_skip_file, extract_keywords


def read_document(file_path: str) -> str:
    """Читает содержимое документа разных форматов"""
    filename = os.path.basename(file_path)
    
    if should_skip_file(filename):
        return ""
    
    ext = os.path.splitext(file_path)[1].lower()
    
    try:
        if ext == '.pdf':
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                content = []
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    if text:
                        content.append(text)
                return "\n".join(content)
        
        elif ext == '.docx':
            doc = Document(file_path)
            return "\n".join([para.text for para in doc.paragraphs])
        
        elif ext in ['.txt', '.md']:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        elif ext == '.json':
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return json.dumps(data, ensure_ascii=False, indent=2)
        
        else:
            return ""
            
    except Exception as e:
        if not should_skip_file(filename):
            print(f"Ошибка чтения {file_path}: {e}")
        return ""


def semantic_search(query: str, content: str, filename: str) -> List[Dict]:
    """Умный семантический поиск по контенту"""
    query_lower = query.lower()
    
    keywords = extract_keywords(query)
    
    chunks = extract_semantic_chunks(content, CHUNK_SIZE)
    results = []
    
    for chunk_idx, chunk in enumerate(chunks):
        chunk_lower = chunk.lower()
        
        relevance_score = 0
        
        for keyword in keywords:
            if keyword in chunk_lower:
                position = chunk_lower.find(keyword)
                if position != -1:
                    position_bonus = max(0, 100 - position)
                    relevance_score += 1 + (position_bonus / 100)
        
        if len(keywords) >= 2:
            for i in range(len(keywords) - 1):
                bigram = f"{keywords[i]} {keywords[i+1]}"
                if bigram in chunk_lower:
                    relevance_score += 3
        
        query_words = query.split()
        for word in query_words:
            if word and word[0].isupper() and len(word) > 1:
                if word.lower() in chunk_lower:
                    relevance_score += 2

        if relevance_score > 0:
            chunk_start = max(0, chunk_idx - 1)
            chunk_end = min(len(chunks), chunk_idx + 2)
            
            context_parts = []
            for i in range(chunk_start, chunk_end):
                if i == chunk_idx:
                    context_parts.append(f"[НАЙДЕННОЕ] {chunks[i]}")
                else:
                    context_parts.append(chunks[i])
            
            context_text = "\n[...]\n".join(context_parts)
            
            found_keywords = [kw for kw in keywords if kw in chunk_lower]
            
            results.append({
                "filename": filename,
                "relevance_score": round(relevance_score, 2),
                "found_words": found_keywords[:5], 
                "context": context_text,
                "chunk_index": chunk_idx
            })
    
    return results