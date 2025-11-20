import shutil   # Utilidades para operaciones de alto nivel con archivos (copiar, mover).
import tempfile # Librería para crear directorios y archivos temporales que se borran solos.
import os       # Interacción con el sistema operativo (rutas, entorno).
from pathlib import Path # Manejo orientado a objetos de rutas de archivos (más moderno que os.path).
from typing import List, Dict, Any, Optional # Tipado estático para mejor documentación y autocompletado.

# Importaciones de FastAPI y SQLAlchemy
from fastapi import UploadFile, HTTPException # Manejo de archivos subidos y errores HTTP.
from sqlalchemy.orm import Session # Tipo de dato para la sesión de base de datos SQL.

# --- Imports actualizados de LangChain (El núcleo del RAG) ---
# Cargador específico para leer PDFs.
from langchain_community.document_loaders import PyPDFLoader 
# Herramienta para dividir texto en fragmentos (chunks) manteniendo contexto.
from langchain_text_splitters import RecursiveCharacterTextSplitter
# Base de datos vectorial (Vector Store) que usaremos.
from langchain_chroma import Chroma
# Conectores para el modelo local Ollama (Chat y Embeddings).
from langchain_ollama import ChatOllama, OllamaEmbeddings
# Clases para construir prompts (instrucciones al modelo).
from langchain_core.prompts import ChatPromptTemplate
# RunnablePassthrough permite pasar datos sin modificarlos en la cadena (pipeline).
from langchain_core.runnables import RunnablePassthrough
# Convierte la respuesta del modelo (objeto) a texto plano (string).
from langchain_core.output_parsers import StrOutputParser
# Objeto base que representa un documento en LangChain.
from langchain_core.documents import Document

# Imports internos de tu proyecto
from .. import models, config # Modelos de DB (SQL) y configuraciones generales.

# Cargamos la configuración (URLs, nombres de modelos, rutas)
settings = config.settings

# --- 1. Configuración e Inicialización Lazy (Perezosa) ---
# PATRÓN SINGLETON / LAZY LOADING:
# Definimos las variables globales como None al inicio.
# No conectamos inmediatamente para que la API arranque rápido 
# y no falle si Ollama está apagado en ese preciso segundo.
_vector_store = None
_ollama_llm = None
_retriever = None

def get_llm():
    """
    Singleton para obtener la instancia del LLM (ChatOllama).
    Si ya existe, la devuelve. Si no, la crea.
    """
    global _ollama_llm # Referenciamos la variable global.
    
    if _ollama_llm is None: # Si aún no se ha creado...
        try:
            # Instanciamos la conexión con el modelo local.
            _ollama_llm = ChatOllama(
                base_url=settings.OLLAMA_BASE_URL, # URL del servidor Ollama (ej. localhost:11434)
                model=settings.OLLAMA_MODEL,       # Modelo a usar (ej. llama3, mistral)
                temperature=0.3  # BAJA TEMPERATURA: Crucial para documentos legales. 
                                 # Reduce la creatividad y prioriza la fidelidad a los datos.
            )
        except Exception as e:
            # Capturamos errores de conexión para logging sin tumbar la app completa.
            print(f"Error conectando a Ollama: {e}")
            
    return _ollama_llm # Retornamos la instancia lista para usar.

def get_vector_store():
    """
    Singleton para obtener la instancia de ChromaDB.
    Aquí es donde se guardan y buscan los vectores (representaciones matemáticas del texto).
    """
    global _vector_store
    
    if _vector_store is None:
        try:
            # Configuración del modelo que convertirá texto a números (Embeddings).
            embeddings = OllamaEmbeddings(
                base_url=settings.OLLAMA_BASE_URL,
                model=settings.EMBEDDING_MODEL # Ej. nomic-embed-text
            )
            # Inicialización de ChromaDB apuntando a una carpeta local (persistencia).
            _vector_store = Chroma(
                persist_directory=settings.CHROMA_PATH, # Dónde se guardan los datos en disco.
                embedding_function=embeddings # Qué función usar para calcular vectores.
            )
        except Exception as e:
            print(f"Error inicializando ChromaDB: {e}")
            
    return _vector_store

