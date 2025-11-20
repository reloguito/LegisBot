from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base
from .routers import auth_router, chat_router, admin_router

# Crear tablas en la base de datos (al inicio)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LegisBot API",
    description="API para gestionar usuarios, chat RAG y analíticas.",
    version="1.0.0"
)

# Configuración de CORS
# Esto es crucial para que tu frontend en React pueda comunicarse con el backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, cámbialo a la URL de tu frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir routers
app.include_router(auth_router.router, prefix="/api/auth", tags=["Autenticación"])
app.include_router(chat_router.router, prefix="/api/chat", tags=["Chatbot"])
app.include_router(admin_router.router, prefix="/api/admin", tags=["Administrador"])

@app.get("/api/health", tags=["General"])
def read_root():
    """Verifica el estado de la API."""
    return {"status": "ok"}
