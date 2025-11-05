from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from .models import UserRole, SenderType
import datetime

# --- Token (JWT) ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# --- Usuario y Autenticación ---
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str
    role: UserRole = UserRole.user
    has_completed_onboarding: bool = False

class UserInDB(UserBase):
    id: int
    role: UserRole
    has_completed_onboarding: bool
    class Config:
        orm_mode = True

class UserLogin(BaseModel):
    username: EmailStr # El email se usará como username
    password: str

# --- Onboarding ---
class OnboardingProfileBase(BaseModel):
    nombre: str
    apellido: str
    pais: str
    provincia: Optional[str] = None
    localidad: Optional[str] = None
    edad: Optional[int] = None
    profesion: Optional[str] = None

class OnboardingProfileCreate(OnboardingProfileBase):
    pass

class OnboardingProfile(OnboardingProfileBase):
    id: int
    user_id: int
    class Config:
        orm_mode = True

# --- Chat ---
class MessageBase(BaseModel):
    content: str
    sender: SenderType
    sources: Optional[List[Dict[str, Any]]] = None

class Message(MessageBase):
    id: int
    timestamp: datetime.datetime
    class Config:
        orm_mode = True

class ChatHistory(BaseModel):
    id: int
    created_at: datetime.datetime
    messages: List[Message]
    class Config:
        orm_mode = True

class ChatRequest(BaseModel):
    query: str
    history_id: Optional[int] = None # Para continuar una conversación

class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    history_id: int

# --- Admin ---
class DemographicStat(BaseModel):
    group: str
    count: int

class UsageStat(BaseModel):
    date: str
    count: int
