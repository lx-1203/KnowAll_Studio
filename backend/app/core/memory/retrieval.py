"""Card retriever - semantic search for flashcards via ChromaDB with SQL fallback"""
import logging
from sqlalchemy import select, or_
from app.database import async_session
from app.models import Flashcard

logger = logging.getLogger(__name__)


class CardRetriever:
    """Semantic search over flashcard corpus.

    Primary: ChromaDB vector similarity search
    Fallback: SQL LIKE keyword search with Jaccard re-ranking
    """

    def __init__(self):
        self._chroma_client = None

    async def _get_chroma(self):
        """Lazy-initialize ChromaDB client."""
        if self._chroma_client is None:
            try:
                import chromadb
                self._chroma_client = chromadb.PersistentClient(
                    path="./data/chromadb"
                )
            except ImportError:
                logger.warning("chromadb not installed, using keyword search")
                self._chroma_client = False
            except Exception as e:
                logger.warning(f"ChromaDB init failed: {e}")
                self._chroma_client = False
        return self._chroma_client if self._chroma_client is not False else None

    async def search(
        self,
        query: str,
        top_k: int = 10,
        deck_id: str | None = None,
    ) -> list[dict]:
        """Semantic search for flashcards.

        Args:
            query: Search query text
            top_k: Number of results
            deck_id: Optional deck filter

        Returns:
            List of card dicts sorted by relevance
        """
        chroma = await self._get_chroma()
        if chroma:
            try:
                return await self._chroma_search(query, top_k, deck_id)
            except Exception as e:
                logger.warning(f"ChromaDB search failed, falling back: {e}")

        return await self._keyword_search(query, top_k, deck_id)

    async def _chroma_search(
        self,
        query: str,
        top_k: int,
        deck_id: str | None,
    ) -> list[dict]:
        """Vector similarity search via ChromaDB."""
        # Placeholder for actual embedding + ChromaDB search
        # Requires embedding model integration (e.g., sentence-transformers)
        # For now, falls through to keyword search
        raise NotImplementedError("Embedding model not configured")

    async def _keyword_search(
        self,
        query: str,
        top_k: int,
        deck_id: str | None,
    ) -> list[dict]:
        """Keyword search with Jaccard similarity re-ranking."""
        async with async_session() as session:
            conditions = [
                or_(
                    Flashcard.front.ilike(f"%{query}%"),
                    Flashcard.back.ilike(f"%{query}%"),
                )
            ]
            if deck_id:
                conditions.append(Flashcard.deck_id == deck_id)

            stmt = select(Flashcard).where(*conditions).limit(top_k * 3)
            result = await session.execute(stmt)
            cards = result.scalars().all()

            # Re-rank by Jaccard similarity
            query_chars = set(query.lower())
            scored = []
            for card in cards:
                text = f"{card.front} {card.back} {card.hints or ''}".lower()
                text_chars = set(text)
                if not text_chars:
                    continue
                jaccard = len(query_chars & text_chars) / len(query_chars | text_chars)
                # Boost exact matches
                if query.lower() in card.front.lower():
                    jaccard += 0.3
                scored.append((jaccard, card))

            scored.sort(key=lambda x: x[0], reverse=True)

            return [
                {
                    "id": c.id,
                    "card_type": c.card_type,
                    "front": c.front,
                    "back": c.back,
                    "hints": c.hints,
                    "tags": c.tags,
                    "deck_id": c.deck_id,
                    "relevance": round(score, 3),
                }
                for score, c in scored[:top_k]
            ]

    async def index_card(self, card_id: str) -> bool:
        """Index a single card into ChromaDB. (Placeholder)"""
        return False

    async def index_deck(self, deck_id: str) -> int:
        """Index all cards in a deck. (Placeholder)"""
        return 0


card_retriever = CardRetriever()
