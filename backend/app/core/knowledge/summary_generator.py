"""Knowledge summary generator - complete Markdown knowledge point summary"""
import re
import json
import logging
from app.core.api_scheduler import api_client, TaskType, GenerationConfig

logger = logging.getLogger(__name__)


class SummaryGenerator:
    """Generate comprehensive Markdown knowledge point summaries from documents."""

    async def generate(
        self,
        chunk_texts: list[str],
        document_id: str,
        model: str = "deepseek-chat",
        max_depth: int = 3,
        language_type: str = "auto",
        structure_context: str = "",
        image_descriptions: list[str] | None = None,
    ) -> dict:
        """Generate a complete knowledge point summary.

        Args:
            chunk_texts: Document text chunks
            document_id: Document ID for tracing
            model: LLM model
            max_depth: Max heading depth
            language_type: Language hint (auto/chinese/english/japanese)
            structure_context: Native document outline for better structure
            image_descriptions: Image analysis results to include

        Returns:
            dict with content_md, node_count, level_stats, nodes list
        """
        from app.prompts import prompt_engine

        # Build context text
        context = self._build_context(chunk_texts, structure_context, image_descriptions)

        # Add language hint
        lang_hint = ""
        if language_type == "english":
            lang_hint = "\n\n注意：这是一份英文学习材料，请适当保留英文术语，必要时添加中文注释。"
        elif language_type == "japanese":
            lang_hint = "\n\n注意：这是一份日语学习材料，请适当保留日文术语，必要时添加中文注释。"

        context += lang_hint

        messages = prompt_engine.render("summary", "full_summary", context=context)

        result = await api_client.generate(
            task_type=TaskType.KNOWLEDGE_TREE,
            messages=messages,
            prompt_template_id="summary.full_summary",
            generation_content=context,
            config=GenerationConfig(model=model, max_tokens=16000),
        )

        content_md = result.content

        # Validate: ensure LLM response contains at least one heading (#)
        # If not, the response is unstructured — wrap it so downstream mindmap works
        if not re.search(r'^#{1,3}\s+', content_md, re.MULTILINE):
            logger.warning(
                "LLM returned unstructured summary (no headings found). "
                "Wrapping in basic structure. First 200 chars: %s",
                content_md[:200]
            )
            content_md = f"# 知识点总结\n\n{content_md}"

        # Extract nodes from the generated Markdown
        nodes = self.extract_nodes_from_markdown(content_md, document_id)
        level_stats = self._compute_level_stats(nodes)
        node_count = len(nodes)

        return {
            "content_md": content_md,
            "node_count": node_count,
            "level_stats": level_stats,
            "nodes": nodes,
        }

    def _build_context(
        self,
        chunk_texts: list[str],
        structure_context: str = "",
        image_descriptions: list[str] | None = None,
    ) -> str:
        """Build full context from multiple sources."""
        parts = []

        if structure_context:
            parts.append("## 文档原生结构大纲\n")
            parts.append(structure_context)
            parts.append("\n---\n")

        parts.append("## 文档正文内容\n")
        # Limit total input to ~60K chars to avoid exceeding context window
        combined = "\n\n".join(chunk_texts)
        if len(combined) > 60000:
            parts.append(combined[:60000])
            parts.append("\n\n（注：文档内容较长，以上为前60,000字符的摘要）")
        else:
            parts.append(combined)

        if image_descriptions:
            parts.append("\n\n## 文档图片内容描述\n")
            for desc in image_descriptions:
                parts.append(f"- {desc}")

        return "\n".join(parts)

    def extract_nodes_from_markdown(self, content_md: str, document_id: str = "") -> list[dict]:
        """Parse Markdown headings to extract knowledge point nodes.

        Extracts H1 (#), H2 (##), H3 (###) headings and their body content,
        building a parent-child hierarchy with auto-generated IDs.

        Returns:
            List of node dicts with id, parent_id, level, sequence, title, explanation, etc.
        """
        nodes = []
        # Match headings and their content
        # Pattern: heading line followed by content until next heading of same or higher level
        heading_pattern = re.compile(r'^(#{1,3})\s+(.+?)(?:\s*[🔴🟡🟢🟠]【[^】]+】)?\s*$', re.MULTILINE)

        # Split by headings
        sections = re.split(r'^(#{1,3})\s+(.+)$', content_md, flags=re.MULTILINE)

        # Parse sections into structured nodes
        current_path = {1: None, 2: None, 3: None}  # level -> node_id
        level_counters = {1: 0, 2: 0, 3: 0}
        doc_short = document_id[:8] if document_id else "doc"

        # Process the content as heading-body pairs
        lines = content_md.split('\n')
        current_node = None
        pending_content = []

        for line in lines:
            match = heading_pattern.match(line)
            if match:
                # Save previous node's content
                if current_node is not None:
                    current_node["explanation"] = self._clean_explanation(pending_content)
                    nodes.append(current_node)
                    pending_content = []

                level = len(match.group(1))
                title = match.group(2).strip()

                if level > max(level_counters.keys()):
                    continue

                level_counters[level] += 1
                # Reset lower level counters
                for l in range(level + 1, 4):
                    level_counters[l] = 0

                # Generate ID
                seq_parts = []
                for l in range(1, level + 1):
                    seq_parts.append(f"{level_counters[l]:02d}")
                node_id = f"kp_{doc_short}_L{level}_{'_'.join(seq_parts)}"

                # Determine parent
                parent_id = current_path.get(level - 1) if level > 1 else None
                current_path[level] = node_id

                # Determine tag from title
                tag = self._extract_tag(title)
                clean_title = self._clean_title(title)

                current_node = {
                    "id": node_id,
                    "parent_id": parent_id,
                    "level": level,
                    "sequence": level_counters[level],
                    "title": clean_title,
                    "tag": tag,
                    "related_concepts": "",
                    "examples": "",
                    "explanation": "",
                }
            elif current_node is not None:
                pending_content.append(line)

        # Don't forget the last node
        if current_node is not None:
            current_node["explanation"] = self._clean_explanation(pending_content)
            nodes.append(current_node)

        # Post-process: extract related concepts and examples from explanation
        for node in nodes:
            expl = node["explanation"]
            # Extract related concepts
            related_match = re.search(r'(?:关联概念|相关内容|关联知识)[：:]\s*(.+?)(?:\n|$)', expl)
            if related_match:
                node["related_concepts"] = related_match.group(1).strip()
                expl = expl.replace(related_match.group(0), "")

            # Extract examples
            example_match = re.search(r'(?:示例|举例|例如)[：:]\s*(.+?)(?:\n\n|\Z)', expl, re.DOTALL)
            if example_match:
                node["examples"] = example_match.group(1).strip()
                expl = expl.replace(example_match.group(0), "")

            node["explanation"] = expl.strip()

        return nodes

    def _extract_tag(self, title: str) -> str:
        """Extract importance tag from title."""
        tag_map = {
            "必考": "必考",
            "重点": "重点",
            "了解": "了解",
            "易错": "易错",
        }
        for cn, tag in tag_map.items():
            if cn in title:
                return tag
        return "重点"

    def _clean_title(self, title: str) -> str:
        """Remove emoji and tag markers from title."""
        title = re.sub(r'[🔴🟡🟢🟠]', '', title)
        title = re.sub(r'【[^】]*】', '', title)
        return title.strip()

    def _clean_explanation(self, lines: list[str]) -> str:
        """Clean up extracted explanation text."""
        text = '\n'.join(lines).strip()
        # Remove excessive blank lines
        text = re.sub(r'\n{4,}', '\n\n', text)
        return text

    def _compute_level_stats(self, nodes: list[dict]) -> dict:
        """Compute node count per level."""
        stats = {}
        for node in nodes:
            level_key = f"L{node['level']}"
            stats[level_key] = stats.get(level_key, 0) + 1
        return stats


summary_generator = SummaryGenerator()
