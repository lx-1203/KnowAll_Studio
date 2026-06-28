"""Comprehensive tests for BOISAnalyzer.

Tests the BOIS (Basic Ordering Ideas) Analyzer based on Tony Buzan's
mind map theory, covering analysis, scoring, suggestions, and restructuring.
"""
import pytest
from unittest.mock import MagicMock, patch

from app.core.knowledge.bois_analyzer import (
    BOISAnalyzer,
    BOISMetrics,
    bois_analyzer,
)


# ---------------------------------------------------------------------------
# Helper factories to build node/edge test data
# ---------------------------------------------------------------------------

def _node(id_, label, level, parent_id=None):
    """Create a single node dict."""
    return {"id": id_, "label": label, "level": level, "parent_id": parent_id}


def _edge(source, target, relation="parent_child"):
    """Create a single edge dict."""
    return {"source": source, "target": target, "relation": relation}


def _make_perfect_3level_tree():
    """Return (nodes, edges) for a perfectly balanced 3-level tree.

    Structure:
      L1 (root): n1
        L2 children: n2, n3, n4  (3 children, each with 3 L3 children)
          L3 grandchildren: 9 nodes total
    """
    nodes = [_node("N1", "Root", 1)]

    edges = []
    l3_counter = 0
    for l2_idx in range(1, 4):
        l2_id = f"N2_{l2_idx}"
        nodes.append(_node(l2_id, f"Topic {l2_idx}", 2, parent_id="N1"))
        edges.append(_edge("N1", l2_id))
        for l3_idx in range(1, 4):
            l3_counter += 1
            l3_id = f"N3_{l2_idx}_{l3_idx}"
            nodes.append(_node(l3_id, f"Subtopic {l3_counter}", 3, parent_id=l2_id))
            edges.append(_edge(l2_id, l3_id))

    return nodes, edges


def _make_flat_nodes():
    """Return (nodes, edges) for a single-level flat list (no hierarchy)."""
    nodes = [_node(f"F{i}", f"Flat {i}", 1) for i in range(1, 8)]
    return nodes, []


def _make_two_level_tree():
    """Return (nodes, edges) for a 2-level tree (L1 root + L2 children)."""
    nodes = [_node("R1", "Root", 1)]
    edges = []
    for i in range(1, 6):
        nid = f"C{i}"
        nodes.append(_node(nid, f"Child {i}", 2, parent_id="R1"))
        edges.append(_edge("R1", nid))
    return nodes, edges


def _make_orphan_nodes():
    """Return (nodes, edges) with orphan nodes (L2 nodes with parent_id but no edge)."""
    nodes = [
        _node("N1", "Root", 1),
        _node("N2", "Child OK", 2, parent_id="N1"),
        _node("N3", "Orphan 1", 2, parent_id="N1"),  # parent_id set but no edge
        _node("N4", "Orphan 2", 3, parent_id="N9"),  # parent doesn't exist
    ]
    edges = [_edge("N1", "N2")]
    return nodes, edges


def _make_gap_tree():
    """Return (nodes, edges) with a level gap: L1 -> L3, missing L2."""
    nodes = [
        _node("G1", "Root", 1),
        _node("G2", "L2 node", 2, parent_id="G1"),
        _node("G3", "Should-be L3 (orphan path)", 3, parent_id="G2"),
        _node("G4", "Direct L3 from root", 3, parent_id="G1"),  # L1 -> L3 gap
    ]
    edges = [
        _edge("G1", "G2"),
        _edge("G2", "G3"),
        _edge("G1", "G4"),  # this creates a gap: L1 directly to L3
        # The path G1->G4 is a direct L1 to L3 jump, missing L2
        # But actually, the coverage function checks leaf-to-root paths
        # G4 is level 3, parent G1 is level 1, so there's a gap at level 2
        # G3 is level 3, parent G2 (level 2), parent G1 (level 1) - no gap
    ]
    return nodes, edges