def get_retriever():
    """
    Configura el 'Retriever' (el buscador).
    Transforma el VectorStore en una interfaz de búsqueda.
    """
    global _retriever
    
    vs = get_vector_store() # Obtenemos la DB vectorial.
    
    # Solo creamos el retriever si la DB cargó correctamente y el retriever no existe aún.
    if vs and _retriever is None:
        _retriever = vs.as_retriever(
            search_type="similarity", # Búsqueda por similitud coseno (estándar).
            search_kwargs={"k": 5}    # TOP-K: Recuperamos los 5 fragmentos más parecidos.
                                      # Aumentamos a 5 para tener más contexto legislativo.
        )
    return _retriever

# --- 2. Plantilla de Prompt Mejorada ---
# Definimos la personalidad y reglas estrictas para el bot.
RAG_TEMPLATE = """
Eres "LegislatiBot", un asistente especializado en análisis legislativo del Senado.

INSTRUCCIONES:
1. Basa tu respuesta ÚNICAMENTE en el contexto proporcionado abajo. (Evita alucinaciones externas)
2. Si la respuesta no está en el contexto, di: "La información solicitada no se encuentra en los documentos disponibles." (Honestidad del sistema)
3. Cita el nombre del documento fuente si es relevante. (Trazabilidad)

CONTEXTO:
{context}

PREGUNTA DEL USUARIO:
{question}

RESPUESTA:
"""

# Creamos el objeto Template de LangChain listo para recibir variables.
rag_prompt = ChatPromptTemplate.from_template(RAG_TEMPLATE)


# --- 3. Funciones de Lógica RAG (Optimizadas) ---

async def process_and_store_pdfs(files: List[UploadFile], db: Session, admin_id: int):
    """
    Procesa PDFs de manera asíncrona (ETL: Extract, Transform, Load).
    Recibe archivos crudos, extrae texto, vectoriza y guarda.
    """
    vs = get_vector_store()
    
    # Validación temprana: Si no hay DB vectorial, no podemos procesar nada.
    if not vs:
        raise HTTPException(status_code=503, detail="El sistema vectorial no está disponible.")
        
    processed_files = [] # Lista para guardar nombres de archivos exitosos.
    all_splits = []      # Lista acumuladora de todos los fragmentos de texto.

    # Context Manager: Crea una carpeta temporal que se autodestruye al salir del 'with'.
    # Esto es vital para no llenar el servidor de archivos basura.
    with tempfile.TemporaryDirectory() as temp_dir:
        
        for file in files: # Iteramos sobre cada archivo subido.
            # Construimos la ruta temporal completa.
            temp_filepath = Path(temp_dir) / file.filename
            
            try:
                # Lectura Asíncrona: 'await' libera el procesador mientras lee el archivo.
                content = await file.read()
                
                # Escribimos el contenido binario en la carpeta temporal.
                with open(temp_filepath, "wb") as buffer:
                    buffer.write(content)
                
                # --- FASE 1: EXTRAER ---
                # Usamos PyPDFLoader para leer el PDF desde la ruta temporal.
                loader = PyPDFLoader(str(temp_filepath))
                docs = loader.load() # Carga el texto en memoria.
                
                # --- FASE 2: TRANSFORMAR (CHUNKING) ---
                # Configuración crítica para RAG:
                # chunk_size=1000: Tamaño moderado. Ni muy corto (pierde sentido) ni muy largo (confunde al LLM).
                # chunk_overlap=200: Solapamiento para no cortar frases a la mitad entre chunks.
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000, 
                    chunk_overlap=200,
                    add_start_index=True # Guarda la posición del caracter inicial (útil para citas).
                )
                splits = text_splitter.split_documents(docs) # Ejecuta la división.
                
                # Enriquecimiento de Metadata:
                # Agregamos el nombre del archivo a cada fragmento para poder citarlo después.
                for split in splits:
                    split.metadata["filename"] = file.filename
                    split.metadata["source"] = file.filename 

                all_splits.extend(splits) # Agregamos a la lista maestra.
                
                # --- FASE 3: LOGGING EN SQL ---
                # Guardamos el registro administrativo en PostgreSQL (quién subió qué y cuándo).
                db_doc = models.Document(filename=file.filename, admin_id=admin_id)
                db.add(db_doc)
                processed_files.append(file.filename)

            except Exception as e:
                print(f"Error procesando {file.filename}: {e}")
                continue # Si falla un archivo, seguimos con el siguiente (Resiliencia).
            finally:
                await file.close() # Cerramos el descriptor de archivo siempre.

    # --- FASE 4: CARGAR (VECTORIZACIÓN) ---
    if all_splits:
        print(f"Vectorizando {len(all_splits)} fragmentos...")
        # Esta línea es la pesada: envía textos al modelo de embeddings y guarda vectores en Chroma.
        vs.add_documents(documents=all_splits)
        print("Vectorización finalizada.")
        
        db.commit() # Confirmamos los cambios en PostgreSQL solo si la vectorización funcionó.
    
    return processed_files

