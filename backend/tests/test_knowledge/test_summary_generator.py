"""Comprehensive tests for SummaryGenerator.

Tests the Markdown-to-knowledge-node extraction, tag detection,
title cleaning, explanation normalization, and level statistics.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.core.knowledge.summary_generator import (
    SummaryGenerator,
    summary_generator,
)


# ---------------------------------------------------------------------------
# extract_nodes_from_markdown() tests
# ---------------------------------------------------------------------------

class TestExtractNodesFromMarkdown:
    """Tests for SummaryGenerator.extract_nodes_from_markdown()."""

    def test_three_level_markdown_parses_correct_hierarchy(self, sample_markdown):
        """extract_nodes_from_markdown with 3-level Markdown parses correct hierarchy."""
        gen = SummaryGenerator()
        nodes = gen.extract_nodes_from_markdown(sample_markdown, "doc001")

        assert len(nodes) > 0

        levels = {n["level"] for n in nodes}
        assert 1 in levels
        assert 2 in levels
        assert 3 in levels

    def test_assigns_correct_parent_id(self, sample_markdown):
        """extract_nodes_from_markdown assigns correct parent_id based on heading hierarchy."""
        gen = SummaryGenerator()
        nodes = gen.extract_nodes_from_markdown(sample_markdown, "doc001")

        # Root-level (L1) nodes should have parent_id = None
        l1_nodes = [n for n in nodes if n["level"] == 1]
        for node in l1_nodes:
            assert node["parent_id"] is None, (
                f"L1 node {node['title']} should have parent_id=None, "
                f"got {node['parent_id']}"
            )

        # L2 nodes should have a parent_id pointing to an L1 node
        l2_nodes = [n for n in nodes if n["level"] == 2]
        for node in l2_nodes:
            assert node["parent_id"] is not None, (
                f"L2 node {node['title']} should have non-None parent_id"
            )
            parent = next((n for n in nodes if n["id"] == node["parent_id"]), None)
            assert parent is not None, (
                f"L2 node {node['title']} parent_id {node['parent_id']} not found"
            )
            assert parent["level"] == 1

        # L3 nodes should have a parent_id pointing to an L2 node
        l3_nodes = [n for n in nodes if n["level"] == 3]
        for node in l3_nodes:
            assert node["parent_id"] is not None, (
                f"L3 node {node['title']} should have non-None parent_id"
            )
            parent = next((n for n in nodes if n["id"] == node["parent_id"]), None)
            assert parent is not None, (
                f"L3 node {node['title']} parent_id {node['parent_id']} not found"
            )
            assert parent["level"] == 2

    def test_generates_correct_auto_ids(self):
        """extract_nodes_from_markdown generates correct auto-IDs (kp_doc_L1_01 format)."""
        gen = SummaryGenerator()
        md = """# First Topic
Some content.

## First Subtopic
More content.