# ---------------------------------------------------------------------------
# BOISMetrics dataclass tests
# ---------------------------------------------------------------------------

class TestBOISMetricsDefaults:
    """Tests for BOISMetrics dataclass default values."""

    def test_default_values_are_correct(self):
        """BOISMetrics default values should match the expected initial state."""
        m = BOISMetrics()
        assert m.total_nodes == 0
        assert m.total_edges == 0
        assert m.max_depth == 0
        assert m.depth_distribution == {}
        assert m.avg_children_per_node == 0.0
        assert m.branching_factor == 0.0
        assert m.hierarchy_balance == 0.0
        assert m.coverage_completeness == 0.0
        assert m.peer_groups == {}
        assert m.peer_variance == 0.0
        assert m.orphan_nodes == 0
        assert m.shallow_nodes == 0
        assert m.deep_nodes == 0
        assert m.bois_score == 0.0
        assert m.suggestions == []
        assert m.category_framework == {}

    def test_can_override_individual_fields(self):
        """BOISMetrics fields can be individually set via constructor."""
        m = BOISMetrics(total_nodes=10, bois_score=85.5)
        assert m.total_nodes == 10
        assert m.bois_score == 85.5
        assert m.total_edges == 0  # unchanged default


# ---------------------------------------------------------------------------
# analyze() method tests
# ---------------------------------------------------------------------------

class TestBOISAnalyzerAnalyze:
    """Tests for BOISAnalyzer.analyze()."""

    def test_analyze_empty_nodes_returns_score_zero(self):
        """analyze() with empty nodes returns score 0 and meaningful suggestions."""
        analyzer = BOISAnalyzer()
        metrics = analyzer.analyze([], [])
        assert metrics.bois_score == 0.0
        assert metrics.total_nodes == 0
        assert metrics.total_edges == 0
        assert metrics.max_depth == 0
        assert len(metrics.suggestions) > 0
        assert "无节点数据" in metrics.suggestions[0]

    def test_analyze_perfect_3level_tree_high_score(self):
        """analyze() with a balanced 3-level tree returns high score (>= 85)."""
        nodes, edges = _make_perfect_3level_tree()
        analyzer = BOISAnalyzer()
        metrics = analyzer.analyze(nodes, edges)
        assert metrics.bois_score >= 85, f"Expected >= 85, got {metrics.bois_score}"
        assert metrics.total_nodes == 13  # 1 root + 3 L2 + 9 L3
        assert metrics.total_edges == 12
        assert metrics.max_depth == 3

    def test_analyze_single_level_flat_list_low_score(self):
        """analyze() with a flat single-level list returns low score."""
        nodes, edges = _make_flat_nodes()
        analyzer = BOISAnalyzer()
        metrics = analyzer.analyze(nodes, edges)
        assert metrics.bois_score < 60, f"Expected < 60 for flat list, got {metrics.bois_score}"
        assert metrics.max_depth == 1
        assert metrics.total_edges == 0

    def test_analyze_detects_orphan_nodes(self):
        """analyze() detects orphan nodes -- those with parent_id but no edge."""
        nodes, edges = _make_orphan_nodes()
        analyzer = BOISAnalyzer()
        metrics = analyzer.analyze(nodes, edges)
        assert metrics.orphan_nodes > 0, f"Expected orphan nodes > 0, got {metrics.orphan_nodes}"

    def test_analyze_detects_missing_intermediate_levels(self):
        """analyze() detects gaps where L1 connects directly to L3 without L2."""
        nodes, edges = _make_gap_tree()
        analyzer = BOISAnalyzer()
        metrics = analyzer.analyze(nodes, edges)
        # coverage_completeness should be < 1.0 because of the L1->L3 gap
        assert metrics.coverage_completeness < 1.0

    def test_analyze_two_level_tree(self):
        """analyze() with a 2-level tree (depth <= 2) gets full coverage score."""
        nodes, edges = _make_two_level_tree()
        analyzer = BOISAnalyzer()
        metrics = analyzer.analyze(nodes, edges)
        assert metrics.coverage_completeness == 1.0
        assert metrics.max_depth == 2

    def test_analyze_all_nodes_no_edges(self):
        """analyze() handles nodes without any edges (all root-level)."""
        nodes = [
            _node("R1", "Root1", 1),
            _node("R2", "Root2", 1),
            _node("R3", "Root3", 1),
        ]
        analyzer = BOISAnalyzer()
        metrics = analyzer.analyze(nodes, [])
        assert metrics.total_nodes == 3
        assert metrics.total_edges == 0
        assert metrics.avg_children_per_node == 0.0
        assert metrics.branching_factor == 0.0

    def test_analyze_single_node(self):
        """analyze() with a single node returns valid metrics."""
        nodes = [_node("S1", "Solo", 1)]
        analyzer = BOISAnalyzer()
        metrics = analyzer.analyze(nodes, [])
        assert metrics.total_nodes == 1
        assert metrics.max_depth == 1
        assert metrics.orphan_nodes == 0
        assert metrics.bois_score is not None

    def test_analyze_counts_deep_nodes_correctly(self):
        """analyze() counts nodes at level >= 3 as deep_nodes."""
        nodes = [
            _node("A", "Root", 1),
            _node("B", "L2", 2, parent_id="A"),
            _node("C", "L3", 3, parent_id="B"),
            _node("D", "L3-2", 3, parent_id="B"),
            _node("E", "L4", 4, parent_id="C"),
        ]
        edges = [
            _edge("A", "B"),
            _edge("B", "C"),
            _edge("B", "D"),
            _edge("C", "E"),
        ]
        analyzer = BOISAnalyzer()
        metrics = analyzer.analyze(nodes, edges)
        # Nodes at level >= 3: C(3), D(3), E(4) = 3 deep_nodes
        assert metrics.deep_nodes == 3
        assert metrics.max_depth == 4


