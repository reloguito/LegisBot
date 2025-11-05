from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from .database import Base
import datetime
import enum

class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.user, nullable=False)
    has_completed_onboarding = Column(Boolean, default=False , nullable=False)

    profile = relationship("OnboardingProfile", back_populates="user", uselist=False)
    chat_histories = relationship("ChatHistory", back_populates="user")

class OnboardingProfile(Base):
    __tablename__ = "onboarding_profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    nombre = Column(String, nullable=False)
    apellido = Column(String, nullable=False)
    pais = Column(String, index=True)
    provincia = Column(String)
    localidad = Column(String)
    edad = Column(Integer)
    profesion = Column(String, index=True)
    
    user = relationship("User", back_populates="profile")

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    upload_date = Column(DateTime, default=datetime.datetime.utcnow)
    admin_id = Column(Integer, ForeignKey("users.id"))

class ChatHistory(Base):
    __tablename__ = "chat_histories"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="chat_histories")
    messages = relationship("Message", back_populates="history", order_by="Message.id")

class SenderType(str, enum.Enum):
    user = "user"
    bot = "bot"

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    history_id = Column(Integer, ForeignKey("chat_histories.id"))
    sender = Column(SQLEnum(SenderType), nullable=False)
    content = Column(String, nullable=False)
    sources = Column(JSON, nullable=True) # Para guardar de dónde sacó la info el RAG
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    history = relationship("ChatHistory", back_populates="messages")