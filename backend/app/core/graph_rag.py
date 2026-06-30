"""GraphRAG - Hybrid Vector + Knowledge Graph Retrieval

Combines ChromaDB vector search with knowledge graph traversal for
multi-hop, context-rich retrieval across the KnowAll knowledge base.

Architecture:
  1. Vector search (existing ChromaDB) for semantic matching
  2. Map results to knowledge point nodes
  3. BFS/DFS graph traversal from matched nodes (1-2 hops)
  4. Collect explanations, edges, and related chunks
  5. Deduplicate & compress context for LLM injection
"""

import hashlib
import logging
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from app.database import async_session
from app.models import KnowledgeEdge, KnowledgePointNode, DocumentChunk
from app.core.rag import search as vector_search

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_MAX_HOPS = 2
DEFAULT_TOP_K_VECTOR = 8
DEFAULT_TOP_K_GRAPH = 20
RELATION_WEIGHTS: dict[str, float] = {
    "prerequisite": 1.5,
    "extends": 1.3,
    "confused_with": 1.2,  # also recorded as contradicted/confused
    "contradicts": 1.2,
    "example_of": 1.1,
    "analogous_to": 1.3,
    "applies_to": 1.1,
    "related_to": 1.0,
}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class GraphNode:
    """A node in the in-memory knowledge graph."""
    node_id: str
    title: str
    explanation: str
    level: int
    chunk_ids: list[str] = field(default_factory=list)


@dataclass
class GraphEdge:
    """A directed edge between two knowledge nodes."""
    source_id: str
    target_id: str
    relation_type: str
    description: str = ""


@dataclass
class RetrievalResult:
    """A single result from hybrid retrieval."""
    source: str          # "vector" | "graph_hop1" | "graph_hop2" | "edge"
    node_id: str | None
    title: str
    text: str
    relevance_score: float
    relation_path: str = ""  # e.g. "A --prerequisite--> B"


# ---------------------------------------------------------------------------
# Lightweight In-Memory Graph
# ---------------------------------------------------------------------------