# ---------------------------------------------------------------------------
# _compute_balance() tests
# ---------------------------------------------------------------------------

class TestComputeBalance:
    """Tests for BOISAnalyzer._compute_balance()."""

    def test_ideal_ratio_returns_full_score(self):
        """_compute_balance returns 1.0 for ideal ratio (1.5-5.0) between levels."""
        analyzer = BOISAnalyzer()
        # level 1: 2 nodes, level 2: 6 nodes (ratio 3.0, in ideal range)
        # level 2: 6 nodes, level 3: 18 nodes (ratio 3.0, in ideal range)
        peer_groups = {1: ["a", "b"], 2: ["c"] * 6, 3: ["d"] * 18}
        balance = analyzer._compute_balance(peer_groups, 3)
        assert balance == 1.0, f"Expected 1.0, got {balance}"

    def test_inverted_ratio_returns_low_score(self):
        """_compute_balance returns low score when lower levels have fewer nodes."""
        analyzer = BOISAnalyzer()
        # level 1: 10 nodes, level 2: 3 nodes (inverted: less detailed as we go deeper)
        peer_groups = {1: ["a"] * 10, 2: ["b"] * 3}
        balance = analyzer._compute_balance(peer_groups, 2)
        assert balance == 0.3, f"Expected 0.3 for inverted ratio, got {balance}"

    def test_single_level_returns_neutral(self):
        """_compute_balance returns 0.5 when only one level exists."""
        analyzer = BOISAnalyzer()
        peer_groups = {1: ["a", "b", "c"]}
        balance = analyzer._compute_balance(peer_groups, 1)
        assert balance == 0.5

    def test_zero_prev_count_returns_zero(self):
        """_compute_balance handles zero nodes in a previous level gracefully."""
        analyzer = BOISAnalyzer()
        peer_groups = {1: [], 2: ["b1", "b2"]}
        balance = analyzer._compute_balance(peer_groups, 2)
        # ratio for level 1->2: prev_count=0 so score is 0.0
        assert balance == 0.0

    def test_overexpansion_returns_moderate_score(self):
        """_compute_balance gives 0.4 when expansion ratio exceeds 7.0."""
        analyzer = BOISAnalyzer()
        # level 1: 1 node, level 2: 20 nodes (ratio 20, > 7.0)
        peer_groups = {1: ["a"], 2: ["b"] * 20}
        balance = analyzer._compute_balance(peer_groups, 2)
        assert balance == 0.4, f"Expected 0.4 for overexpansion, got {balance}"

    def test_slightly_low_ratio_returns_moderate(self):
        """_compute_balance gives 0.7 when ratio is between 1.0 and 1.5."""
        analyzer = BOISAnalyzer()
        peer_groups = {1: ["a", "b", "c"], 2: ["d"] * 4}  # ratio 4/3 = 1.33
        balance = analyzer._compute_balance(peer_groups, 2)
        assert balance == 0.7, f"Expected 0.7 for slightly low ratio, got {balance}"


