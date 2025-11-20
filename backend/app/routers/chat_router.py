from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List

from .. import schemas, models, database
from ..services import auth_service, rag_service

router = APIRouter()

# ### CAMBIO IMPORTANTE: Agregamos 'async' antes de def
@router.post("/query", response_model=schemas.ChatResponse)
async def handle_chat_query(
    request: schemas.ChatRequest,
    current_user: models.User = Depends(auth_service.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Recibe una consulta del usuario, la procesa con RAG de forma ASÍNCRONA y devuelve una respuesta.
    """
    try:
        # 1. Obtener o crear historial de chat (Operaciones DB síncronas son rápidas, está bien dejarlas así)
        if request.history_id:
            history = db.query(models.ChatHistory).filter(
                models.ChatHistory.id == request.history_id,
                models.ChatHistory.user_id == current_user.id
            ).first()
            if not history:
                raise HTTPException(status_code=404, detail="Historial de chat no encontrado")
        else:
            history = models.ChatHistory(user_id=current_user.id)
            db.add(history)
            db.commit()
            db.refresh(history)
        
        # 2. Loguear pregunta del usuario
        rag_service.log_chat_message(db, history.id, models.SenderType.user, request.query)
        
        # 3. Obtener documentos relevantes (Esto sigue siendo síncrono en el servicio porque es rápido)
        sources = rag_service.get_relevant_documents(request.query)
        
        # ### CAMBIO CRÍTICO: Eliminamos chain.invoke() y usamos la nueva función asíncrona
        # Esto libera al servidor para atender a otros mientras la IA "piensa".
        answer = await rag_service.generate_rag_response(request.query)
        
        # 4. Loguear respuesta del bot
        rag_service.log_chat_message(db, history.id, models.SenderType.bot, answer, sources)
        
        return schemas.ChatResponse(
            answer=answer,
            sources=sources,
            history_id=history.id
        )

    except Exception as e:
        print(f"Error en endpoint /query: {e}") # Buen log para debug
        raise HTTPException(status_code=500, detail=f"Error al procesar la consulta: {str(e)}")


@router.get("/history", response_model=List[schemas.ChatHistory])
def get_user_chat_history(
    current_user: models.User = Depends(auth_service.get_current_user),
    db: Session = Depends(database.get_db)
):
    """Obtiene todos los historiales de chat del usuario."""
    # Este endpoint es pura base de datos, puede quedarse síncrono (def) sin problemas.
    histories = db.query(models.ChatHistory).filter(models.ChatHistory.user_id == current_user.id).all()
    return histories


# ### CAMBIO IMPORTANTE: Agregamos 'async'
@router.post("/upload-context", status_code=status.HTTP_201_CREATED)
async def upload_context_documents(
    files: List[UploadFile] = File(...),
    admin_user: models.User = Depends(auth_service.get_current_admin_user),
    db: Session = Depends(database.get_db)
):
    """
    (Solo Admin) Sube archivos PDF.
    AHORA ES ASÍNCRONO para permitir la carga de archivos grandes sin congelar la app.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No se enviaron archivos.")
        
    try:
        # ### CAMBIO CRÍTICO: Usamos 'await' porque el procesamiento de PDFs ahora es async
        processed = await rag_service.process_and_store_pdfs(files, db, admin_user.id)
        
        return {
            "message": f"Archivos procesados y añadidos al contexto: {', '.join(processed)}",
            "processed_files": processed
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar los archivos: {str(e)}")