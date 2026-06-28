"""Local RAG vector search layer - ChromaDB-backed, fully offline"""
import logging
from app.config import settings

logger = logging.getLogger("knowall")
_client = None


def _get_chromadb():
    """Lazy import chromadb to avoid hard dependency on startup."""
    try:
        from chromadb import PersistentClient
        from chromadb.config import Settings as ChromaSettings
        return PersistentClient, ChromaSettings
    except ImportError:
        return None, None


def get_chroma_client():
    """Get or create the ChromaDB persistent client."""
    global _client
    if _client is None:
        PersistentClient, ChromaSettings = _get_chromadb()
        if PersistentClient is None:
            logger.warning("ChromaDB not installed. RAG search disabled.")
            return None
        try:
            _client = PersistentClient(
                path=settings.chroma_persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            logger.info("ChromaDB initialized at %s", settings.chroma_persist_dir)
        except Exception as e:
            logger.warning("ChromaDB unavailable: %s. RAG search disabled.", e)
            return None
    return _client


def get_or_create_collection(name: str = "document_knowledge"):
    """Get or create a ChromaDB collection. Returns None if unavailable."""
    client = get_chroma_client()
    if client is None:
        return None
    return client.get_or_create_collection(name=name)


def index_chunks(chunks: list[dict], collection_name: str = "document_knowledge"):
    """Index document chunks into vector store. Returns count or 0."""
    try:
        collection = get_or_create_collection(collection_name)
        if collection is None:
            return 0
        ids = [c["id"] for c in chunks]
        texts = [c["text"] for c in chunks]
        metadatas = [c.get("metadata", {}) for c in chunks]
        collection.add(ids=ids, documents=texts, metadatas=metadatas)
        logger.info("Indexed %d chunks into %s", len(chunks), collection_name)
        return len(chunks)
    except Exception as e:
        logger.error("Failed to index chunks: %s", e)
        return 0


def search(query: str, collection_name: str = "document_knowledge", n_results: int = 5) -> list[dict]:
    """Search for relevant document chunks. Returns empty list if unavailable."""
    try:
        collection = get_or_create_collection(collection_name)
        if collection is None:
            return []
        results = collection.query(query_texts=[query], n_results=n_results)
        return [
            {
                "id": id_,
                "text": doc,
                "metadata": meta,
                "distance": round(dist, 4),
            }
            for id_, doc, meta, dist in zip(
                results.get("ids", [[]])[0],
                results.get("documents", [[]])[0],
                results.get("metadatas", [[]])[0],
                results.get("distances", [[]])[0],
            )
        ]
    except Exception as e:
        logger.error("Search failed: %s", e)
        return []


def rag_query(query: str, top_k: int = 3) -> str:
    """Retrieve relevant context for a question. Returns concatenated text
    that can be passed to an LLM for answer generation.
    """
    results = search(query, n_results=top_k)
    if not results:
        return ""
    return "\n\n---\n\n".join(r["text"] for r in results)


def delete_vectors_by_doc_id(doc_id: str) -> int:
    """Delete all vectors associated with a document from ChromaDB."""
    try:
        collection = get_or_create_collection()
        if collection is None:
            return 0
        collection.delete(where={"doc_id": doc_id})
        logger.info("Deleted vectors for doc %s", doc_id)
        return 0
    except Exception as e:
        logger.warning("Failed to delete vectors for doc %s: %s", doc_id, e)
        return 0


def delete_collection(name: str = "document_knowledge"):
    """Delete a collection."""
    try:
        client = get_chroma_client()
        if client is None:
            return
        client.delete_collection(name)
        logger.info("Deleted collection: %s", name)
    except Exception as e:
        logger.error("Failed to delete collection: %s", e)


def get_index_stats(collection_name: str = "document_knowledge") -> dict:
    """Get statistics about the indexed collection."""
    try:
        collection = get_or_create_collection(collection_name)
        if collection is None:
            return {"collection": collection_name, "indexed_chunks": 0, "status": "chromadb_unavailable"}
        count = collection.count()
        return {"collection": collection_name, "indexed_chunks": count, "status": "active"}
    except Exception:
        return {"collection": collection_name, "indexed_chunks": 0, "status": "error"}