# ---------------------------------------------------------------------------
# _compute_coverage() tests
# ---------------------------------------------------------------------------

class TestComputeCoverage:
    """Tests for BOISAnalyzer._compute_coverage()."""

    def test_depth_two_or_less_returns_full(self):
        """_compute_coverage returns 1.0 for trees with max_depth <= 2."""
        analyzer = BOISAnalyzer()
        nodes = [_node("A", "Root", 1), _node("B", "Child", 2, parent_id="A")]
        children_map = {"A": ["B"]}
        parent_map = {"B": "A"}
        coverage = analyzer._compute_coverage(nodes, children_map, parent_map, max_depth=2)
        assert coverage == 1.0

    def test_depth_one_returns_full(self):
        """_compute_coverage returns 1.0 for flat depth-1 tree."""
        analyzer = BOISAnalyzer()
        nodes = [_node("A", "Root", 1)]
        children_map = {}
        parent_map = {}
        coverage = analyzer._compute_coverage(nodes, children_map, parent_map, max_depth=1)
        assert coverage == 1.0

    def test_penalizes_level_gaps(self):
        """_compute_coverage penalizes trees where intermediate levels are missing."""
        analyzer = BOISAnalyzer()
        # G1(L1) -> G4(L3): direct L1->L3, level 2 is missing in this path
        nodes = [
            _node("G1", "Root", 1),
            _node("G4", "Deep child", 3, parent_id="G1"),
        ]
        children_map = {"G1": ["G4"]}
        parent_map = {"G4": "G1"}
        coverage = analyzer._compute_coverage(nodes, children_map, parent_map, max_depth=3)
        assert coverage < 1.0

    def test_perfect_tree_no_gaps(self):
        """_compute_coverage returns 1.0 for a tree with no level gaps."""
        analyzer = BOISAnalyzer()
        nodes = [
            _node("A", "Root", 1),
            _node("B", "L2", 2, parent_id="A"),
            _node("C", "L3", 3, parent_id="B"),
        ]
        children_map = {"A": ["B"], "B": ["C"]}
        parent_map = {"B": "A", "C": "B"}
        coverage = analyzer._compute_coverage(nodes, children_map, parent_map, max_depth=3)
        assert coverage == 1.0

    def test_no_leaves_returns_full(self):
        """_compute_coverage returns 1.0 when there are no leaf paths to check."""
        analyzer = BOISAnalyzer()
        nodes = []
        children_map = {}
        parent_map = {}
        coverage = analyzer._compute_coverage(nodes, children_map, parent_map, max_depth=3)
        assert coverage == 1.0


# ---------------------------------------------------------------------------
# _compute_score() tests
# ---------------------------------------------------------------------------