def format_docs(docs: List[Document]) -> str:
    """
    Función auxiliar para limpiar y formatear los documentos recuperados
    antes de pasárselos al LLM en el prompt.
    """
    formatted = []
    for doc in docs:
        # Extraemos metadatos de forma segura.
        source = doc.metadata.get('filename', doc.metadata.get('source', 'Desconocido'))
        page = doc.metadata.get('page', '?')
        
        # Creamos un string legible: "--- Documento: Ley.pdf (Pág 1) --- [Contenido...]"
        formatted.append(f"--- Documento: {source} (Pág {page}) ---\n{doc.page_content}")
    
    # Unimos todos los fragmentos con saltos de línea.
    return "\n\n".join(formatted)

async def generate_rag_response(query: str):
    """
    Función principal que ejecuta la cadena RAG.
    Usa LCEL (LangChain Expression Language) para un flujo limpio.
    """
    llm = get_llm()
    retriever_instance = get_retriever()
    
    # Verificación de salud de los servicios.
    if not llm or not retriever_instance:
        raise HTTPException(status_code=503, detail="Servicio de IA no disponible.")

    # --- DEFINICIÓN DE LA CADENA (CHAIN) ---
    # La sintaxis de 'pipe' (|) pasa la salida de uno como entrada del siguiente.
    chain = (
        {
            # Paso 1: 'context' se llena buscando docs y formateándolos.
            "context": retriever_instance | format_docs, 
            # Paso 2: 'question' simplemente pasa la pregunta del usuario tal cual.
            "question": RunnablePassthrough()
        }
        | rag_prompt       # Paso 3: Se llena la plantilla del prompt con context y question.
        | llm              # Paso 4: Se envía el prompt al modelo (Ollama).
        | StrOutputParser() # Paso 5: Se limpia la respuesta (de objeto AIMessage a string).
    )
    
    # EJECUCIÓN ASÍNCRONA
    # .ainvoke() permite que FastAPI maneje otras peticiones mientras la IA "piensa".
    response = await chain.ainvoke(query)
    return response

def get_relevant_documents(query: str) -> List[Dict[str, Any]]:
    """
    Función extra para la UI: Permite mostrar "Fuentes" o "Referencias"
    sin generar una respuesta de chat completa.
    """
    retriever_instance = get_retriever()
    if not retriever_instance:
        return []
    
    # Invocación síncrona directa al buscador (rápido).
    docs = retriever_instance.invoke(query)
    
    sources = []
    for doc in docs:
        # Construimos un diccionario limpio para enviar al Frontend (React).
        sources.append({
            "source": doc.metadata.get('filename', doc.metadata.get('source', 'N/A')),
            "page": doc.metadata.get('page', 'N/A'),
            # Preview de 200 chars para no sobrecargar la UI.
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
    """
    Función de auditoría: Guarda cada interacción en la base de datos SQL.
    Vital para historial de chats.
    """
    try:
        # Verificamos si hay fuentes para guardar (JSON).
        sources_data = sources if sources else None
        
        # Creamos el objeto del modelo ORM.
        db_message = models.Message(
            history_id=history_id,
            sender=sender,   # 'user' o 'bot'
            content=content, # Texto del mensaje
            sources=sources_data 
        )
        db.add(db_message)
        db.commit() # Guardamos en DB.
        db.refresh(db_message) # Actualizamos el objeto con ID generado.
        return db_message
    except Exception as e:
        db.rollback() # Si falla, deshacemos cambios para no corromper la DB.
        print(f"Error logueando mensaje: {e}")
        return None