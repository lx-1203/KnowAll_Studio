"""Tests for MindMapAgent - BOIS theory driven mind map generation."""
import pytest
import sys
import os
import json as json_module
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.agents.base import AgentResult


class TestMindMapLabelsRelated:
    """Tests for MindMapAgent._labels_related()."""

    def test_labels_related_overlapping_characters(self):
        """_labels_related() returns True for overlapping character sets."""
        from app.core.agents.mindmap_agent import MindMapAgent

        assert MindMapAgent._labels_related("数据结构", "数据模型") is True

    def test_labels_related_no_overlap(self):
        """_labels_related() returns False for completely different labels."""
        from app.core.agents.mindmap_agent import MindMapAgent

        assert MindMapAgent._labels_related("数据结构", "编译原理") is False

    def test_labels_related_short_labels(self):
        """_labels_related() returns False for short labels (< 2 chars after filtering)."""
        from app.core.agents.mindmap_agent import MindMapAgent

        assert MindMapAgent._labels_related("的", "与") is False

    def test_labels_related_empty_labels(self):
        """_labels_related() returns False for empty labels."""
        from app.core.agents.mindmap_agent import MindMapAgent

        assert MindMapAgent._labels_related("", "") is False


class TestMindMapTreeJson:
    """Tests for _nodes_to_tree_json() and _flatten_tree()."""

    def test_nodes_to_tree_json_produces_nested_json(self):
        """_nodes_to_tree_json() produces valid nested JSON structure."""
        from app.core.agents.mindmap_agent import MindMapAgent

        agent = MindMapAgent()
        nodes = [
            {"id": "root", "level": 1, "title": "Root", "parent_id": None, "tag": "重点", "summary": "Root summary"},
            {"id": "child1", "level": 2, "title": "Child 1", "parent_id": "root", "tag": "", "summary": "Child 1 summary"},
            {"id": "child2", "level": 2, "title": "Child 2", "parent_id": "root", "tag": "", "summary": "Child 2 summary"},
        ]
        edges = [
            {"source": "root", "target": "child1", "relation": "parent_child"},
            {"source": "root", "target": "child2", "relation": "parent_child"},
        ]

        tree_json = agent._nodes_to_tree_json(nodes, edges)
        parsed = json_module.loads(tree_json)
        assert len(parsed) == 1  # One root
        assert parsed[0]["id"] == "root"
        assert len(parsed[0]["children"]) == 2

    def test_flatten_tree_round_trips(self):
        """_flatten_tree() round-trips correctly with _nodes_to_tree_json()."""
        from app.core.agents.mindmap_agent import MindMapAgent

        agent = MindMapAgent()

        # Build a tree and flatten it
        tree_nodes = [
            {
                "id": "root",
                "label": "Root",
                "level": 1,
                "tag": "重点",
                "summary": "Summary",
                "children": [
                    {
                        "id": "c1",
                        "label": "Child 1",
                        "level": 2,
                        "tag": "",
                        "summary": "Summary 1",
                        "children": [],
                    },
                    {
                        "id": "c2",
                        "label": "Child 2",
                        "level": 2,
                        "tag": "",
                        "summary": "Summary 2",
                        "children": [
                            {
                                "id": "gc1",
                                "label": "Grandchild",
                                "level": 3,
                                "tag": "",
                                "summary": "Summary gc",
                                "children": [],
                            }
                        ],
                    },
                ],
            }
        ]

        flat_nodes, flat_edges = agent._flatten_tree(tree_nodes)

        assert len(flat_nodes) == 4  # root + 2 children + 1 grandchild
        assert len(flat_edges) == 3  # 3 parent_child edges

        node_ids = {n["id"] for n in flat_nodes}
        assert "root" in node_ids
        assert "c1" in node_ids
        assert "c2" in node_ids
        assert "gc1" in node_ids

        edge_pairs = {(e["source"], e["target"]) for e in flat_edges}
        assert ("root", "c1") in edge_pairs
        assert ("root", "c2") in edge_pairs
        assert ("c2", "gc1") in edge_pairs


