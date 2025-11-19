import shutil
import tempfile
from pathlib import Path
from fastapi import UploadFile, HTTPException
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from .. import models, schemas, config

settings = config.settings

# We'll import the language/vector libraries inside a try block so that
# the module can still be imported when optional dependencies aren't
# installed (the endpoints will return 503 in that case).
ollama_llm = None
ollama_embeddings = None
vector_store = None
retriever = None

try:
    # Import langchain components only if available
    from langchain.document_loaders import PyPDFLoader
    from langchain.text_splitters import RecursiveCharacterTextSplitter
    from langchain.vectorstores import Chroma

    # Ollama-specific bindings may be provided by langchain-ollama or
    # langchain_ollama; attempt common import paths.
    try:
        from langchain_ollama import OllamaEmbeddings, ChatOllama
    except Exception:
        # Fallback to community namespace if available
        from langchain_community.embeddings import OllamaEmbeddings
        from langchain_community.chat_models import ChatOllama

    # Instantiate LLM, embeddings and vector store
    ollama_llm = ChatOllama(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL,
    )

    ollama_embeddings = OllamaEmbeddings(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.EMBEDDING_MODEL,
    )

    vector_store = Chroma(
        persist_directory=settings.CHROMA_PATH,
        embedding_function=ollama_embeddings,
    )

    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 5},
    )

    print("--- Modelos LLM y Vector Store inicializados ---")

except Exception as e:
    # Don't crash import; endpoints will check `ollama_llm`/`retriever` and
    # return an appropriate error to the client.
    print(f"RAG initialization warning: {e}")
    ollama_llm = None
    retriever = None


# --- Plantilla de Prompt ---
RAG_PROMPT_TEMPLATE = (
    "Eres \"LegislatiBot\", un asistente legal experto. Tu tarea es responder preguntas basándote "
    "únicamente en el siguiente contexto extraído de documentos oficiales. Si el contexto no contiene "
    "la respuesta, di explícitamente: \"Lo siento, no tengo información sobre ese tema en los "
    "documentos proporcionados.\" No inventes información. Sé claro y conciso.\n\n"
    "CONTEXTO:\n{context}\n\nPREGUNTA:\n{question}\n\nRESPUESTA:\n"
)


def process_and_store_pdfs(files: List[UploadFile], db: Session, admin_id: int):
    """Procesa archivos PDF, los divide en chunks y los añade a Chroma.

    Raises:
        Exception: si el LLM o la vector store no están inicializados.
    """
    if not ollama_llm or not retriever or not vector_store:
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

                # Cargar PDF
                loader = PyPDFLoader(str(temp_filepath))
                docs = loader.load()

                # Dividir en chunks
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000, chunk_overlap=200
                )
                splits = text_splitter.split_documents(docs)
                all_splits.extend(splits)

                # Guardar en DB SQL
                db_doc = models.Document(filename=file.filename, admin_id=admin_id)
                db.add(db_doc)
                processed_files.append(file.filename)

            except Exception as e:
                print(f"Error procesando el archivo {file.filename}: {e}")
            finally:
                try:
                    file.file.close()
                except Exception:
                    pass

    # Añadir a la base vectorial
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


class SimpleRAGChain:
    """Pequeña envoltura que expone .invoke(query) y realiza: retrieve -> format -> llm call.

    This keeps the router usage (chain.invoke(query)) unchanged while avoiding
    fragile dependencies on specific LangChain runnable APIs.
    """

    def __init__(self, retriever, llm):
        self.retriever = retriever
        self.llm = llm

    def _get_docs(self, query: str):
        # Try a few common retriever method names
        for meth in ("get_relevant_documents", "get_retrieved_documents", "retrieve", "get_documents", "_get_relevant_documents"):
            if hasattr(self.retriever, meth):
                try:
                    return getattr(self.retriever, meth)(query)
                except TypeError:
                    # Some implementations require kwargs or different signature
                    try:
                        return getattr(self.retriever, meth)(query, k=5)
                    except Exception:
                        continue

        # Last resort: if retriever has `get_relevant_documents` via `.get_relevant_documents`
        if hasattr(self.retriever, "get_relevant_documents"):
            return self.retriever.get_relevant_documents(query)

        # If retriever is callable
        if callable(self.retriever):
            return self.retriever(query)

        return []

    def invoke(self, query: str) -> str:
        if not self.llm or not self.retriever:
            raise HTTPException(status_code=503, detail="Servicio RAG no disponible. Verifica la conexión con Ollama.")

        docs = self._get_docs(query) or []
        context = format_docs(docs)
        prompt = RAG_PROMPT_TEMPLATE.format(context=context, question=query)

        # Try a few ways to call the LLM
        try:
            # Common pattern: LLM is callable
            result = None
            if callable(self.llm):
                result = self.llm(prompt)

            # Some LLM clients expose .generate(...) returning an object with 'generations'
            if result is None and hasattr(self.llm, "generate"):
                gen = self.llm.generate([prompt])
                # try to extract text
                if hasattr(gen, "generations"):
                    try:
                        return gen.generations[0][0].text
                    except Exception:
                        return str(gen)

            # If result is a string
            if isinstance(result, str):
                return result

            # If result has .text
            if hasattr(result, "text"):
                return result.text

            # Fallback to str()
            return str(result)

        except Exception as e:
            raise Exception(f"LLM invocation failed: {e}")


def get_rag_chain():
    """Construye y devuelve una instancia SimpleRAGChain que expone .invoke(query)."""
    if not ollama_llm or not retriever:
        raise HTTPException(status_code=503, detail="Servicio RAG no disponible. Verifica la conexión con Ollama.")

    return SimpleRAGChain(retriever=retriever, llm=ollama_llm)


def get_relevant_documents(query: str) -> List[Dict[str, Any]]:
    """Obtiene los documentos fuente para la cita."""
    if not retriever:
        return []

    # Try common retriever methods
    docs = []
    for meth in ("get_relevant_documents", "retrieve", "get_documents", "_get_relevant_documents"):
        if hasattr(retriever, meth):
            try:
                docs = getattr(retriever, meth)(query)
                break
            except Exception:
                continue

    # If retriever is callable
    if not docs and callable(retriever):
        try:
            docs = retriever(query)
        except Exception:
            docs = []

    sources = []
    for doc in docs or []:
        sources.append({
            "source": getattr(doc, "metadata", {}).get("source", "N/A") if hasattr(doc, "metadata") else getattr(doc, "source", "N/A"),
            "page": getattr(doc, "metadata", {}).get("page", "N/A") if hasattr(doc, "metadata") else getattr(doc, "page", "N/A"),
            "content_preview": (getattr(doc, "page_content", "")[:150] + "...") if hasattr(doc, "page_content") else "",
        })
    return sources


def log_chat_message(
    db: Session,
    history_id: int,
    sender: models.SenderType,
    content: str,
    sources: Optional[List[Dict[str, Any]]] = None,
):
    """Guarda un mensaje en la base de datos SQL."""
    db_message = models.Message(
        history_id=history_id, sender=sender, content=content, sources=sources
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message
