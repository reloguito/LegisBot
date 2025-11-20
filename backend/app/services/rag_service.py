import shutil
import tempfile
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session

# --- Imports actualizados de LangChain ---
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document

# Imports internos
from .. import models, config

settings = config.settings

# --- 1. Configuración e Inicialización Lazy (Perezosa) ---
# Inicializamos las variables como None para evitar errores si Ollama está apagado al arrancar.
_vector_store = None
_ollama_llm = None
_retriever = None

def get_llm():
    """Singleton para obtener la instancia del LLM"""
    global _ollama_llm
    if _ollama_llm is None:
        try:
            _ollama_llm = ChatOllama(
                base_url=settings.OLLAMA_BASE_URL,
                model=settings.OLLAMA_MODEL,
                temperature=0.3  # Menor temperatura para respuestas más factuales
            )
        except Exception as e:
            print(f"Error conectando a Ollama: {e}")
    return _ollama_llm

def get_vector_store():
    """Singleton para obtener la instancia de ChromaDB"""
    global _vector_store
    if _vector_store is None:
        try:
            embeddings = OllamaEmbeddings(
                base_url=settings.OLLAMA_BASE_URL,
                model=settings.EMBEDDING_MODEL
            )
            _vector_store = Chroma(
                persist_directory=settings.CHROMA_PATH,
                embedding_function=embeddings
            )
        except Exception as e:
            print(f"Error inicializando ChromaDB: {e}")
    return _vector_store

def get_retriever():
    """Obtiene el retriever configurado"""
    global _retriever
    vs = get_vector_store()
    if vs and _retriever is None:
        # Aumentamos k a 5 pero reducimos el chunk size en la ingesta
        _retriever = vs.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 5} 
        )
    return _retriever

# --- 2. Plantilla de Prompt Mejorada ---
RAG_TEMPLATE = """
Eres "LegislatiBot", un asistente especializado en análisis legislativo del Senado.

INSTRUCCIONES:
1. Basa tu respuesta ÚNICAMENTE en el contexto proporcionado abajo.
2. Si la respuesta no está en el contexto, di: "La información solicitada no se encuentra en los documentos disponibles."
3. Cita el nombre del documento fuente si es relevante.

CONTEXTO:
{context}

PREGUNTA DEL USUARIO:
{question}

RESPUESTA:
"""

rag_prompt = ChatPromptTemplate.from_template(RAG_TEMPLATE)


# --- 3. Funciones de Lógica RAG (Optimizadas) ---

async def process_and_store_pdfs(files: List[UploadFile], db: Session, admin_id: int):
    """
    Procesa PDFs de manera asíncrona.
    Optimización: Chunk size reducido para mejor precisión en recuperación.
    """
    vs = get_vector_store()
    if not vs:
        raise HTTPException(status_code=503, detail="El sistema vectorial no está disponible.")
        
    processed_files = []
    all_splits = []

    # Crear directorio temporal seguro
    with tempfile.TemporaryDirectory() as temp_dir:
        for file in files:
            temp_filepath = Path(temp_dir) / file.filename
            try:
                # Escritura asíncrona o eficiente
                content = await file.read()
                with open(temp_filepath, "wb") as buffer:
                    buffer.write(content)
                
                # Cargar PDF
                loader = PyPDFLoader(str(temp_filepath))
                docs = loader.load()
                
                # OPTIMIZACIÓN: Chunks más pequeños (1000 chars) con overlap
                # Esto mejora la precisión semántica para modelos locales.
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000, 
                    chunk_overlap=200,
                    add_start_index=True
                )
                splits = text_splitter.split_documents(docs)
                
                # Añadir metadata extra si es necesario
                for split in splits:
                    split.metadata["filename"] = file.filename
                    split.metadata["source"] = file.filename # Asegurar consistencia

                all_splits.extend(splits)
                
                # Registro SQL
                db_doc = models.Document(filename=file.filename, admin_id=admin_id)
                db.add(db_doc)
                processed_files.append(file.filename)

            except Exception as e:
                print(f"Error procesando {file.filename}: {e}")
                continue # No romper todo el proceso por un archivo corrupto
            finally:
                await file.close()

    if all_splits:
        print(f"Vectorizando {len(all_splits)} fragmentos...")
        # Add documents to Chroma (puede tardar, por eso async es util en el wrapper)
        vs.add_documents(documents=all_splits)
        # vs.persist() # NOTA: En versiones nuevas de Chroma (>0.4) la persistencia es automática.
        print("Vectorización finalizada.")
        db.commit()
    
    return processed_files

def format_docs(docs: List[Document]) -> str:
    """Formato limpio para inyectar en el prompt."""
    formatted = []
    for doc in docs:
        source = doc.metadata.get('filename', doc.metadata.get('source', 'Desconocido'))
        page = doc.metadata.get('page', '?')
        formatted.append(f"--- Documento: {source} (Pág {page}) ---\n{doc.page_content}")
    return "\n\n".join(formatted)

async def generate_rag_response(query: str):
    """
    Genera respuesta usando LCEL (LangChain Expression Language) de forma asíncrona.
    """
    llm = get_llm()
    retriever_instance = get_retriever()
    
    if not llm or not retriever_instance:
        raise HTTPException(status_code=503, detail="Servicio de IA no disponible.")

    # Cadena RAG definida con LCEL
    chain = (
        {"context": retriever_instance | format_docs, "question": RunnablePassthrough()}
        | rag_prompt
        | llm
        | StrOutputParser()
    )
    
    # Uso de ainvoke para no bloquear el servidor FastAPI
    response = await chain.ainvoke(query)
    return response

def get_relevant_documents(query: str) -> List[Dict[str, Any]]:
    """Recupera documentos para mostrar fuentes (síncrono es ok aquí, es rápido)."""
    retriever_instance = get_retriever()
    if not retriever_instance:
        return []
    
    docs = retriever_instance.invoke(query)
    sources = []
    for doc in docs:
        sources.append({
            "source": doc.metadata.get('filename', doc.metadata.get('source', 'N/A')),
            "page": doc.metadata.get('page', 'N/A'),
            "content_preview": doc.page_content[:200].replace('\n', ' ') + "..."
        })
    return sources

def log_chat_message(
    db: Session, 
    history_id: int, 
    sender: models.SenderType, 
    content: str, 
    sources: Optional[List[Dict[str, Any]]] = None
):
    """Guarda mensaje en SQL."""
    try:
        # Aseguramos que sources sea serializable o None
        sources_data = sources if sources else None
        
        db_message = models.Message(
            history_id=history_id,
            sender=sender,
            content=content,
            sources=sources_data 
        )
        db.add(db_message)
        db.commit()
        db.refresh(db_message)
        return db_message
    except Exception as e:
        db.rollback()
        print(f"Error logueando mensaje: {e}")
        return None