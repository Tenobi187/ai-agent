from pydantic import BaseModel, EmailStr
from typing import List, Optional

# ЭТО УЖЕ ЕСТЬ (НЕ ТРОГАЕМ)
class ResearchReport(BaseModel):
    topic: str
    answer: str
    sources: List[str]

# ========== ЭТО МЫ ДОБАВЛЯЕМ ==========

class UserCreate(BaseModel):
    """
    Данные, которые приходят при регистрации.
    FastAPI автоматически проверит, что все поля есть.
    """
    username: str
    email: EmailStr  # EmailStr сам проверит, что это похоже на email
    password: str

class UserLogin(BaseModel):
    """
    Данные для входа.
    """
    username: str
    password: str

class UserResponse(BaseModel):
    """
    Данные, которые мы отдаем после входа/регистрации.
    """
    id: int
    username: str
    email: str
    created_at: str
    role: str 
    

class TokenResponse(BaseModel):
    """
    Ответ при успешном входе.
    """
    access_token: str   # сам токен
    token_type: str = "bearer"  # тип токена (всегда bearer)
    user: UserResponse   # данные пользователя