### First Detail
Deep content.
"""
        nodes = gen.extract_nodes_from_markdown(md, "abc12345")

        # Nodes should be in order: L1, L2, L3
        assert len(nodes) == 3

        # Check ID format: kp_{doc_short}_L{level}_{sequence}
        l1_node = nodes[0]
        assert l1_node["id"] == "kp_abc12345_L1_01"
        assert l1_node["level"] == 1

        l2_node = nodes[1]
        assert l2_node["id"] == "kp_abc12345_L2_01_01"
        assert l2_node["level"] == 2

        l3_node = nodes[2]
        assert l3_node["id"] == "kp_abc12345_L3_01_01_01"
        assert l3_node["level"] == 3

    def test_extracts_related_concepts_from_explanation(self, sample_markdown):
        """extract_nodes_from_markdown extracts related_concepts from explanation text."""
        gen = SummaryGenerator()
        nodes = gen.extract_nodes_from_markdown(sample_markdown, "doc001")

        # Find nodes that should have related_concepts
        nodes_with_concepts = [n for n in nodes if n["related_concepts"]]
        assert len(nodes_with_concepts) > 0, (
            "Expected at least one node with related_concepts extracted"
        )

        # The "物理层" node has "关联概念：数据链路层、传输介质、信号编码"
        physical_layer = next(
            (n for n in nodes if "物理层" in n["title"]), None
        )
        assert physical_layer is not None
        assert physical_layer["related_concepts"] != ""
        assert "数据链路层" in physical_layer["related_concepts"]

    def test_extracts_examples_from_explanation(self, sample_markdown):
        """extract_nodes_from_markdown extracts examples from explanation text."""
        gen = SummaryGenerator()
        nodes = gen.extract_nodes_from_markdown(sample_markdown, "doc001")

        # Find nodes that should have examples
        nodes_with_examples = [n for n in nodes if n["examples"]]
        assert len(nodes_with_examples) > 0, (
            "Expected at least one node with examples extracted"
        )

        # The "数据链路层" node has "示例：以太网帧格式中..."
        data_link = next(
            (n for n in nodes if "数据链路层" in n["title"]), None
        )
        assert data_link is not None
        assert "以太网帧" in data_link["examples"]

    def test_handles_empty_markdown_gracefully(self):
        """extract_nodes_from_markdown handles empty string gracefully."""
        gen = SummaryGenerator()
        nodes = gen.extract_nodes_from_markdown("", "doc001")
        assert nodes == []

    def test_handles_markdown_with_no_headings(self):
        """extract_nodes_from_markdown handles Markdown with no headings."""
        gen = SummaryGenerator()
        md = "This is just plain text.\n\nNo headings here.\nJust paragraphs."
        nodes = gen.extract_nodes_from_markdown(md, "doc001")
        assert nodes == []

    def test_ignores_h4_and_deeper_headings(self):
        """extract_nodes_from_markdown ignores H4+ headings (only H1-H3)."""
        gen = SummaryGenerator()
        md = """# Level 1

## Level 2

### Level 3

#### Level 4 - Should Be Ignored

##### Level 5 - Should Be Ignored
"""
        nodes = gen.extract_nodes_from_markdown(md, "doc001")
        levels_found = {n["level"] for n in nodes}
        assert 4 not in levels_found
        assert 5 not in levels_found
        assert len(nodes) == 3  # Only H1, H2, H3

    def test_handles_deeply_nested_structures(self):
        """extract_nodes_from_markdown handles deeply nested heading structures."""
        gen = SummaryGenerator()
        md = """# Root

## Section A

### Sub A1

### Sub A2

## Section B

### Sub B1

### Sub B2

### Sub B3

## Section C

### Sub C1

### Sub C2
"""
        nodes = gen.extract_nodes_from_markdown(md, "doc001")

        # Count by level
        l1 = [n for n in nodes if n["level"] == 1]
        l2 = [n for n in nodes if n["level"] == 2]
        l3 = [n for n in nodes if n["level"] == 3]

        assert len(l1) == 1  # Root
        assert len(l2) == 3  # Section A, B, C
        assert len(l3) == 7  # Sub A1, A2, B1, B2, B3, C1, C2

        # Sub-nodes under Section A should have parent A
        section_a = next((n for n in l2 if "Section A" in n["title"]), None)
        assert section_a is not None
        sub_a_nodes = [n for n in l3 if n["parent_id"] == section_a["id"]]
        assert len(sub_a_nodes) == 2

    def test_sets_correct_level_for_h2_and_h3(self):
        """extract_nodes_from_markdown sets correct level values for H2 and H3."""
        gen = SummaryGenerator()
        md = """# Top
## Middle
### Bottom
"""
        nodes = gen.extract_nodes_from_markdown(md, "test")
        assert nodes[0]["level"] == 1
        assert nodes[1]["level"] == 2
        assert nodes[2]["level"] == 3

    def test_handles_consecutive_same_level_headings(self):
        """extract_nodes_from_markdown handles consecutive headings at the same level."""
        gen = SummaryGenerator()
        md = """# A
Content A.
# B
Content B.
# C
Content C.
"""
        nodes = gen.extract_nodes_from_markdown(md, "doc001")
        assert len(nodes) == 3
        for node in nodes:
            assert node["level"] == 1
            assert node["parent_id"] is None

    def test_empty_document_id_uses_doc_prefix(self):
        """extract_nodes_from_markdown with empty document_id uses 'doc' prefix."""
        gen = SummaryGenerator()
        md = """# Topic