class TestMindMapScoreToGrade:
    """Tests for _score_to_grade()."""

    def test_score_to_grade_a(self):
        """_score_to_grade() returns A for score >= 90."""
        from app.core.agents.mindmap_agent import MindMapAgent

        assert "A" in MindMapAgent._score_to_grade(95)
        assert "A" in MindMapAgent._score_to_grade(90)

    def test_score_to_grade_b(self):
        """_score_to_grade() returns B for 75 <= score < 90."""
        from app.core.agents.mindmap_agent import MindMapAgent

        assert "B" in MindMapAgent._score_to_grade(80)
        assert "B" in MindMapAgent._score_to_grade(75)

    def test_score_to_grade_c(self):
        """_score_to_grade() returns C for 60 <= score < 75."""
        from app.core.agents.mindmap_agent import MindMapAgent

        assert "C" in MindMapAgent._score_to_grade(65)
        assert "C" in MindMapAgent._score_to_grade(60)

    def test_score_to_grade_d(self):
        """_score_to_grade() returns D for score < 60."""
        from app.core.agents.mindmap_agent import MindMapAgent

        assert "D" in MindMapAgent._score_to_grade(40)
        assert "D" in MindMapAgent._score_to_grade(0)


class TestMindMapBuildAndEnhance:
    """Tests for _build_mindmap() and _bois_edge_enhancement()."""

    def test_build_mindmap_creates_correct_parent_child_edges(self):
        """_build_mindmap() creates correct parent_child edges."""
        from app.core.agents.mindmap_agent import MindMapAgent

        agent = MindMapAgent()
        nodes = [
            {"id": "root", "level": 1, "title": "Root", "parent_id": None, "tag": "重点", "summary": "R"},
            {"id": "c1", "level": 2, "title": "Child 1", "parent_id": "root", "tag": "", "summary": "C1"},
            {"id": "c2", "level": 2, "title": "Child 2", "parent_id": "root", "tag": "", "summary": "C2"},
            {"id": "orphan", "level": 2, "title": "Orphan", "parent_id": "nonexistent", "tag": "", "summary": "O"},
        ]
        mindmap_nodes, mindmap_edges = agent._build_mindmap(nodes)

        assert len(mindmap_nodes) == 4
        # parent_child edges only for nodes with existing parent in node_map
        edge_pairs = {(e["source"], e["target"]) for e in mindmap_edges if e["relation"] == "parent_child"}
        assert ("root", "c1") in edge_pairs
        assert ("root", "c2") in edge_pairs
        # orphan should not have a parent_child edge (parent doesn't exist)
        assert not any(e["target"] == "orphan" and e["relation"] == "parent_child" for e in mindmap_edges)

    def test_bois_edge_enhancement_adds_cross_references(self):
        """_bois_edge_enhancement() adds cross_reference edges for related labels."""
        from app.core.agents.mindmap_agent import MindMapAgent

        agent = MindMapAgent()
        nodes = [
            {"id": "r1", "label": "数据结构", "level": 1, "tag": ""},
            {"id": "c1a", "label": "线性表", "level": 2, "tag": ""},
            {"id": "r2", "label": "数据模型", "level": 1, "tag": ""},
            {"id": "c2a", "label": "关系模型", "level": 2, "tag": ""},
        ]
        edges = [
            {"source": "r1", "target": "c1a", "relation": "parent_child"},
            {"source": "r2", "target": "c2a", "relation": "parent_child"},
        ]

        enhanced = agent._bois_edge_enhancement(nodes, edges)
        assert len(enhanced) >= len(edges)


