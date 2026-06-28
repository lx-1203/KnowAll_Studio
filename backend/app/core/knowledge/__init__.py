"""Knowledge structure generation (M2)"""
import json
import logging
from app.core.api_scheduler import api_client, TaskType, GenerationConfig

logger = logging.getLogger(__name__)


class KnowledgeGenerator:
    """Generate knowledge trees, outlines from document chunks via API."""

    async def generate_summary(
        self,
        chunk_texts: list[str],
        document_id: str,
        model: str = "deepseek-chat",
        max_depth: int = 3,
        language_type: str = "auto",
        structure_context: str = "",
        image_descriptions: list[str] | None = None,
    ) -> dict:
        """Generate a complete Markdown knowledge point summary.

        Delegates to SummaryGenerator for the full structured output.
        """
        from app.core.knowledge.summary_generator import summary_generator
        return await summary_generator.generate(
            chunk_texts=chunk_texts,
            document_id=document_id,
            model=model,
            max_depth=max_depth,
            language_type=language_type,
            structure_context=structure_context,
            image_descriptions=image_descriptions,
        )

    async def generate_tree(
        self,
        chunk_texts: list[str],
        model: str = "deepseek-chat",
        structure_context: str = "",
        image_descriptions: list[str] | None = None,
    ) -> dict:
        """Generate a knowledge tree from document chunks.

        Args:
            chunk_texts: Document text chunks
            model: LLM model to use
            structure_context: Optional native outline structure for prompt injection
            image_descriptions: Optional image analysis descriptions to append
        """
        from app.prompts import prompt_engine

        # Build augmented text: chunks + image descriptions
        augmented_text = self._build_augmented_text(chunk_texts, image_descriptions)

        # Choose prompt template based on available context
        if structure_context:
            template = "structure_aware"
            render_kwargs = {
                "document_structure": structure_context,
                "chunk_text": augmented_text,
            }
        else:
            template = "standard"
            render_kwargs = {"chunk_text": augmented_text}

        if len(chunk_texts) == 1:
            messages = prompt_engine.render("knowledge_tree", template, **render_kwargs)
            result = await api_client.generate(
                task_type=TaskType.KNOWLEDGE_TREE,
                messages=messages,
                prompt_template_id=f"knowledge_tree.{template}",
                generation_content=augmented_text,
                config=GenerationConfig(model=model),
            )
            return self._parse_tree_json(result.content)

        # For multiple chunks: generate per-chunk trees, then merge
        trees = []
        for i, chunk in enumerate(chunk_texts):
            chunk_render = {**render_kwargs, "chunk_text": chunk}
            messages = prompt_engine.render("knowledge_tree", template, **chunk_render)
            result = await api_client.generate(
                task_type=TaskType.KNOWLEDGE_TREE,
                messages=messages,
                prompt_template_id=f"knowledge_tree.{template}",
                generation_content=chunk,
                config=GenerationConfig(model=model),
            )
            tree = self._parse_tree_json(result.content)
            if tree:
                trees.append(tree)

        return self._merge_trees(trees)

    async def generate_outline(
        self,
        chunk_texts: list[str],
        model: str = "deepseek-chat",
        structure_context: str = "",
    ) -> str:
        """Generate a markdown outline from document chunks.

        If structure_context is provided, the LLM polishes/enriches
        the native outline instead of generating from scratch.
        """
        from app.prompts import prompt_engine

        combined = "\n\n".join(chunk_texts[:5])
        if structure_context:
            # Use the native structure as the primary input, LLM polishes it
            enriched_prompt = (
                f"以下是文档的原生结构大纲：\n\n{structure_context}\n\n"
                f"以下是部分章节内容：\n\n{combined[:6000]}\n\n"
                f"请完善以上大纲：为每个章节添加2-5个知识点要点，并用缩进表示。"
                f"保留原章节结构，只添加内容。输出Markdown格式。"
            )
            messages = [
                {"role": "system", "content": "你是一位知识整理专家。请完善文档大纲。"},
                {"role": "user", "content": enriched_prompt},
            ]
        else:
            messages = prompt_engine.render("knowledge_tree", "simple", chunk_text=combined)

        result = await api_client.generate(
            task_type=TaskType.OUTLINE_GEN,
            messages=messages,
            prompt_template_id="knowledge_tree.simple",
            generation_content=combined,
            config=GenerationConfig(model=model),
        )
        return result.content

    def _build_augmented_text(
        self,
        chunk_texts: list[str],
        image_descriptions: list[str] | None,
    ) -> str:
        """Combine chunk texts with image descriptions."""
        if not image_descriptions:
            if len(chunk_texts) == 1:
                return chunk_texts[0]
            return "\n\n".join(chunk_texts)

        parts = list(chunk_texts)
        parts.append("\n\n【文档图片内容描述】\n")
        for desc in image_descriptions:
            parts.append(f"- {desc}")
        return "\n".join(parts)

    def _parse_tree_json(self, content: str) -> dict | None:
        """Parse and validate knowledge tree JSON."""
        try:
            data = json.loads(content)
            return data.get("tree", data)
        except json.JSONDecodeError:
            logger.warning("Failed to parse knowledge tree JSON")
            return None

    def _merge_trees(self, trees: list[dict]) -> dict:
        """Merge multiple knowledge trees into one."""
        if not trees:
            return {"title": "", "nodes": []}
        if len(trees) == 1:
            return trees[0]

        merged = {"title": "综合知识体系", "nodes": []}
        for i, tree in enumerate(trees):
            nodes = tree.get("nodes", [])
            for node in nodes:
                node["id"] = f"c{i}_{node['id']}"
            merged["nodes"].extend(nodes)
        return merged


knowledge_generator = KnowledgeGenerator()
