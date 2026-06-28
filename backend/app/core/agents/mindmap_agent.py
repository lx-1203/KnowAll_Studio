"""Mind Map Agent - 基于 BOIS 理论的智能思维导图生成器

BOIS (Basic Ordering Ideas / 基本分类概念) 是思维导图创始人托尼·巴赞提出的
核心技术。本 Agent 实现了：

1. 层级结构自动提取与构建
2. BOIS 质量评估（位阶合理性、分支发散度、同位阶均衡性、覆盖完整性）
3. LLM 驱动的 BOIS 重构优化（三步法：上找大类→中找同类→下找小类）
4. 横向知识关联（跨分支连线）
5. BOIS 分类框架生成
"""

import json as json_module
import logging
from app.core.agents.base import BaseAgent, AgentRegistry, AgentResult
from app.core.knowledge.bois_analyzer import bois_analyzer, BOISMetrics

logger = logging.getLogger(__name__)


@AgentRegistry.register("mindmap")
class MindMapAgent(BaseAgent):
    """将知识点总结转化为符合 BOIS 理论的层级思维导图结构。

    BOIS 三步法在 Agent 中的映射：
    - 上找大类 (Upper Category Detection)：自动识别并补全缺失的上位阶
    - 中找同类 (Peer Expansion)：检测同级概念的完整性，标记遗漏
    - 下找小类 (Lower Detail Drill)：评估下位阶展开深度，提出深挖建议
    """

    name = "mindmap"
    description = "基于BOIS理论将知识点转化为层级思维导图结构，含质量评估与优化建议"

    # ── 配置常量 ─────────────────────────────────────────────
    BOIS_LLM_ENABLED = True       # 是否启用 LLM 重构
    BOIS_SCORE_THRESHOLD = 70     # BOIS 分数阈值，低于此分数触发 LLM 重构
    MAX_LLM_NODES = 200           # LLM 重构时最大节点数（超出则跳过）

    async def run(
        self,
        summary_id: str,
        document_ids: list[str] | None = None,
        enable_bois_llm: bool = True,
        force_restructure: bool = False,
        **kwargs,
    ) -> AgentResult:
        """执行思维导图生成（含 BOIS 分析）。

        Args:
            summary_id: 知识总结 ID
            document_ids: 文档 ID 列表（用于加载跨知识树关联）
            enable_bois_llm: 是否启用 LLM 驱动的 BOIS 重构
            force_restructure: 即使 BOIS 评分合格也强制 LLM 重构

        Returns:
            AgentResult 包含 nodes/edges/bois_metrics/restructure_plan
        """
        from app.database import async_session
        from app.models import KnowledgeSummary, KnowledgePointNode
        from sqlalchemy import select

        try:
            async with async_session() as session:
                # 1. 加载知识总结和节点
                summary = await session.get(KnowledgeSummary, summary_id)
                if not summary:
                    return AgentResult(
                        agent=self.name, status="error",
                        error="Summary not found"
                    )

                node_dicts = await self._load_nodes(session, summary, document_id)

                if not node_dicts:
                    return AgentResult(
                        agent=self.name, status="error",
                        error="No knowledge point nodes found. Generate a summary first."
                    )

                # 2. 构建基础思维导图结构
                mindmap_nodes, mindmap_edges = self._build_mindmap(node_dicts)

                # 3. 加载横向关联边
                cross_edges = await self._load_cross_edges(session, document_id)
                mindmap_edges.extend(cross_edges)

                # 4. BOIS 质量分析
                bois_metrics: BOISMetrics = bois_analyzer.analyze(
                    mindmap_nodes, mindmap_edges
                )

                # 5. 生成重构建议
                restructure_plan = bois_analyzer.suggest_restructure(
                    mindmap_nodes, mindmap_edges, bois_metrics
                )

                # 6. LLM 驱动的 BOIS 重构（条件触发）
                llm_restructured = None
                should_restructure = (
                    self.BOIS_LLM_ENABLED
                    and enable_bois_llm
                    and (
                        force_restructure
                        or bois_metrics.bois_score < self.BOIS_SCORE_THRESHOLD
                    )
                    and len(mindmap_nodes) <= self.MAX_LLM_NODES
                )

                if should_restructure:
                    logger.info(
                        f"BOIS score {bois_metrics.bois_score:.1f} < {self.BOIS_SCORE_THRESHOLD}, "
                        f"triggering LLM restructure"
                    )
                    llm_restructured = await self._llm_bois_restructure(
                        mindmap_nodes, mindmap_edges, bois_metrics
                    )
                    if llm_restructured:
                        # 使用 LLM 重构后的节点替换
                        restructured_nodes, restructured_edges = llm_restructured
                        # 重新评估
                        bois_metrics = bois_analyzer.analyze(
                            restructured_nodes, restructured_edges
                        )
                        restructure_plan = bois_analyzer.suggest_restructure(
                            restructured_nodes, restructured_edges, bois_metrics
                        )
                        mindmap_nodes = restructured_nodes
                        mindmap_edges = restructured_edges

                # 7. 构建分类框架
                children_map = {}
                for e in mindmap_edges:
                    if e.get("relation") == "parent_child":
                        children_map.setdefault(e["source"], []).append(e["target"])

                # 8. 组装返回结果
                return AgentResult(
                    agent=self.name,
                    status="success",
                    result={
                        "nodes": mindmap_nodes,
                        "edges": mindmap_edges,
                        "total_nodes": len(mindmap_nodes),
                        "total_edges": len(mindmap_edges),
                        # BOIS 分析结果
                        "bois_metrics": {
                            "score": round(bois_metrics.bois_score, 1),
                            "max_depth": bois_metrics.max_depth,
                            "depth_distribution": bois_metrics.depth_distribution,
                            "avg_children_per_node": round(bois_metrics.avg_children_per_node, 2),
                            "branching_factor": round(bois_metrics.branching_factor, 2),
                            "hierarchy_balance": round(bois_metrics.hierarchy_balance, 3),
                            "coverage_completeness": round(bois_metrics.coverage_completeness, 3),
                            "peer_variance": round(bois_metrics.peer_variance, 1),
                            "suggestions": bois_metrics.suggestions,
                            "grade": self._score_to_grade(bois_metrics.bois_score),
                        },
                        "restructure_plan": restructure_plan,
                        "category_framework": bois_metrics.category_framework,
                        "llm_restructured": llm_restructured is not None,
                    },
                )

        except Exception as e:
            logger.error(f"MindMapAgent failed: {e}", exc_info=True)
            return AgentResult(
                agent=self.name, status="error", error=str(e)
            )

    # ── 内部方法 ──────────────────────────────────────────────

    async def _load_nodes(
        self, session, summary, document_id: str
    ) -> list[dict]:
        """从数据库或 Markdown 中加载知识点节点。"""
        from app.models import KnowledgePointNode
        from sqlalchemy import select

        stmt = (
            select(KnowledgePointNode)
            .where(KnowledgePointNode.summary_id == summary.id)
            .order_by(KnowledgePointNode.level, KnowledgePointNode.sequence)
        )
        result = await session.execute(stmt)
        nodes = result.scalars().all()

        if not nodes:
            from app.core.knowledge.summary_generator import summary_generator
            node_dicts = summary_generator.extract_nodes_from_markdown(
                summary.content_md, document_id
            )
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
        return node_dicts

    async def _load_cross_edges(
        self, session, document_ids: list[str]
    ) -> list[dict]:
        """加载跨知识树的横向关联边。

        使用 Python 侧过滤以兼容 PostgreSQL 和 SQLite。
        """
        from app.models import KnowledgeEdge, KnowledgeTree
        from sqlalchemy import select

        if not document_ids:
            return []

        cross_edges = []
        # 加载所有知识树，在 Python 中按 doc_ids 过滤
        stmt = select(KnowledgeTree)
        result = await session.execute(stmt)
        trees = result.scalars().all()

        doc_id_set = set(document_ids)
        for tree in trees:
            # 检查该树是否包含目标文档（兼容 JSON 列表）
            tree_doc_ids = tree.doc_ids or []
            if not doc_id_set.intersection(tree_doc_ids):
                continue

            edge_stmt = select(KnowledgeEdge).where(
                KnowledgeEdge.tree_id == tree.id
            )
            edge_result = await session.execute(edge_stmt)
            for edge in edge_result.scalars().all():
                cross_edges.append({
                    "source": edge.source_node_id,
                    "target": edge.target_node_id,
                    "relation": edge.relation_type or "related_to",
                })

        return cross_edges

    def _build_mindmap(
        self, nodes: list[dict]
    ) -> tuple[list[dict], list[dict]]:
        """构建层次化思维导图节点和边。"""
        mindmap_nodes = []
        mindmap_edges = []
        node_map = {n["id"]: n for n in nodes}

        for node in nodes:
            mn = {
                "id": node["id"],
                "label": node["title"],
                "level": node["level"],
                "tag": node.get("tag", ""),
                "summary": node.get("summary", "")[:120],
            }
            mindmap_nodes.append(mn)

            if node.get("parent_id") and node["parent_id"] in node_map:
                mindmap_edges.append({
                    "source": node["parent_id"],
                    "target": node["id"],
                    "relation": "parent_child",
                })

        # BOIS 增强：检测并补全缺失的父节点关系
        mindmap_edges = self._bois_edge_enhancement(
            mindmap_nodes, mindmap_edges
        )

        return mindmap_nodes, mindmap_edges

    def _bois_edge_enhancement(
        self, nodes: list[dict], edges: list[dict]
    ) -> list[dict]:
        """BOIS 边增强：为同位阶节点补充隐式关联。

        当多个 L1 节点下存在语义相似的 L2 节点时，添加跨分支关联边，
        体现 BOIS 理论中"找同类"的横向思维。
        """
        children_by_parent = {}
        for edge in edges:
            if edge.get("relation") == "parent_child":
                children_by_parent.setdefault(
                    edge["source"], []
                ).append(edge["target"])

        node_map = {n["id"]: n for n in nodes}
        enhanced = list(edges)

        # 同层节点标签相似度检测（简单启发式：共享关键词）
        for pid1, children1 in children_by_parent.items():
            for pid2, children2 in children_by_parent.items():
                if pid1 >= pid2:
                    continue
                for c1 in children1:
                    for c2 in children2:
                        n1 = node_map.get(c1, {})
                        n2 = node_map.get(c2, {})
                        label1 = n1.get("label", "")
                        label2 = n2.get("label", "")
                        if self._labels_related(label1, label2):
                            # 避免重复边
                            existing = {
                                (e["source"], e["target"]) for e in enhanced
                            }
                            if (c1, c2) not in existing and (c2, c1) not in existing:
                                enhanced.append({
                                    "source": c1,
                                    "target": c2,
                                    "relation": "cross_reference",
                                })
        return enhanced

    @staticmethod
    def _labels_related(a: str, b: str) -> bool:
        """检测两个标签是否可能存在语义关联。"""
        if not a or not b:
            return False
        a_chars = set(a.replace("的", "").replace("与", ""))
        b_chars = set(b.replace("的", "").replace("与", ""))
        if len(a_chars) < 2 or len(b_chars) < 2:
            return False
        overlap = a_chars & b_chars
        return len(overlap) >= min(2, len(a_chars) * 0.5)

    async def _llm_bois_restructure(
        self,
        nodes: list[dict],
        edges: list[dict],
        metrics: BOISMetrics,
    ) -> tuple[list[dict], list[dict]] | None:
        """使用 LLM 按 BOIS 原则重构知识树结构。

        Returns:
            (nodes, edges) 重构后的节点和边，失败返回 None
        """
        try:
            from app.prompts import prompt_engine
            from app.core.api_scheduler import api_client, TaskType, GenerationConfig

            # 将当前结构序列化为 JSON 供 LLM 分析
            current_tree = self._nodes_to_tree_json(nodes, edges)
            level_dist = json_module.dumps(metrics.depth_distribution)

            messages = prompt_engine.render(
                "mindmap", "bois_restructure",
                total_nodes=metrics.total_nodes,
                max_depth=metrics.max_depth,
                level_distribution=level_dist,
                current_tree_json=current_tree,
            )

            result = await api_client.generate(
                task_type=TaskType.KNOWLEDGE_TREE,
                messages=messages,
                prompt_template_id="mindmap.bois_restructure",
                generation_content=current_tree,
                config=GenerationConfig(model="deepseek-chat", max_tokens=8000),
            )

            parsed = json_module.loads(result.content)

            # 从 LLM 返回中提取节点和边
            restructured = parsed.get("restructured_tree", {})
            llm_nodes = restructured.get("nodes", [])

            if not llm_nodes:
                logger.warning("LLM returned empty nodes, skipping restructure")
                return None

            # 展平 LLM 返回的嵌套 children 结构为节点+边列表
            flat_nodes, flat_edges = self._flatten_tree(llm_nodes)

            logger.info(
                f"LLM restructured: {len(nodes)}→{len(flat_nodes)} nodes, "
                f"new BOIS score (claimed): {restructured.get('bois_score_after', 'N/A')}"
            )
            return flat_nodes, flat_edges

        except json_module.JSONDecodeError as e:
            logger.warning(f"LLM restructure JSON parse failed: {e}")
            return None
        except Exception as e:
            logger.error(f"LLM restructure failed: {e}", exc_info=True)
            return None

    def _nodes_to_tree_json(
        self, nodes: list[dict], edges: list[dict]
    ) -> str:
        """将节点列表和边列表转换为嵌套树形 JSON 字符串。"""
        # 构建父子关系
        children_map = {}
        for e in edges:
            if e.get("relation") == "parent_child":
                children_map.setdefault(e["source"], []).append(e["target"])

        node_map = {n["id"]: n for n in nodes}
        root_ids = {
            n["id"] for n in nodes
            if n.get("level") == 1 or (
                n.get("parent_id") is None
                and not any(
                    e.get("target") == n["id"] and e.get("relation") == "parent_child"
                    for e in edges
                )
            )
        }

        def build_children(node_id):
            child_ids = children_map.get(node_id, [])
            result = []
            for cid in child_ids:
                child = node_map.get(cid, {})
                result.append({
                    "id": cid,
                    "label": child.get("label", ""),
                    "level": child.get("level", 0),
                    "tag": child.get("tag", ""),
                    "summary": child.get("summary", ""),
                    "children": build_children(cid),
                })
            return result

        tree = []
        for rid in sorted(root_ids):
            root = node_map.get(rid, {})
            tree.append({
                "id": rid,
                "label": root.get("label", ""),
                "level": root.get("level", 1),
                "tag": root.get("tag", ""),
                "summary": root.get("summary", ""),
                "children": build_children(rid),
            })

        return json_module.dumps(tree, ensure_ascii=False, indent=2)

    def _flatten_tree(
        self, tree_nodes: list[dict], parent_id: str | None = None
    ) -> tuple[list[dict], list[dict]]:
        """将嵌套树结构递归展开为扁平的节点列表和边列表。"""
        flat_nodes = []
        flat_edges = []

        for node in tree_nodes:
            children = node.pop("children", [])
            node_id = node["id"]
            flat_node = {
                "id": node_id,
                "label": node.get("label", ""),
                "level": node.get("level", 1),
                "tag": node.get("tag", ""),
                "summary": node.get("summary", "")[:120],
            }
            flat_nodes.append(flat_node)

            if parent_id:
                flat_edges.append({
                    "source": parent_id,
                    "target": node_id,
                    "relation": "parent_child",
                })

            if children:
                child_nodes, child_edges = self._flatten_tree(
                    children, parent_id=node_id
                )
                flat_nodes.extend(child_nodes)
                flat_edges.extend(child_edges)

        return flat_nodes, flat_edges

    @staticmethod
    def _score_to_grade(score: float) -> str:
        """将 BOIS 评分转为等级。"""
        if score >= 90:
            return "A (优秀 - 结构优秀)"
        elif score >= 75:
            return "B (良好 - 结构合理)"
        elif score >= 60:
            return "C (合格 - 建议优化)"
        else:
            return "D (待改进 - 建议重建)"
