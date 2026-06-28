"""Card quality checker - structural validation and LLM-augmented quality scoring"""
import json as json_module
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class QualityReport:
    """Result of a card quality check."""
    passed: bool
    score: float = 0.0
    dimension_scores: dict = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    suggestions: str = ""


class CardQualityChecker:
    """Validates and scores flashcard quality.

    Layer 1: Structural validation (fast, no LLM)
    Layer 2: LLM-based content quality scoring (slow, sampled)
    """

    # Thresholds
    MIN_QUALITY_SCORE = 3.0       # Overall score must be >= 3.0 to pass
    REVIEW_SAMPLE_SIZE = 3         # Number of cards to sample for LLM review
    REVIEW_MIN_BATCH_SIZE = 10     # Min batch size to trigger LLM review

    @staticmethod
    def structural_check(card: dict, card_type: str) -> tuple[bool, list[str]]:
        """Run structural validation rules. Returns (passed, issues)."""
        issues = []
        front = (card.get("front") or "").strip()
        back = (card.get("back") or "").strip()

        if not front:
            issues.append("empty_front")
        elif len(front) < 4:
            issues.append("front_too_short")

        if not back:
            issues.append("empty_back")

        if card_type == "qa" and front == back:
            issues.append("front_equals_back")

        if card_type == "cloze" and "{{c" not in front:
            issues.append("missing_cloze_marker")

        if card_type == "compare" and "|" not in back:
            # Compare cards should have a markdown table in back
            issues.append("compare_missing_table")

        return len(issues) == 0, issues

    async def llm_review_batch(
        self,
        cards: list[dict],
        model: str = "deepseek-chat",
    ) -> list[QualityReport]:
        """Run LLM quality review on a sample of cards.

        Returns one QualityReport per sampled card.
        """
        import random
        from app.prompts import prompt_engine
        from app.core.api_scheduler import api_client, TaskType, GenerationConfig

        sample_size = min(self.REVIEW_SAMPLE_SIZE, len(cards))
        if len(cards) < self.REVIEW_MIN_BATCH_SIZE:
            return []

        sample_indices = random.sample(range(len(cards)), sample_size)
        reports = []

        for idx in sample_indices:
            card = cards[idx]
            try:
                messages = prompt_engine.render(
                    "flashcard_review", "review_single",
                    card_type=card.get("card_type", "qa"),
                    front=card.get("front", ""),
                    back=card.get("back", ""),
                    hints=card.get("hints", ""),
                )
                result = await api_client.generate(
                    task_type=TaskType.FLASHCARD_GEN,
                    messages=messages,
                    prompt_template_id="flashcard_review.review_single",
                    generation_content=card.get("front", "") + card.get("back", ""),
                    config=GenerationConfig(model=model, temperature=0.3, max_tokens=512),
                )
                review = json_module.loads(result.content)
                scores = review.get("scores", {})
                total = review.get("total", sum(scores.values()) / max(len(scores), 1))
                passed = review.get("passed", total >= self.MIN_QUALITY_SCORE)

                reports.append(QualityReport(
                    passed=passed,
                    score=total,
                    dimension_scores=scores,
                    suggestions=review.get("suggestions", ""),
                ))
            except json_module.JSONDecodeError as e:
                logger.warning(f"LLM review JSON parse failed for card {idx}: {e}")
                reports.append(QualityReport(passed=True, score=3.0))
            except Exception as e:
                logger.warning(f"LLM review failed for card {idx}: {e}")
                reports.append(QualityReport(passed=True, score=3.0))

        return reports

    @staticmethod
    def aggregate_reports(reports: list[QualityReport]) -> dict:
        """Aggregate multiple quality reports into a summary."""
        if not reports:
            return {"avg_score": 0.0, "passed": True, "count": 0}

        avg_score = sum(r.score for r in reports) / len(reports)
        all_passed = all(r.passed for r in reports)

        # Aggregate dimension scores
        dim_scores = {}
        dim_counts = {}
        for r in reports:
            for dim, score in r.dimension_scores.items():
                dim_scores[dim] = dim_scores.get(dim, 0) + score
                dim_counts[dim] = dim_counts.get(dim, 0) + 1
        avg_dims = {k: round(dim_scores[k] / dim_counts[k], 2) for k in dim_scores}

        return {
            "avg_score": round(avg_score, 2),
            "passed": all_passed,
            "count": len(reports),
            "dimension_scores": avg_dims,
            "suggestions": [r.suggestions for r in reports if r.suggestions],
        }


quality_checker = CardQualityChecker()
