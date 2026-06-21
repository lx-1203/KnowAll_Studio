"""Knowledge structure generation (M2)"""
import json
from app.core.api_scheduler import api_client, TaskType


class KnowledgeGenerator:
    """Generate knowledge trees, outlines from document chunks via API."""

    async def generate_tree(
        self,
        chunk_texts: list[str],
        model: str = "deepseek-chat",
    ) -> dict:
        """Generate a knowledge tree from document chunks."""
        from app.prompts import prompt_engine

        # For single chunk, generate directly
        if len(chunk_texts) == 1:
            messages = prompt_engine.render("knowledge_tree", "standard", chunk_text=chunk_texts[0])
            result = await api_client.generate(
                task_type=TaskType.KNOWLEDGE_TREE,
                messages=messages,
                prompt_template_id="knowledge_tree.standard",
                generation_content=chunk_texts[0],
            )
            return self._parse_tree_json(result.content)

        # For multiple chunks: generate per-chunk trees, then merge
        trees = []
        for i, chunk in enumerate(chunk_texts):
            messages = prompt_engine.render("knowledge_tree", "standard", chunk_text=chunk)
            result = await api_client.generate(
                task_type=TaskType.KNOWLEDGE_TREE,
                messages=messages,
                prompt_template_id="knowledge_tree.standard",
                generation_content=chunk,
            )
            tree = self._parse_tree_json(result.content)
            if tree:
                trees.append(tree)

        return self._merge_trees(trees)

    async def generate_outline(
        self,
        chunk_texts: list[str],
        model: str = "deepseek-chat",
    ) -> str:
        """Generate a markdown outline from document chunks."""
        from app.prompts import prompt_engine

        combined = "\n\n".join(chunk_texts[:5])  # limit input
        messages = prompt_engine.render("knowledge_tree", "simple", chunk_text=combined)
        result = await api_client.generate(
            task_type=TaskType.OUTLINE_GEN,
            messages=messages,
            prompt_template_id="knowledge_tree.simple",
            generation_content=combined,
        )
        return result.content

    def _parse_tree_json(self, content: str) -> dict | None:
        """Parse and validate knowledge tree JSON."""
        try:
            data = json.loads(content)
            return data.get("tree", data)
        except json.JSONDecodeError:
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