class TestComputeScore:
    """Tests for BOISAnalyzer._compute_score()."""

    def test_perfect_subscores_equals_100(self):
        """_compute_score with all perfect sub-scores equals 100."""
        analyzer = BOISAnalyzer()
        m = BOISMetrics()
        m.total_nodes = 10
        m.max_depth = 3  # between IDEAL_MIN(2) and IDEAL_MAX(4) -> 100
        m.avg_children_per_node = 3.0  # between 2 and 7 -> 100
        m.hierarchy_balance = 1.0  # -> 100
        m.coverage_completeness = 1.0  # -> 100
        m.orphan_nodes = 0  # -> 100
        score = analyzer._compute_score(m)
        assert score == 100.0, f"Expected 100, got {score}"

    def test_max_depth_zero_scores_zero_hierarchy(self):
        """_compute_score gives 0 for hierarchy dimension when max_depth is 0."""
        analyzer = BOISAnalyzer()
        m = BOISMetrics()
        m.total_nodes = 5
        m.max_depth = 0
        m.avg_children_per_node = 0
        m.hierarchy_balance = 0.5
        m.coverage_completeness = 1.0
        m.orphan_nodes = 0
        score = analyzer._compute_score(m)
        # hierarchy=0 (30%), branching=0 (25%), balance=50*0.2, coverage=100*0.15, connectivity=100*0.10
        expected = 0 * 0.30 + 0 * 0.25 + 50 * 0.20 + 100 * 0.15 + 100 * 0.10
        assert score == expected

    def test_single_node_connectivity_full(self):
        """_compute_score gives full connectivity for single-node graph."""
        analyzer = BOISAnalyzer()
        m = BOISMetrics()
        m.total_nodes = 1
        m.max_depth = 1
        m.avg_children_per_node = 0
        m.hierarchy_balance = 0.5
        m.coverage_completeness = 1.0
        m.orphan_nodes = 1  # but total_nodes=1 so connectivity = 100
        score = analyzer._compute_score(m)
        assert score >= 0

    def test_orphans_penalize_connectivity(self):
        """_compute_score penalizes connectivity proportionally to orphan ratio."""
        analyzer = BOISAnalyzer()
        m = BOISMetrics()
        m.total_nodes = 10
        m.max_depth = 2
        m.avg_children_per_node = 3.0
        m.hierarchy_balance = 1.0
        m.coverage_completeness = 1.0
        m.orphan_nodes = 3  # 30% orphans
        score = analyzer._compute_score(m)
        # connectivity = (1 - 3/10) * 100 = 70
        expected_connectivity = 70.0
        expected = (100 * 0.30 + 100 * 0.25 + 100 * 0.20 + 100 * 0.15 + 70 * 0.10)
        assert score == expected, f"Expected {expected}, got {score}"


# ---------------------------------------------------------------------------
# _generate_suggestions() tests
# ---------------------------------------------------------------------------

