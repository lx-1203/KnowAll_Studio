"""Mind Map Agent - converts knowledge points to visual mind map structure"""
import logging
from app.core.agents.base import BaseAgent, AgentRegistry, AgentResult

logger = logging.getLogger(__name__)


@AgentRegistry.register("mindmap")
class MindMapAgent(BaseAgent):
    """Converts knowledge point hierarchy into a mind map data structure."""

    name = "mindmap"
    description = "将知识点总结转化为层级思维导图结构"

    async def run(self, summary_id: str, document_id: str, **kwargs) -> AgentResult:
        from app.database import async_session
        from app.models import KnowledgeSummary, KnowledgePointNode
        from sqlalchemy import select

        try:
            async for session in get_session():
                summary = await session.get(KnowledgeSummary, summary_id)
                if not summary:
                    return AgentResult(agent=self.name, status="error", error="Summary not found")

                # Load nodes
                stmt = select(KnowledgePointNode).where(
                    KnowledgePointNode.summary_id == summary_id
                ).order_by(KnowledgePointNode.level, KnowledgePointNode.sequence)
                result = await session.execute(stmt)
                nodes = result.scalars().all()

                if not nodes:
                    # Extract from markdown
                    from app.core.knowledge.summary_generator import summary_generator
                    node_dicts = summary_generator.extract_nodes_from_markdown(summary.content_md, document_id)
                else:
                    node_dicts = []
                    for n in nodes:
                        node_dicts.append({
                            "id": n.id,
                            "parent_id": n.parent_id,
                            "level": n.level,
                            "sequence": n.sequence,
                            "title": n.title,
                            "tag": n.tags[0] if n.tags else "重点",
                            "summary": n.explanation[:120] if n.explanation else "",
                        })

                # Build tree structure
                mindmap_nodes, mindmap_edges = self._build_mindmap(node_dicts)

                # Also load cross-reference edges
                from app.models import KnowledgeEdge
                from app.models import KnowledgeTree

                # Find related tree for this document
                stmt2 = select(KnowledgeTree).where(KnowledgeTree.doc_ids.contains([document_id]))
                result2 = await session.execute(stmt2)
                trees = result2.scalars().all()

                for tree in trees:
                    edge_stmt = select(KnowledgeEdge).where(KnowledgeEdge.tree_id == tree.id)
                    edge_result = await session.execute(edge_stmt)
                    edges = edge_result.scalars().all()
                    for edge in edges:
                        mindmap_edges.append({
                            "source": edge.source_node_id,
                            "target": edge.target_node_id,
                            "relation": edge.relation_type,
                        })

                return AgentResult(
                    agent=self.name,
                    status="success",
                    result={
                        "nodes": mindmap_nodes,
                        "edges": mindmap_edges,
                        "total_nodes": len(mindmap_nodes),
                        "total_edges": len(mindmap_edges),
                    },
                )

        except Exception as e:
            logger.error(f"MindMapAgent failed: {e}", exc_info=True)
            return AgentResult(agent=self.name, status="error", error=str(e))

    def _build_mindmap(self, nodes: list[dict]) -> tuple[list[dict], list[dict]]:
        """Build hierarchical mind map nodes and edges."""
        mindmap_nodes = []
        mindmap_edges = []

        node_map = {n["id"]: n for n in nodes}

        for node in nodes:
            # Create mind map node
            mn = {
                "id": node["id"],
                "label": node["title"],
                "level": node["level"],
                "tag": node.get("tag", ""),
                "summary": node.get("summary", "")[:120],
            }
            mindmap_nodes.append(mn)

            # Create edge to parent
            if node.get("parent_id") and node["parent_id"] in node_map:
                mindmap_edges.append({
                    "source": node["parent_id"],
                    "target": node["id"],
                    "relation": "parent_child",
                })

        return mindmap_nodes, mindmap_edges