class TestMindMapRun:
    """Tests for MindMapAgent.run() method."""

    @pytest.mark.asyncio
    async def test_run_with_missing_summary_returns_error(self):
        """run() with missing summary returns error AgentResult."""
        from app.core.agents.mindmap_agent import MindMapAgent

        agent = MindMapAgent()

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await agent.run(summary_id="bad_sum", document_id="doc_1")

        assert result.status == "error"
        assert "Summary not found" in result.error

    @pytest.mark.asyncio
    async def test_run_with_empty_nodes_returns_error(self):
        """run() with empty nodes returns error."""
        from app.core.agents.mindmap_agent import MindMapAgent

        agent = MindMapAgent()

        mock_summary = MagicMock()
        mock_summary.id = "sum_1"
        mock_summary.content_md = ""

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_summary)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch(
                "app.core.agents.mindmap_agent.summary_generator.extract_nodes_from_markdown",
                return_value=[],
            ):
                result = await agent.run(summary_id="sum_1", document_id="doc_1")

        assert result.status == "error"
        assert "No knowledge point nodes found" in result.error

    @pytest.mark.asyncio
    async def test_run_with_successful_build(self):
        """run() successfully builds a mindmap with BOIS metrics when valid nodes exist."""
        from app.core.agents.mindmap_agent import MindMapAgent

        agent = MindMapAgent()

        mock_summary = MagicMock()
        mock_summary.id = "sum_1"
        mock_summary.content_md = "# Test"

        nodes = [
            MagicMock(id="root", parent_id=None, level=1, sequence=1, title="Root", tags=["重点"], explanation="Root explanation."),
            MagicMock(id="c1", parent_id="root", level=2, sequence=1, title="Child 1", tags=[], explanation="Child 1 explanation text."),
            MagicMock(id="c2", parent_id="root", level=2, sequence=2, title="Child 2", tags=[], explanation="Child 2 explanation text."),
        ]

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_summary)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = nodes
        mock_node_result = MagicMock()
        mock_node_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_node_result)

        # Mock _load_cross_edges inner execute
        # The _load_cross_edges does two selections internally
        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            # Mock BOIS analyzer
            with patch("app.core.agents.mindmap_agent.bois_analyzer") as mock_bois:
                mock_metrics = MagicMock()
                mock_metrics.bois_score = 85.0
                mock_metrics.max_depth = 2
                mock_metrics.depth_distribution = {1: 1, 2: 2}
                mock_metrics.avg_children_per_node = 1.0
                mock_metrics.branching_factor = 0.67
                mock_metrics.hierarchy_balance = 0.8
                mock_metrics.coverage_completeness = 0.9
                mock_metrics.peer_variance = 1.0
                mock_metrics.suggestions = ["Add more detail at L3"]
                mock_metrics.category_framework = {}
                mock_metrics.total_nodes = 3

                mock_bois.analyze.return_value = mock_metrics
                mock_bois.suggest_restructure.return_value = {"suggestions": []}

                result = await agent.run(summary_id="sum_1", document_id="doc_1")

        assert result.status == "success"
        assert result.result["total_nodes"] == 3
        assert result.result["total_edges"] >= 2  # At least 2 parent-child edges
        assert result.result["bois_metrics"]["score"] == 85.0
        assert result.result["bois_metrics"]["grade"] is not None

    @pytest.mark.asyncio
    async def test_run_triggers_llm_restructure_below_threshold(self):
        """run() triggers LLM restructure when BOIS score below threshold."""
        from app.core.agents.mindmap_agent import MindMapAgent

        agent = MindMapAgent()

        mock_summary = MagicMock()
        mock_summary.id = "sum_1"
        mock_summary.content_md = "# Test"

        nodes = [
            MagicMock(id="root", parent_id=None, level=1, sequence=1, title="Root", tags=["重点"], explanation="Root."),
            MagicMock(id="c1", parent_id="root", level=2, sequence=1, title="Child", tags=[], explanation="Child."),
        ]

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_summary)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = nodes
        mock_node_result = MagicMock()
        mock_node_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_node_result)

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch("app.core.agents.mindmap_agent.bois_analyzer") as mock_bois:
                # Score below threshold (70)
                mock_metrics = MagicMock()
                mock_metrics.bois_score = 50.0
                mock_metrics.max_depth = 1
                mock_metrics.depth_distribution = {1: 1, 2: 1}
                mock_metrics.avg_children_per_node = 1.0
                mock_metrics.branching_factor = 0.5
                mock_metrics.hierarchy_balance = 0.5
                mock_metrics.coverage_completeness = 0.5
                mock_metrics.peer_variance = 1.0
                mock_metrics.suggestions = []
                mock_metrics.category_framework = {}
                mock_metrics.total_nodes = 2

                mock_bois.analyze.return_value = mock_metrics
                mock_bois.suggest_restructure.return_value = {"suggestions": []}

                # Mock LLM restructure to be called
                with patch.object(agent, "_llm_bois_restructure", new_callable=AsyncMock) as mock_llm:
                    mock_llm.return_value = None  # LLM returns None (failed)
                    result = await agent.run(summary_id="sum_1", document_id="doc_1")

        assert result.status == "success"
        mock_llm.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_skips_llm_restructure_above_threshold(self):
        """run() skips LLM restructure when BOIS score above threshold."""
        from app.core.agents.mindmap_agent import MindMapAgent

        agent = MindMapAgent()

        mock_summary = MagicMock()
        mock_summary.id = "sum_1"
        mock_summary.content_md = "# Test"

        nodes = [
            MagicMock(id="root", parent_id=None, level=1, sequence=1, title="Root", tags=["重点"], explanation="Root."),
            MagicMock(id="c1", parent_id="root", level=2, sequence=1, title="Child", tags=[], explanation="Child."),
        ]

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_summary)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = nodes
        mock_node_result = MagicMock()
        mock_node_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_node_result)

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch("app.core.agents.mindmap_agent.bois_analyzer") as mock_bois:
                mock_metrics = MagicMock()
                mock_metrics.bois_score = 85.0  # Above threshold
                mock_metrics.max_depth = 2
                mock_metrics.depth_distribution = {1: 1, 2: 1}
                mock_metrics.avg_children_per_node = 1.0
                mock_metrics.branching_factor = 0.5
                mock_metrics.hierarchy_balance = 0.8
                mock_metrics.coverage_completeness = 0.8
                mock_metrics.peer_variance = 0.5
                mock_metrics.suggestions = []
                mock_metrics.category_framework = {}
                mock_metrics.total_nodes = 2

                mock_bois.analyze.return_value = mock_metrics
                mock_bois.suggest_restructure.return_value = {"suggestions": []}

                with patch.object(agent, "_llm_bois_restructure", new_callable=AsyncMock) as mock_llm:
                    result = await agent.run(summary_id="sum_1", document_id="doc_1")

        assert result.status == "success"
        mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_force_restructure_triggers_llm_regardless_of_score(self):
        """run() with force_restructure=True triggers LLM regardless of score."""
        from app.core.agents.mindmap_agent import MindMapAgent

        agent = MindMapAgent()

        mock_summary = MagicMock()
        mock_summary.id = "sum_1"
        mock_summary.content_md = "# Test"

        nodes = [
            MagicMock(id="root", parent_id=None, level=1, sequence=1, title="Root", tags=["重点"], explanation="Root."),
            MagicMock(id="c1", parent_id="root", level=2, sequence=1, title="Child", tags=[], explanation="Child."),
        ]

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_summary)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = nodes
        mock_node_result = MagicMock()
        mock_node_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_node_result)

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch("app.core.agents.mindmap_agent.bois_analyzer") as mock_bois:
                mock_metrics = MagicMock()
                mock_metrics.bois_score = 95.0
                mock_metrics.max_depth = 2
                mock_metrics.depth_distribution = {1: 1, 2: 1}
                mock_metrics.avg_children_per_node = 1.0
                mock_metrics.branching_factor = 0.5
                mock_metrics.hierarchy_balance = 0.9
                mock_metrics.coverage_completeness = 0.9
                mock_metrics.peer_variance = 0.2
                mock_metrics.suggestions = []
                mock_metrics.category_framework = {}
                mock_metrics.total_nodes = 2

                mock_bois.analyze.return_value = mock_metrics
                mock_bois.suggest_restructure.return_value = {"suggestions": []}

                with patch.object(agent, "_llm_bois_restructure", new_callable=AsyncMock) as mock_llm:
                    mock_llm.return_value = None
                    result = await agent.run(
                        summary_id="sum_1", document_id="doc_1",
                        force_restructure=True,
                    )

        assert result.status == "success"
        mock_llm.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_disable_bois_llm_disables_restructure(self):
        """run() with enable_bois_llm=False disables LLM restructure."""
        from app.core.agents.mindmap_agent import MindMapAgent

        agent = MindMapAgent()

        mock_summary = MagicMock()
        mock_summary.id = "sum_1"
        mock_summary.content_md = "# Test"

        nodes = [
            MagicMock(id="root", parent_id=None, level=1, sequence=1, title="Root", tags=["重点"], explanation="Root."),
            MagicMock(id="c1", parent_id="root", level=2, sequence=1, title="Child", tags=[], explanation="Child."),
        ]

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_summary)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = nodes
        mock_node_result = MagicMock()
        mock_node_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_node_result)

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch("app.core.agents.mindmap_agent.bois_analyzer") as mock_bois:
                mock_metrics = MagicMock()
                mock_metrics.bois_score = 40.0  # Below threshold
                mock_metrics.max_depth = 2
                mock_metrics.depth_distribution = {1: 1, 2: 1}
                mock_metrics.avg_children_per_node = 1.0
                mock_metrics.branching_factor = 0.5
                mock_metrics.hierarchy_balance = 0.5
                mock_metrics.coverage_completeness = 0.5
                mock_metrics.peer_variance = 1.0
                mock_metrics.suggestions = []
                mock_metrics.category_framework = {}
                mock_metrics.total_nodes = 2

                mock_bois.analyze.return_value = mock_metrics
                mock_bois.suggest_restructure.return_value = {"suggestions": []}

                with patch.object(agent, "_llm_bois_restructure", new_callable=AsyncMock) as mock_llm:
                    result = await agent.run(
                        summary_id="sum_1", document_id="doc_1",
                        enable_bois_llm=False,
                    )

        assert result.status == "success"
        mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_skips_llm_restructure_when_node_count_exceeds_max(self):
        """run() skips LLM restructure when node count > MAX_LLM_NODES."""
        from app.core.agents.mindmap_agent import MindMapAgent

        agent = MindMapAgent()

        mock_summary = MagicMock()
        mock_summary.id = "sum_1"
        mock_summary.content_md = "# Test"

        # Create more than MAX_LLM_NODES (200) to verify the skip
        nodes = []
        for i in range(201):
            n = MagicMock()
            n.id = f"n_{i}"
            n.parent_id = "root" if i > 0 else None
            n.level = 1 if i == 0 else 2
            n.sequence = i
            n.title = f"Node {i}"
            n.tags = []
            n.explanation = f"Explanation {i}"
            nodes.append(n)

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_summary)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = nodes
        mock_node_result = MagicMock()
        mock_node_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_node_result)

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch("app.core.agents.mindmap_agent.bois_analyzer") as mock_bois:
                mock_metrics = MagicMock()
                mock_metrics.bois_score = 30.0
                mock_metrics.max_depth = 2
                mock_metrics.depth_distribution = {}
                mock_metrics.avg_children_per_node = 1.0
                mock_metrics.branching_factor = 0.5
                mock_metrics.hierarchy_balance = 0.5
                mock_metrics.coverage_completeness = 0.5
                mock_metrics.peer_variance = 1.0
                mock_metrics.suggestions = []
                mock_metrics.category_framework = {}
                mock_metrics.total_nodes = 201

                mock_bois.analyze.return_value = mock_metrics
                mock_bois.suggest_restructure.return_value = {"suggestions": []}

                with patch.object(agent, "_llm_bois_restructure", new_callable=AsyncMock) as mock_llm:
                    result = await agent.run(summary_id="sum_1", document_id="doc_1")

        assert result.status == "success"
        # Should NOT call LLM restructure due to node count exceeding max
        mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_restructure_handles_json_parse_failure(self):
        """_llm_bois_restructure() handles JSON parse failure gracefully."""
        from app.core.agents.mindmap_agent import MindMapAgent
        from app.core.knowledge.bois_analyzer import BOISMetrics

        agent = MindMapAgent()

        nodes = [{"id": "r", "label": "Root", "level": 1, "tag": "", "summary": ""}]
        edges = []
        metrics = BOISMetrics()
        metrics.total_nodes = 1
        metrics.max_depth = 1
        metrics.depth_distribution = {1: 1}

        with patch("app.core.agents.mindmap_agent.prompt_engine") as mock_pe:
            mock_pe.render.return_value = [{"role": "system", "content": "test"}]
            with patch("app.core.agents.mindmap_agent.api_client") as mock_api:
                mock_llm_result = MagicMock()
                mock_llm_result.content = "This is not JSON at all"
                mock_api.generate = AsyncMock(return_value=mock_llm_result)

                result = await agent._llm_bois_restructure(nodes, edges, metrics)

        assert result is None

    @pytest.mark.asyncio
    async def test_run_handles_db_exception_gracefully(self):
        """run() handles DB exception gracefully."""
        from app.core.agents.mindmap_agent import MindMapAgent

        agent = MindMapAgent()

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.side_effect = RuntimeError("DB not available")

            result = await agent.run(summary_id="sum_1", document_id="doc_1")

        assert result.status == "error"
        assert "DB not available" in result.error