class TestGenerateSuggestions:
    """Tests for BOISAnalyzer._generate_suggestions()."""

    def test_shallow_tree_produces_hint(self):
        """_generate_suggestions produces hint for shallow trees (max_depth < 2)."""
        analyzer = BOISAnalyzer()
        m = BOISMetrics()
        m.max_depth = 1
        m.avg_children_per_node = 2.0
        m.hierarchy_balance = 0.5
        m.coverage_completeness = 1.0
        m.orphan_nodes = 0
        m.total_nodes = 10
        m.shallow_nodes = 2
        suggestions = analyzer._generate_suggestions(m)
        assert any("下找小类" in s for s in suggestions), f"Got: {suggestions}"

    def test_deep_tree_produces_hint(self):
        """_generate_suggestions produces hint for overly deep trees."""
        analyzer = BOISAnalyzer()
        m = BOISMetrics()
        m.max_depth = 7  # > IDEAL_MAX_DEPTH + 1 (5)
        m.avg_children_per_node = 2.0
        m.hierarchy_balance = 0.6
        m.coverage_completeness = 0.8
        m.orphan_nodes = 0
        m.total_nodes = 30
        m.shallow_nodes = 5
        suggestions = analyzer._generate_suggestions(m)
        assert any("收拢建议" in s for s in suggestions), f"Got: {suggestions}"

    def test_good_structure_positive_message(self):
        """_generate_suggestions produces positive message when tree structure is good."""
        analyzer = BOISAnalyzer()
        m = BOISMetrics()
        m.max_depth = 3  # ideal
        m.avg_children_per_node = 3.0  # good branching
        m.hierarchy_balance = 0.8  # good balance
        m.coverage_completeness = 0.9  # good coverage
        m.orphan_nodes = 0
        m.total_nodes = 20
        m.shallow_nodes = 5  # 25%, okay
        suggestions = analyzer._generate_suggestions(m)
        assert any("结构良好" in s for s in suggestions), f"Got: {suggestions}"

    def test_low_branching_produces_hint(self):
        """_generate_suggestions produces hint when avg_children_per_node < 1.5."""
        analyzer = BOISAnalyzer()
        m = BOISMetrics()
        m.max_depth = 3
        m.avg_children_per_node = 1.0
        m.hierarchy_balance = 0.6
        m.coverage_completeness = 0.8
        m.orphan_nodes = 0
        m.total_nodes = 10
        m.shallow_nodes = 2
        suggestions = analyzer._generate_suggestions(m)
        assert any("中找同类" in s for s in suggestions), f"Got: {suggestions}"

    def test_orphan_nodes_produces_hint(self):
        """_generate_suggestions produces hint for orphan nodes."""
        analyzer = BOISAnalyzer()
        m = BOISMetrics()
        m.max_depth = 3
        m.avg_children_per_node = 2.5
        m.hierarchy_balance = 0.6
        m.coverage_completeness = 0.8
        m.orphan_nodes = 3
        m.total_nodes = 10
        m.shallow_nodes = 2
        suggestions = analyzer._generate_suggestions(m)
        assert any("孤立节点" in s for s in suggestions), f"Got: {suggestions}"

    def test_excessive_shallow_nodes_hint(self):
        """_generate_suggestions warns when >60% nodes are shallow."""
        analyzer = BOISAnalyzer()
        m = BOISMetrics()
        m.max_depth = 3
        m.avg_children_per_node = 2.0
        m.hierarchy_balance = 0.6
        m.coverage_completeness = 0.8
        m.orphan_nodes = 0
        m.total_nodes = 10
        m.shallow_nodes = 8  # 80%
        suggestions = analyzer._generate_suggestions(m)
        assert any("发散不足" in s for s in suggestions), f"Got: {suggestions}"

    def test_low_coverage_produces_hint(self):
        """_generate_suggestions produces jump-level hint for low coverage."""
        analyzer = BOISAnalyzer()
        m = BOISMetrics()
        m.max_depth = 3
        m.avg_children_per_node = 2.0
        m.hierarchy_balance = 0.6
        m.coverage_completeness = 0.5  # < 0.7
        m.orphan_nodes = 0
        m.total_nodes = 10
        m.shallow_nodes = 3
        suggestions = analyzer._generate_suggestions(m)
        assert any("跳级检测" in s for s in suggestions), f"Got: {suggestions}"


# ---------------------------------------------------------------------------
# suggest_restructure() tests
# ---------------------------------------------------------------------------