Content.
"""
        nodes = gen.extract_nodes_from_markdown(md, "")
        assert len(nodes) == 1
        assert nodes[0]["id"].startswith("kp_doc_")

    def test_single_h1_with_content(self):
        """extract_nodes_from_markdown handles single H1 heading with content."""
        gen = SummaryGenerator()
        md = """# Single Topic
This is the explanation for a single topic.
It spans multiple lines.
"""
        nodes = gen.extract_nodes_from_markdown(md, "doc001")
        assert len(nodes) == 1
        assert nodes[0]["title"] == "Single Topic"
        assert "explanation for a single topic" in nodes[0]["explanation"]
        assert nodes[0]["level"] == 1
        assert nodes[0]["parent_id"] is None

    def test_explanation_text_is_preserved(self, sample_markdown):
        """extract_nodes_from_markdown preserves non-heading lines as explanation."""
        gen = SummaryGenerator()
        nodes = gen.extract_nodes_from_markdown(sample_markdown, "doc001")

        l1_nodes = [n for n in nodes if n["level"] == 1]
        assert len(l1_nodes) > 0
        root_node = l1_nodes[0]
        assert root_node["explanation"] != ""
        assert "计算机网络" in root_node["explanation"]


# ---------------------------------------------------------------------------
# _extract_tag() tests
# ---------------------------------------------------------------------------

class TestExtractTag:
    """Tests for SummaryGenerator._extract_tag()."""

    def test_detects_bikao_tag(self):
        """_extract_tag detects '必考' in title."""
        gen = SummaryGenerator()
        assert gen._extract_tag("OSI七层参考模型 必考") == "必考"
        assert gen._extract_tag("必考知识点汇总") == "必考"

    def test_detects_zhongdian_tag(self):
        """_extract_tag detects '重点' in title."""
        gen = SummaryGenerator()
        assert gen._extract_tag("TCP/IP协议栈 重点") == "重点"
        assert gen._extract_tag("重点内容回顾") == "重点"

    def test_detects_liaojie_tag(self):
        """_extract_tag detects '了解' in title."""
        gen = SummaryGenerator()
        assert gen._extract_tag("补充材料 了解") == "了解"
        assert gen._extract_tag("了解内容") == "了解"

    def test_detects_yicuo_tag(self):
        """_extract_tag detects '易错' in title."""
        gen = SummaryGenerator()
        assert gen._extract_tag("常见错误 易错") == "易错"
        assert gen._extract_tag("易错题分析") == "易错"

    def test_returns_zhongdian_as_default(self):
        """_extract_tag returns '重点' when no recognized tag is present."""
        gen = SummaryGenerator()
        assert gen._extract_tag("计算机网络基础") == "重点"
        assert gen._extract_tag("") == "重点"
        assert gen._extract_tag("Some English Title") == "重点"

    def test_priority_when_multiple_tags_present(self):
        """_extract_tag returns first matching tag from the tag_map iteration order."""
        gen = SummaryGenerator()
        # "必考" appears before "重点" in tag_map, so a title with both
        # (which is unlikely but possible) returns first match
        result = gen._extract_tag("必考重点内容")
        # "必考" is checked first in the tag_map dict iteration
        assert result == "必考"


# ---------------------------------------------------------------------------
# _clean_title() tests
# ---------------------------------------------------------------------------

class TestCleanTitle:
    """Tests for SummaryGenerator._clean_title()."""

    def test_removes_emojis(self):
        """_clean_title removes emoji characters."""
        gen = SummaryGenerator()
        assert gen._clean_title("🔴重要标题") == "重要标题"
        assert gen._clean_title("🟡普通标题") == "普通标题"
        assert gen._clean_title("🟢了解标题") == "了解标题"
        assert gen._clean_title("🟠警示标题") == "警示标题"

    def test_removes_bracket_tag_markers(self):
        """_clean_title removes 【...】tag markers."""
        gen = SummaryGenerator()
        assert gen._clean_title("计算机网络【必考】") == "计算机网络"
        assert gen._clean_title("TCP协议【重点】") == "TCP协议"
        assert gen._clean_title("基础概念【了解】") == "基础概念"
        assert gen._clean_title("常见问题【易错】") == "常见问题"

    def test_removes_emoji_and_brackets_together(self):
        """_clean_title removes both emojis and bracket markers."""
        gen = SummaryGenerator()
        assert gen._clean_title("🔴OSI模型【必考】") == "OSI模型"
        assert gen._clean_title("🟡TCP/IP【重点】") == "TCP/IP"

    def test_preserves_normal_titles(self):
        """_clean_title preserves titles without special markers."""
        gen = SummaryGenerator()
        assert gen._clean_title("计算机网络基础") == "计算机网络基础"
        assert gen._clean_title("OSI七层参考模型") == "OSI七层参考模型"

    def test_strips_whitespace(self):
        """_clean_title strips leading/trailing whitespace."""
        gen = SummaryGenerator()
        assert gen._clean_title("  有空格标题  ") == "有空格标题"


# ---------------------------------------------------------------------------
# _clean_explanation() tests
# ---------------------------------------------------------------------------

class TestCleanExplanation:
    """Tests for SummaryGenerator._clean_explanation()."""

    def test_normalizes_excessive_whitespace(self):
        """_clean_explanation normalizes excessive blank lines (>=4 -> 2)."""
        gen = SummaryGenerator()
        lines = ["Line 1", "", "", "", "", "Line 2"]
        result = gen._clean_explanation(lines)
        # 5 blank lines between Line 1 and Line 2 -> reduced to 2
        assert "Line 1" in result
        assert "Line 2" in result
        assert "\n\n\n\n\n\n" not in result  # 4+ blank lines should be gone

    def test_handles_empty_list(self):
        """_clean_explanation handles empty list of lines."""
        gen = SummaryGenerator()
        result = gen._clean_explanation([])
        assert result == ""

    def test_handles_single_line(self):
        """_clean_explanation handles a single line."""
        gen = SummaryGenerator()
        result = gen._clean_explanation(["Just one line"])
        assert result == "Just one line"

    def test_preserves_normal_paragraph_spacing(self):
        """_clean_explanation preserves normal paragraph breaks (1-3 blank lines)."""
        gen = SummaryGenerator()
        lines = ["Para 1", "", "Para 2", "", "", "Para 3"]
        result = gen._clean_explanation(lines)
        assert "Para 1" in result
        assert "Para 2" in result
        assert "Para 3" in result

    def test_strips_trailing_content(self):
        """_clean_explanation result is stripped of leading/trailing whitespace."""
        gen = SummaryGenerator()
        lines = ["", "  Content  ", ""]
        result = gen._clean_explanation(lines)
        # Should not start with newline
        assert not result.startswith("\n")
        assert "Content" in result


# ---------------------------------------------------------------------------
# _compute_level_stats() tests
# ---------------------------------------------------------------------------

class TestComputeLevelStats:
    """Tests for SummaryGenerator._compute_level_stats()."""

    def test_produces_correct_count_per_level(self):
        """_compute_level_stats produces correct count per level."""
        gen = SummaryGenerator()
        nodes = [
            {"level": 1, "id": "n1"},
            {"level": 1, "id": "n2"},
            {"level": 2, "id": "n3"},
            {"level": 2, "id": "n4"},
            {"level": 2, "id": "n5"},
            {"level": 3, "id": "n6"},
        ]
        stats = gen._compute_level_stats(nodes)
        assert stats == {"L1": 2, "L2": 3, "L3": 1}

    def test_empty_nodes_returns_empty_dict(self):
        """_compute_level_stats returns empty dict for empty nodes."""
        gen = SummaryGenerator()
        stats = gen._compute_level_stats([])
        assert stats == {}

    def test_single_level_only(self):
        """_compute_level_stats works with single-level nodes."""
        gen = SummaryGenerator()
        nodes = [{"level": 1, "id": "n1"}, {"level": 1, "id": "n2"}]
        stats = gen._compute_level_stats(nodes)
        assert stats == {"L1": 2}


# ---------------------------------------------------------------------------
# Module singleton test
# ---------------------------------------------------------------------------

class TestModuleSingleton:
    """Test the module-level singleton."""

    def test_summary_generator_singleton_exists(self):
        """The module-level summary_generator is a SummaryGenerator instance."""
        assert isinstance(summary_generator, SummaryGenerator)