class KnowledgeGraph:
    """Dict-based adjacency-list graph built from DB knowledge edges + nodes.

    Lazily loaded and rebuilt on every graph traversal — keeps data fresh
    without needing a persistent graph DB like Neo4j.
    """

    def __init__(self):
        self._adj_out: dict[str, list[tuple[str, str, str]]] = {}   # src -> [(tgt, relation, desc)]
        self._adj_in: dict[str, list[tuple[str, str, str]]] = {}    # tgt -> [(src, relation, desc)]
        self._nodes: dict[str, GraphNode] = {}
        self._title_index: dict[str, list[str]] = {}  # lowercase title words -> node_ids
        self._built = False

    async def build(self) -> int:
        """(Re)build the graph from database. Returns number of nodes loaded."""
        self._adj_out.clear()
        self._adj_in.clear()
        self._nodes.clear()
        self._title_index.clear()

        async with async_session() as db:
            # Load all edges
            edges_result = await db.execute(select(KnowledgeEdge))
            edges = edges_result.scalars().all()

            for e in edges:
                self._adj_out.setdefault(e.source_node_id, []).append(
                    (e.target_node_id, e.relation_type, e.description or "")
                )
                self._adj_in.setdefault(e.target_node_id, []).append(
                    (e.source_node_id, e.relation_type, e.description or "")
                )

            # Load all knowledge point nodes
            nodes_result = await db.execute(select(KnowledgePointNode))
            nodes = nodes_result.scalars().all()

            for n in nodes:
                gn = GraphNode(
                    node_id=n.id,
                    title=n.title,
                    explanation=n.explanation or "",
                    level=n.level,
                )
                self._nodes[n.id] = gn

                # Build title word index for fuzzy lookup
                for word in self._tokenize(n.title):
                    self._title_index.setdefault(word, []).append(n.id)

            edge_count = len(edges)

        self._built = True
        logger.info("KnowledgeGraph built: %d nodes, %d edges", len(self._nodes), edge_count)
        return len(self._nodes)

    # ---- Traversal ----

    def traverse(
        self,
        seed_ids: list[str],
        max_hops: int = DEFAULT_MAX_HOPS,
        max_results: int = DEFAULT_TOP_K_GRAPH,
    ) -> list[tuple[GraphNode, str, float]]:  # (node, relation_path, score)
        """BFS from seed nodes. Returns [(node, path_description, relevance_score), ...]."""
        if not self._nodes:
            return []

        visited: set[str] = set()
        results: list[tuple[GraphNode, str, float]] = []
        queue: deque = deque()

        # Seed queue with initial nodes
        for sid in seed_ids:
            if sid in self._nodes:
                score = 2.0  # direct vector match = highest score
                queue.append((sid, f"[直接匹配] {self._nodes[sid].title}", score))
                visited.add(sid)

        hop = 0
        while queue and len(results) < max_results and hop <= max_hops:
            level_size = len(queue)
            for _ in range(level_size):
                if len(results) >= max_results:
                    break
                node_id, path, base_score = queue.popleft()
                node = self._nodes.get(node_id)
                if node:
                    decay = 1.0 / (hop + 1)  # score decays with hop distance
                    results.append((node, path, base_score * decay))

                # Expand neighbors (outgoing)
                for tgt_id, rel_type, desc in self._adj_out.get(node_id, []):
                    if tgt_id not in visited and tgt_id in self._nodes:
                        visited.add(tgt_id)
                        rel_weight = RELATION_WEIGHTS.get(rel_type, 1.0) if hop == 0 else 0.8
                        new_path = f"{path} --[{rel_type}]--> {self._nodes[tgt_id].title}"
                        if desc:
                            new_path += f" ({desc})"
                        queue.append((tgt_id, new_path, base_score * rel_weight))

                # Expand neighbors (incoming)
                for src_id, rel_type, desc in self._adj_in.get(node_id, []):
                    if src_id not in visited and src_id in self._nodes:
                        visited.add(src_id)
                        new_path = f"{self._nodes[src_id].title} --[{rel_type}]--> {path.split('] ')[-1] if '] ' in path else path}"
                        queue.append((src_id, new_path, base_score * 0.9))

            hop += 1

        # Sort by relevance score descending
        results.sort(key=lambda x: x[2], reverse=True)
        return results[:max_results]

    # ---- Node lookup helpers ----

    def find_nodes_by_title(self, query: str, max_results: int = 10) -> list[GraphNode]:
        """Fuzzy title lookup using word overlap + substring matching."""
        tokens = self._tokenize(query)
        scored: list[tuple[GraphNode, float]] = []

        candidate_ids: set[str] = set()
        for token in tokens:
            if token in self._title_index:
                candidate_ids.update(self._title_index[token])

        for nid in candidate_ids:
            node = self._nodes.get(nid)
            if node is None:
                continue
            # Simple word overlap score
            title_tokens = set(self._tokenize(node.title))
            overlap = len(tokens & title_tokens)
            if overlap > 0:
                scored.append((node, overlap / len(tokens)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in scored[:max_results]]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Simple Chinese + English tokenizer."""
        # Split on non-alphanumeric, keep CJK chars individually
        text = text.lower()
        tokens: list[str] = []
        for char in text:
            if '\u4e00' <= char <= '\u9fff':
                tokens.append(char)  # each CJK char is a token
        # Also extract alphanumeric words
        for word in re.findall(r'[a-z0-9]{2,}', text):
            tokens.append(word)
        return tokens

    @property
    def node_count(self) -> int:
        return len(self._nodes)


# ---------------------------------------------------------------------------
# Context Compressor
# ---------------------------------------------------------------------------

class ContextCompressor:
    """Deduplicate and compress retrieval results to avoid token waste."""

    @staticmethod
    def deduplicate(
        results: list[RetrievalResult],
        similarity_threshold: float = 0.7,
    ) -> list[RetrievalResult]:
        """Remove near-duplicate results using Jaccard similarity on character bigrams."""
        if len(results) <= 1:
            return results

        kept: list[RetrievalResult] = []
        for r in results:
            is_dup = False
            r_bigrams = ContextCompressor._bigrams(r.text)
            for existing in kept:
                e_bigrams = ContextCompressor._bigrams(existing.text)
                if not r_bigrams or not e_bigrams:
                    continue
                intersection = len(r_bigrams & e_bigrams)
                union = len(r_bigrams | e_bigrams)
                jaccard = intersection / union if union > 0 else 0
                if jaccard > similarity_threshold:
                    is_dup = True
                    break
            if not is_dup:
                kept.append(r)

        return kept

    @staticmethod
    def format_context(
        results: list[RetrievalResult],
        max_chars: int = 8000,
    ) -> str:
        """Format deduplicated results into a compact Markdown context block."""
        parts: list[str] = []
        total_chars = 0

        sections: dict[str, list[RetrievalResult]] = {
            "直接匹配": [],
            "图关联": [],
            "向量检索": [],
        }

        for r in results:
            if "[直接匹配]" in r.relation_path:
                sections["直接匹配"].append(r)
            elif "--[" in r.relation_path:
                sections["图关联"].append(r)
            else:
                sections["向量检索"].append(r)

        for section_name, items in sections.items():
            if not items:
                continue
            parts.append(f"### {section_name}")
            for i, item in enumerate(items, 1):
                header = f"**{item.title}**"
                if item.relation_path:
                    header += f" | 路径: {item.relation_path}"
                header += f" | 相关度: {item.relevance_score:.2f}"
                body = item.text[:1000]  # truncate each result
                block = f"{i}. {header}\n   {body}\n"
                if total_chars + len(block) > max_chars:
                    parts.append(f"\n*(剩余 {len(items) - i + 1} 条结果已截断)*")
                    break
                parts.append(block)
                total_chars += len(block)

        return "\n".join(parts)

    @staticmethod
    def _bigrams(text: str) -> set[str]:
        """Character bigrams for fuzzy dedup."""
        clean = re.sub(r'\s+', '', text)
        return {clean[i:i + 2] for i in range(len(clean) - 1)}


# ---------------------------------------------------------------------------
# Hybrid Retriever
# ---------------------------------------------------------------------------

class HybridRetriever:
    """Combines vector search + knowledge graph traversal for rich retrieval."""

    def __init__(self):
        self._graph: KnowledgeGraph | None = None
        self._compressor = ContextCompressor()

    async def _ensure_graph(self) -> KnowledgeGraph:
        """Lazy-build the knowledge graph."""
        if self._graph is None or not self._graph._built:
            self._graph = KnowledgeGraph()
            await self._graph.build()
        return self._graph

    async def retrieve(
        self,
        query: str,
        top_k_vector: int = DEFAULT_TOP_K_VECTOR,
        max_hops: int = DEFAULT_MAX_HOPS,
        max_graph_results: int = DEFAULT_TOP_K_GRAPH,
        max_total: int = 30,
    ) -> list[RetrievalResult]:
        """Main hybrid retrieval entry point.

        1. Vector search for relevant chunks
        2. Map chunks -> knowledge point nodes
        3. Graph BFS from matched nodes
        4. Collect and deduplicate all results
        """
        results: list[RetrievalResult] = []

        # Step 1: Vector search
        vector_results = vector_search(query, n_results=top_k_vector)
        matched_chunk_ids: set[str] = set()
        matched_doc_ids: set[str] = set()

        for vr in vector_results:
            results.append(RetrievalResult(
                source="vector",
                node_id=None,
                title=vr.get("metadata", {}).get("doc_id", "文档片段")[:30],
                text=vr.get("text", ""),
                relevance_score=1.0 - vr.get("distance", 0),
            ))
            chunk_id = vr.get("id", "")
            if chunk_id:
                matched_chunk_ids.add(chunk_id)
            doc_id = vr.get("metadata", {}).get("doc_id", "")
            if doc_id:
                matched_doc_ids.add(doc_id)

        # Step 2: Build graph & map chunks -> knowledge point nodes
        graph = await self._ensure_graph()

        if graph.node_count == 0:
            logger.info("Knowledge graph is empty, returning vector-only results")
            return self._compressor.deduplicate(results)

        seed_node_ids: set[str] = set()

        if matched_chunk_ids:
            async with async_session() as db:
                # Find chunk texts to match against node titles
                chunks_result = await db.execute(
                    select(DocumentChunk).where(DocumentChunk.id.in_(list(matched_chunk_ids)[:20]))
                )
                for chunk in chunks_result.scalars().all():
                    text_snippet = (chunk.text_content or "")[:200]
                    # Find nodes by title overlap with chunk content
                    for word in self._extract_keywords(text_snippet):
                        matched = graph.find_nodes_by_title(word, max_results=3)
                        for mn in matched:
                            seed_node_ids.add(mn.node_id)

        # Also try matching query directly against node titles
        query_matches = graph.find_nodes_by_title(query, max_results=5)
        for qm in query_matches:
            seed_node_ids.add(qm.node_id)

        logger.info("GraphRAG: %d vector results → %d seed nodes", len(vector_results), len(seed_node_ids))

        # Step 3: Graph traversal from seeds
        if seed_node_ids:
            graph_results = graph.traverse(
                list(seed_node_ids)[:10],
                max_hops=max_hops,
                max_results=max_graph_results,
            )
            for node, path, score in graph_results:
                results.append(RetrievalResult(
                    source="graph_hop1" if "--[" not in path else "graph_hop2",
                    node_id=node.node_id,
                    title=node.title,
                    text=node.explanation[:1500],
                    relevance_score=score,
                    relation_path=path,
                ))

        # Step 4: Deduplicate & truncate
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        results = self._compressor.deduplicate(results)
        return results[:max_total]

    @staticmethod
    def _extract_keywords(text: str, max_kw: int = 8) -> list[str]:
        """Extract potential keyword phrases from text."""
        # Split on common delimiters
        parts = re.split(r'[，。、；：,.\n;:\s]+', text)
        keywords = [p.strip() for p in parts if 2 <= len(p.strip()) <= 20]
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique.append(kw)
        return unique[:max_kw]


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

_hybrid_retriever: HybridRetriever | None = None


def get_hybrid_retriever() -> HybridRetriever:
    global _hybrid_retriever
    if _hybrid_retriever is None:
        _hybrid_retriever = HybridRetriever()
    return _hybrid_retriever


async def graph_rag_query(
    query: str,
    top_k_vector: int = DEFAULT_TOP_K_VECTOR,
    max_hops: int = DEFAULT_MAX_HOPS,
    max_context_chars: int = 8000,
) -> tuple[str, list[RetrievalResult]]:
    """Convenience function: returns (formatted_context, raw_results)."""
    retriever = get_hybrid_retriever()
    results = await retriever.retrieve(
        query=query,
        top_k_vector=top_k_vector,
        max_hops=max_hops,
    )
    context = ContextCompressor.format_context(results, max_chars=max_context_chars)
    return context, results


async def rebuild_graph() -> int:
    """Force rebuild the knowledge graph index. Returns node count."""
    global _hybrid_retriever
    graph = KnowledgeGraph()
    count = await graph.build()
    _hybrid_retriever = HybridRetriever()
    _hybrid_retriever._graph = graph
    return count


async def get_graph_stats() -> dict:
    """Get current graph statistics."""
    retriever = get_hybrid_retriever()
    graph = await retriever._ensure_graph()
    return {
        "node_count": graph.node_count,
        "edge_count_out": sum(len(v) for v in graph._adj_out.values()),
        "edge_count_in": sum(len(v) for v in graph._adj_in.values()),
        "built": graph._built,
    }