class TestSuggestRestructure:
    """Tests for BOISAnalyzer.suggest_restructure()."""

    def test_identifies_single_child_for_merge(self):
        """suggest_restructure identifies single-child parents for merge."""
        analyzer = BOISAnalyzer()
        nodes = [
            _node("P1", "Parent", 1),
            _node("C1", "Only Child", 2, parent_id="P1"),
            _node("P2", "Parent2", 1),
            _node("C2a", "Child A", 2, parent_id="P2"),
            _node("C2b", "Child B", 2, parent_id="P2"),
        ]
        edges = [
            _edge("P1", "C1"),
            _edge("P2", "C2a"),
            _edge("P2", "C2b"),
        ]
        metrics = analyzer.analyze(nodes, edges)
        result = analyzer.suggest_restructure(nodes, edges, metrics)
        assert "merge_suggestions" in result
        assert len(result["merge_suggestions"]) >= 1
        # P1 has only 1 child (C1), should be a merge candidate
        merge_parents = [m["parent"]["id"] for m in result["merge_suggestions"]]
        assert "P1" in merge_parents

    def test_identifies_many_children_for_split(self):
        """suggest_restructure identifies nodes with > 7 children for split."""
        analyzer = BOISAnalyzer()
        nodes = [_node("BigParent", "Big", 1)]
        edges = []
        for i in range(1, 10):  # 9 children > IDEAL_MAX_CHILDREN (7)
            kid_id = f"K{i}"
            nodes.append(_node(kid_id, f"Kid {i}", 2, parent_id="BigParent"))
            edges.append(_edge("BigParent", kid_id))
        metrics = analyzer.analyze(nodes, edges)
        result = analyzer.suggest_restructure(nodes, edges, metrics)
        assert "split_suggestions" in result
        assert len(result["split_suggestions"]) >= 1
        assert result["split_suggestions"][0]["node"]["id"] == "BigParent"
        assert result["split_suggestions"][0]["child_count"] == 9

    def test_identifies_deep_nodes_for_reclassify(self):
        """suggest_restructure identifies nodes deeper than IDEAL_MAX_DEPTH."""
        analyzer = BOISAnalyzer()
        nodes = [
            _node("R", "Root", 1),
            _node("L2", "L2", 2, parent_id="R"),
            _node("L3", "L3", 3, parent_id="L2"),
            _node("L4", "L4", 4, parent_id="L3"),
            _node("L5", "Too Deep", 5, parent_id="L4"),
        ]
        edges = [
            _edge("R", "L2"),
            _edge("L2", "L3"),
            _edge("L3", "L4"),
            _edge("L4", "L5"),
        ]
        metrics = analyzer.analyze(nodes, edges)
        result = analyzer.suggest_restructure(nodes, edges, metrics)
        assert "reclassify_suggestions" in result
        # L5 is at level 5 > IDEAL_MAX_DEPTH (4), should be reclassified
        deep_ids = [r["node"]["id"] for r in result["reclassify_suggestions"]]
        assert "L5" in deep_ids

    def test_empty_nodes_returns_empty_suggestions(self):
        """suggest_restructure with empty nodes returns empty lists."""
        analyzer = BOISAnalyzer()
        metrics = analyzer.analyze([], [])
        result = analyzer.suggest_restructure([], [], metrics)
        assert result["merge_suggestions"] == []
        assert result["split_suggestions"] == []
        assert result["reclassify_suggestions"] == []


# ---------------------------------------------------------------------------
# _build_category_framework() tests
# ---------------------------------------------------------------------------

class TestBuildCategoryFramework:
    """Tests for BOISAnalyzer._build_category_framework()."""

    def test_separates_upper_middle_lower_categories(self):
        """_build_category_framework correctly separates L1/L2/L3+ nodes."""
        analyzer = BOISAnalyzer()
        nodes = [
            _node("A", "Upper1", 1),
            _node("B", "Upper2", 1),
            _node("C", "Middle1", 2),
            _node("D", "Middle2", 2),
            _node("E", "Lower1", 3),
            _node("F", "Lower2", 4),
        ]
        children_map = {"A": ["C"], "B": ["D"], "C": ["E"], "E": ["F"]}
        framework = analyzer._build_category_framework(nodes, children_map)
        assert len(framework["上位阶（大类）"]) == 2
        assert len(framework["中位阶（中类）"]) == 2
        assert len(framework["下位阶（小类）"]) == 2  # L3 + L4

    def test_empty_nodes_returns_empty_framework(self):
        """_build_category_framework returns empty lists for empty nodes."""
        analyzer = BOISAnalyzer()
        framework = analyzer._build_category_framework([], {})
        assert framework["上位阶（大类）"] == []
        assert framework["中位阶（中类）"] == []
        assert framework["下位阶（小类）"] == []

    def test_framework_contains_child_count_for_upper(self):
        """Upper categories include child_count."""
        analyzer = BOISAnalyzer()
        nodes = [_node("A", "Upper", 1), _node("B", "Child", 2)]
        children_map = {"A": ["B"]}
        framework = analyzer._build_category_framework(nodes, children_map)
        upper = framework["上位阶（大类）"][0]
        assert upper["id"] == "A"
        assert upper["child_count"] == 1


