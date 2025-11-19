import shutil
import tempfile
from pathlib import Path
from fastapi import UploadFile
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_classic.schema.runnable import RunnablePassthrough
from langchain_classic.schema.output_parser import StrOutputParser
from langchain_core.load import dumps, loads

from .. import models, schemas, config

settings = config.settings

# --- Inicialización de Modelos ---
# (Se inicializan aquí para reutilizarlos)

try:
    ollama_llm = ChatOllama(
        base_url=settings.OLLAMA_BASE_URL, 
        model=settings.OLLAMA_MODEL
    )
    
    ollama_embeddings = OllamaEmbeddings(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.EMBEDDING_MODEL
    )
    
    # Vector store persistente
    vector_store = Chroma(
        persist_directory=settings.CHROMA_PATH,
        embedding_function=ollama_embeddings
    )
    
    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 5} # Obtener 5 documentos relevantes
    )

    print("--- Modelos LLM y Vector Store inicializados ---")

except Exception as e:
    print(f"Error al inicializar modelos de Ollama o Chroma: {e}")
    print("Asegúrate de que Ollama esté corriendo y los modelos estén descargados.")
    ollama_llm = None
    retriever = None

# --- Plantilla de Prompt ---

RAG_PROMPT_TEMPLATE = """
Eres "LegislatiBot", un asistente legal experto. Tu tarea es responder preguntas basándote únicamente en el siguiente contexto extraído de documentos oficiales.
Si el contexto no contiene la respuesta, di explícitamente: "Lo siento, no tengo información sobre ese tema en los documentos proporcionados."
No inventes información. Sé claro y conciso.

CONTEXTO:
{context}

PREGUNTA:
{question}

RESPUESTA:
"""

rag_prompt = PromptTemplate.from_template(RAG_PROMPT_TEMPLATE)

# --- Funciones de Lógica RAG ---

def process_and_store_pdfs(files: List[UploadFile], db: Session, admin_id: int):
    """
    Procesa una lista de archivos PDF, los vectoriza y los guarda en ChromaDB.
    """
    if not ollama_llm:
        raise Exception("LLM o Vector Store no inicializados.")
        
    all_splits = []
    processed_files = []

    with tempfile.TemporaryDirectory() as temp_dir:
        for file in files:
            temp_filepath = Path(temp_dir) / file.filename
            try:
                # Guardar el PDF temporalmente
                with open(temp_filepath, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                
                # 1. Cargar el PDF
                loader = PyPDFLoader(str(temp_filepath))
                docs = loader.load()
                
                # 2. Dividir en chunks
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000, 
                    chunk_overlap=200
                )
                splits = text_splitter.split_documents(docs)
                all_splits.extend(splits)
                
                # Guardar en DB SQL
                db_doc = models.Document(filename=file.filename, admin_id=admin_id)
                db.add(db_doc)
                processed_files.append(file.filename)

            except Exception as e:
                print(f"Error procesando el archivo {file.filename}: {e}")
                # Opcional: manejar el error, tal vez devolverlo al usuario
            finally:
                file.file.close()

    # 3. Vectorizar y almacenar en Chroma
    if all_splits:
        print(f"Añadiendo {len(all_splits)} chunks a la base de datos vectorial...")
        vector_store.add_documents(documents=all_splits)
        vector_store.persist()
        print("Vectorización completada y persistida.")

    db.commit()
    return processed_files

def format_docs(docs: List[Any]) -> str:
    """Formatea los documentos recuperados para el prompt."""
    return "\n\n".join(
        f"Fuente: {doc.metadata.get('source', 'N/A')} (Página: {doc.metadata.get('page', 'N/A')})\nContenido: {doc.page_content}"
        for doc in docs
    )

def get_rag_chain():
    """Construye la cadena RAG."""
    if not ollama_llm or not retriever:
        raise HTTPException(status_code=503, detail="Servicio RAG no disponible. Verifica la conexión con Ollama.")
        
    return (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | rag_prompt
        | ollama_llm
        | StrOutputParser()
    )

def get_relevant_documents(query: str) -> List[Dict[str, Any]]:
    """Obtiene los documentos fuente para la cita."""
    if not retriever:
        return []
    
    docs = retriever.invoke(query)
    sources = []
    for doc in docs:
        sources.append({
            "source": doc.metadata.get('source', 'N/A'),
            "page": doc.metadata.get('page', 'N/A'),
            "content_preview": doc.page_content[:150] + "..."
        })
    return sources

def log_chat_message(
    db: Session, 
    history_id: int, 
    sender: models.SenderType, 
    content: str, 
    sources: Optional[List[Dict[str, Any]]] = None
):
    """Guarda un mensaje en la base de datos SQL."""
    db_message = models.Message(
        history_id=history_id,
        sender=sender,
        content=content,
        sources=sources
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message
