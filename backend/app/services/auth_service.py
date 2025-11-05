from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional

from .. import models, schemas, database, config

settings = config.settings

# Contexto de Passlib para hashear contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Esquema OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

# --- Funciones de Utilidad ---

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

# --- Lógica de Base de Datos ---

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        email=user.email, 
        hashed_password=hashed_password, 
        role=user.role,
        has_completed_onboarding=user.has_completed_onboarding
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def create_onboarding_profile(db: Session, profile: schemas.OnboardingProfileCreate, user_id: int):
    # Verificar si ya existe un perfil
    existing_profile = db.query(models.OnboardingProfile).filter(models.OnboardingProfile.user_id == user_id).first()
    if existing_profile:
        # Actualizar el perfil existente
        for key, value in profile.dict().items():
            setattr(existing_profile, key, value)
        db_profile = existing_profile
    else:
        # Crear un nuevo perfil
        db_profile = models.OnboardingProfile(**profile.dict(), user_id=user_id)
        db.add(db_profile)
    
    # Actualizar el campo 'has_completed_onboarding' del usuario
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user and not user.has_completed_onboarding:
        user.has_completed_onboarding = True

    db.commit()
    db.refresh(db_profile)
    return db_profile

# --- Dependencias de Autenticación ---

async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: Session = Depends(database.get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = schemas.TokenData(email=email)
    except JWTError:
        raise credentials_exception
    
    user = get_user_by_email(db, email=token_data.email)
    if user is None:
        raise credentials_exception
    return user

async def get_current_admin_user(
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role != models.UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos de administrador"
        )
    return current_user