# ---------------------------------------------------------------------------
# Internal utility method tests
# ---------------------------------------------------------------------------

class TestInternalUtilities:
    """Tests for BOISAnalyzer internal utility methods."""

    def test_count_by_level_correct_distribution(self):
        """_count_by_level returns correct count per level."""
        analyzer = BOISAnalyzer()
        nodes = [
            {"id": "a", "level": 1},
            {"id": "b", "level": 1},
            {"id": "c", "level": 2},
            {"id": "d", "level": 3},
            {"id": "e", "level": 3},
        ]
        dist = analyzer._count_by_level(nodes)
        assert dist == {1: 2, 2: 1, 3: 2}

    def test_count_by_level_empty(self):
        """_count_by_level returns empty dict for empty nodes."""
        analyzer = BOISAnalyzer()
        dist = analyzer._count_by_level([])
        assert dist == {}

    def test_group_by_level_groups_correctly(self):
        """_group_by_level groups node labels by level."""
        analyzer = BOISAnalyzer()
        nodes = [
            {"id": "a", "level": 1, "label": "Root"},
            {"id": "b", "level": 2, "label": "Child A"},
            {"id": "c", "level": 2, "label": "Child B"},
            {"id": "d", "level": 3, "label": "Grandchild"},
        ]
        groups = analyzer._group_by_level(nodes)
        assert groups == {1: ["Root"], 2: ["Child A", "Child B"], 3: ["Grandchild"]}

    def test_compute_peer_variance_empty_groups(self):
        """_compute_peer_variance handles empty peer_groups."""
        analyzer = BOISAnalyzer()
        variance = analyzer._compute_peer_variance({})
        assert variance == 0.0

    def test_compute_peer_variance_single_element(self):
        """_compute_peer_variance returns 0.0 for single-element groups."""
        analyzer = BOISAnalyzer()
        variance = analyzer._compute_peer_variance({1: ["a"]})
        assert variance == 0.0

    def test_compute_peer_variance_uniform(self):
        """_compute_peer_variance returns 0.0 for perfectly uniform groups."""
        analyzer = BOISAnalyzer()
        groups = {1: ["a", "b", "c"], 2: ["d", "e", "f"], 3: ["g", "h", "i"]}
        variance = analyzer._compute_peer_variance(groups)
        assert variance == 0.0

    def test_compute_peer_variance_uneven(self):
        """_compute_peer_variance returns positive value for uneven groups."""
        analyzer = BOISAnalyzer()
        groups = {1: ["a"], 2: ["b", "c", "d", "e", "f"]}
        variance = analyzer._compute_peer_variance(groups)
        assert variance > 0.0

    def test_suggest_groups_clusters_by_prefix(self):
        """_suggest_groups clusters nodes by label prefix."""
        analyzer = BOISAnalyzer()
        children = [
            {"id": "n1", "label": "计算机网络"},
            {"id": "n2", "label": "计算机组成"},
            {"id": "n3", "label": "网络协议"},
        ]
        groups = analyzer._suggest_groups(children)
        # "计算机" prefix appears twice
        assert len(groups) >= 1

    def test_suggest_groups_single_node_no_group(self):
        """_suggest_groups does not create groups for single nodes."""
        analyzer = BOISAnalyzer()
        children = [
            {"id": "n1", "label": "独立概念"},
            {"id": "n2", "label": "另一个"},
        ]
        groups = analyzer._suggest_groups(children)
        assert len(groups) == 0  # No prefix shared by >= 2 nodes

    def test_module_level_singleton_exists(self):
        """The module-level bois_analyzer singleton is a BOISAnalyzer instance."""
        assert isinstance(bois_analyzer, BOISAnalyzer)
