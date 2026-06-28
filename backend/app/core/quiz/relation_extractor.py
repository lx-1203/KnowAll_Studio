"""Knowledge relation extraction and cross-topic question generation.

Extracts semantic edges (prerequisite, confused_with, etc.) between knowledge points
and uses them to generate higher-quality, relation-aware quiz questions.
"""
import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

RELATION_TYPES = [
    "prerequisite",    # 前置依赖
    "extends",         # 扩展延伸
    "confused_with",   # 易混淆
    "analogous_to",    # 类同
    "contradicts",     # 对立
    "applies_to",      # 应用关系
]

RELATION_LABELS: dict[str, str] = {
    "prerequisite": "前置依赖",
    "extends": "扩展延伸",
    "confused_with": "易混淆",
    "analogous_to": "类同",
    "contradicts": "对立矛盾",
    "applies_to": "应用关系",
}


@dataclass
class KnowledgeRelation:
    """A typed edge between two knowledge points."""
    source_id: str
    source_title: str
    target_id: str
    target_title: str
    relation_type: str       # one of RELATION_TYPES
    description: str = ""


@dataclass
class ConfusionPair:
    """Two easily-confused concepts with their key difference."""
    concept_a: str
    concept_b: str
    difference_key: str       # the most important distinguishing factor
    typical_mistake: str = "" # common student error


class KnowledgeRelationExtractor:
    """Extract semantic relations from knowledge point nodes via LLM."""

    async def extract(
        self,
        nodes: list[dict],
        model: str = "deepseek-chat",
    ) -> tuple[list[KnowledgeRelation], list[ConfusionPair]]:
        """Extract relations and confusion pairs from knowledge point nodes.

        Args:
            nodes: List of dicts with at least id, title, explanation fields.
            model: LLM model to use.

        Returns:
            Tuple of (relations, confusion_pairs).
        """
        from app.prompts import prompt_engine
        from app.core.api_scheduler import api_client, TaskType, GenerationConfig

        # Build a compact JSON representation of nodes
        node_summaries = []
        for n in nodes:
            node_summaries.append({
                "id": n.get("id", ""),
                "title": n.get("title", ""),
                "explanation": (n.get("explanation", "") or "")[:200],
                "level": n.get("level", 0),
            })

        nodes_json = json.dumps(node_summaries, ensure_ascii=False, indent=2)

        try:
            messages = prompt_engine.render(
                "knowledge_relation", "extract_relations",
                knowledge_points_json=nodes_json,
            )

            result = await api_client.generate(
                task_type=TaskType.QUIZ_GEN,
                messages=messages,
                prompt_template_id="knowledge_relation.extract_relations",
                generation_content=nodes_json[:500],
                config=GenerationConfig(model=model),
            )

            data = json.loads(result.content)

            relations = []
            for e in data.get("edges", []):
                relations.append(KnowledgeRelation(
                    source_id=e.get("source_id", ""),
                    source_title=e.get("source", ""),
                    target_id=e.get("target_id", ""),
                    target_title=e.get("target", ""),
                    relation_type=e.get("relation_type", "related_to"),
                    description=e.get("description", ""),
                ))

            confusion_pairs = []
            for cp in data.get("confusion_pairs", []):
                confusion_pairs.append(ConfusionPair(
                    concept_a=cp.get("concept_a", ""),
                    concept_b=cp.get("concept_b", ""),
                    difference_key=cp.get("difference_key", ""),
                    typical_mistake=cp.get("typical_mistake", ""),
                ))

            logger.info(
                f"Extracted {len(relations)} relations and "
                f"{len(confusion_pairs)} confusion pairs from {len(nodes)} nodes"
            )
            return relations, confusion_pairs

        except Exception as e:
            logger.error(f"Relation extraction failed: {e}", exc_info=True)
            return [], []

    def build_confusion_map(
        self,
        confusion_pairs: list[ConfusionPair],
    ) -> dict[str, list[ConfusionPair]]:
        """Index confusion pairs by concept name for O(1) lookup during question generation."""
        cmap: dict[str, list[ConfusionPair]] = {}
        for cp in confusion_pairs:
            for concept in (cp.concept_a, cp.concept_b):
                if concept not in cmap:
                    cmap[concept] = []
                cmap[concept].append(cp)
        return cmap

    def get_distractor_hints(
        self,
        node_title: str,
        confusion_map: dict[str, list[ConfusionPair]],
    ) -> str:
        """Generate distractor hints for a knowledge point based on confusion pairs.

        Returns a string that can be injected into the quiz generation prompt to
        help the LLM create better distractors.
        """
        pairs = confusion_map.get(node_title, [])
        if not pairs:
            # Try partial match
            for key, val in confusion_map.items():
                if node_title in key or key in node_title:
                    pairs = val
                    break

        if not pairs:
            return ""

        hints = ["\n【易混淆概念提示——用于生成干扰项】"]
        for cp in pairs[:3]:  # max 3 pairs
            other = cp.concept_b if cp.concept_a == node_title else cp.concept_a
            hints.append(
                f"- 学生常将「{node_title}」与「{other}」混淆。"
                f"关键区分：{cp.difference_key}。"
                f"典型错误：{cp.typical_mistake}"
            )
        return "\n".join(hints)

    def get_cross_topic_pairs(
        self,
        relations: list[KnowledgeRelation],
    ) -> list[dict]:
        """Find prerequisite chains and confusion pairs suitable for cross-topic questions."""
        cross_pairs = []

        # Prerequisite chains: test understanding of WHY A is needed for B
        prereqs = [r for r in relations if r.relation_type == "prerequisite"]
        for r in prereqs[:5]:
            cross_pairs.append({
                "type": "prerequisite_chain",
                "source": r.source_title,
                "target": r.target_title,
                "description": r.description,
                "prompt_hint": (
                    f"知识点「{r.source_title}」是「{r.target_title}」的前置基础。"
                    f"请生成一道题，考察学生是否理解为什么必须先掌握前者才能学好后者。"
                ),
            })

        # Confusion pairs: directly test the distinction
        confused = [r for r in relations if r.relation_type == "confused_with"]
        for r in confused[:5]:
            cross_pairs.append({
                "type": "confusion_differentiation",
                "source": r.source_title,
                "target": r.target_title,
                "description": r.description,
                "prompt_hint": (
                    f"「{r.source_title}」和「{r.target_title}」是易混淆概念。"
                    f"请生成一道辨析题，选项设计基于典型混淆点。"
                ),
            })

        return cross_pairs


# Singleton
relation_extractor = KnowledgeRelationExtractor()
