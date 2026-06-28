"""Native outline extractor - converts Docling headings to structured outlines"""
from dataclasses import dataclass, field


@dataclass
class OutlineResult:
    """Extracted outline result"""
    markdown: str
    tree_json: dict
    flat_headings: list[dict]


class OutlineExtractor:
    """Extract native outline from StructuredDocument headings."""

    MAX_DEPTH = 4
    TAG_DEFAULT = "了解"

    def extract(self, headings: list) -> OutlineResult:
        """Convert heading nodes to multiple output formats."""
        flat = self._flatten(headings)
        markdown = self.to_markdown(headings)
        tree_json = self.to_tree_json(headings)
        return OutlineResult(markdown=markdown, tree_json=tree_json, flat_headings=flat)

    def to_markdown(self, headings: list, depth: int = 0) -> str:
        """Recursively generate hierarchical Markdown outline."""
        if depth >= self.MAX_DEPTH:
            return ""
        lines = []
        for h in headings:
            level = min(h.level, 6) if hasattr(h, "level") else min(depth + 1, 6)
            prefix = "#" * level
            lines.append(f"{prefix} {h.label}")
            if hasattr(h, "children") and h.children:
                child_md = self.to_markdown(h.children, depth + 1)
                if child_md:
                    lines.append(child_md)
        return "\n".join(lines)

    def to_tree_json(self, headings: list) -> dict:
        """Convert to JSON format compatible with existing KnowledgeTree.tree_data."""
        nodes = self._convert_nodes(headings, start_id=0)
        title = headings[0].label if headings else ""
        return {"title": title, "nodes": nodes}

    def _convert_nodes(self, headings: list, start_id: int = 0, depth: int = 0) -> list[dict]:
        """Recursively convert heading nodes to API-compatible tree dict."""
        if depth >= self.MAX_DEPTH:
            return []
        nodes = []
        for i, h in enumerate(headings):
            node_id = f"native_{start_id + i}"
            children = self._convert_nodes(
                h.children if hasattr(h, "children") else [],
                start_id=start_id + i * 100,
                depth=depth + 1,
            )
            nodes.append({
                "id": node_id,
                "label": h.label,
                "level": getattr(h, "level", depth + 1),
                "tag": self.TAG_DEFAULT,
                "summary": "",
                "page": getattr(h, "page", 0),
                "children": children,
            })
        return nodes

    def inject_context(self, headings: list, depth: int = 0) -> str:
        """Generate structural context string for LLM prompt injection.

        Produces a scannable document structure overview like:
        - 第一章 绪论 (p1-p15)
          - 1.1 研究背景 (p1-p5)
          - 1.2 研究意义 (p6-p12)
        """
        if depth >= self.MAX_DEPTH or not headings:
            return ""
        lines = []
        indent = "  " * depth
        for h in headings:
            page = getattr(h, "page", 0) or 0
            page_str = f"(p{page})" if page else ""
            lines.append(f"{indent}- {h.label} {page_str}".strip())
            children = getattr(h, "children", [])
            if children:
                child_str = self.inject_context(children, depth + 1)
                if child_str:
                    lines.append(child_str)
        return "\n".join(lines)

    def _flatten(self, headings: list, depth: int = 0) -> list[dict]:
        """Flatten heading tree to a list with depth info."""
        result = []
        for h in headings:
            result.append({
                "id": getattr(h, "id", ""),
                "label": h.label,
                "level": getattr(h, "level", depth + 1),
                "page": getattr(h, "page", 0),
            })
            children = getattr(h, "children", [])
            if children:
                result.extend(self._flatten(children, depth + 1))
        return result


outline_extractor = OutlineExtractor()
