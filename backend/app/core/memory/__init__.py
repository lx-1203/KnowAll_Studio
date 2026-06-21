"""Flashcard generation + FSRS spaced repetition scheduler (M4)"""
import json
import math
from datetime import datetime, timedelta, timezone
from app.core.api_scheduler import api_client, TaskType


class FlashcardGenerator:
    """Generate flashcard content via API."""

    async def generate(
        self,
        knowledge_text: str,
        card_type: str = "qa",
        count: int = 20,
        model: str = "deepseek-chat",
    ) -> list[dict]:
        """Generate flashcards from knowledge text."""
        from app.prompts import prompt_engine

        messages = prompt_engine.render(
            "flashcard", card_type,
            knowledge_points=knowledge_text,
            count=count,
        )

        result = await api_client.generate(
            task_type=TaskType.FLASHCARD_GEN,
            messages=messages,
            prompt_template_id=f"flashcard.{card_type}",
            generation_content=knowledge_text + card_type + str(count),
        )
        return self._parse_cards(result.content)

    def _parse_cards(self, content: str) -> list[dict]:
        try:
            data = json.loads(content)
            return data.get("cards", data if isinstance(data, list) else [])
        except json.JSONDecodeError:
            return []


class FSRS:
    """Free Spaced Repetition Scheduler - local algorithm, zero network.

    Based on the FSRS algorithm used in modern Anki.
    Reference: https://github.com/open-spaced-repetition/fsrs4anki
    """

    # Default FSRS parameters (optimized for typical learning)
    DEFAULT_W = [
        0.4, 0.6, 2.4, 5.8, 4.93, 0.94, 0.86, 0.01, 1.49,
        0.14, 0.94, 2.18, 0.05, 0.34, 1.26, 0.29, 2.61,
    ]

    # Rating mapping
    AGAIN = 1    # Forgot completely
    HARD = 2     # Recalled with difficulty
    GOOD = 3     # Recalled normally
    EASY = 4     # Recalled easily

    def __init__(self, w: list[float] | None = None):
        self.w = w or self.DEFAULT_W

    def init_card(self) -> dict:
        """Initialize FSRS state for a new card."""
        return {
            "stability": 0.0,
            "difficulty": 0.0,
            "retrievability": 0.0,
            "next_review_at": None,
            "last_review_at": None,
            "review_count": 0,
            "state": "new",
        }

    def review(self, card_state: dict, rating: int) -> dict:
        """Process a review and return updated card state + next interval.

        Args:
            card_state: Current FSRS card state
            rating: 1 (Again), 2 (Hard), 3 (Good), 4 (Easy)

        Returns updated card_state dict.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        state = dict(card_state)  # copy

        if state["state"] == "new":
            return self._first_review(state, rating, now)

        # Calculate retrievability
        if state["last_review_at"] and state["stability"] > 0:
            elapsed = (now - state["last_review_at"]).total_seconds() / 86400.0
            state["retrievability"] = math.exp(
                math.log(0.9) * elapsed / max(state["stability"], 0.001)
            )

        # Update difficulty based on rating
        difficulty_delta = self._difficulty_delta(rating)
        state["difficulty"] = max(0.0, min(1.0, state["difficulty"] + difficulty_delta * 0.1))

        # Update stability
        if rating == self.AGAIN:
            state["stability"] = state["stability"] * 0.5
            state["state"] = "relearning"
        else:
            stability_increase = self._stability_increase(state["difficulty"], rating)
            if state["stability"] == 0:
                state["stability"] = 1.0
            state["stability"] = state["stability"] * stability_increase
            state["state"] = "review"

        # Calculate next review time
        if rating == self.AGAIN:
            interval_minutes = 10
        elif rating == self.HARD:
            interval_days = max(1, state["stability"] * 0.8)
            interval_minutes = interval_days * 1440
        elif rating == self.GOOD:
            interval_minutes = max(1, state["stability"]) * 1440
        else:  # EASY
            interval_minutes = max(1, state["stability"] * 1.3) * 1440

        state["next_review_at"] = now + timedelta(minutes=interval_minutes)
        state["last_review_at"] = now
        state["review_count"] += 1

        return state

    def _first_review(self, state: dict, rating: int, now: datetime) -> dict:
        """Handle the first review of a new card."""
        state["difficulty"] = 0.3

        if rating == self.AGAIN:
            state["stability"] = 0.1
            state["next_review_at"] = now + timedelta(minutes=1)
            state["state"] = "learning"
        elif rating == self.HARD:
            state["stability"] = 0.5
            state["next_review_at"] = now + timedelta(minutes=10)
            state["state"] = "learning"
        elif rating == self.GOOD:
            state["stability"] = 1.0
            state["next_review_at"] = now + timedelta(days=1)
            state["state"] = "review"
        else:  # EASY
            state["stability"] = 3.0
            state["next_review_at"] = now + timedelta(days=4)
            state["state"] = "review"

        state["last_review_at"] = now
        state["review_count"] = 1
        return state

    def _difficulty_delta(self, rating: int) -> float:
        """How much to adjust difficulty based on rating."""
        return {
            self.AGAIN: 0.15,   # Make harder
            self.HARD: 0.05,    # Slightly harder
            self.GOOD: -0.05,   # Slightly easier
            self.EASY: -0.15,   # Make easier
        }[rating]

    def _stability_increase(self, difficulty: float, rating: int) -> float:
        """Calculate stability multiplier."""
        base = {
            self.HARD: 1.2,
            self.GOOD: 2.0,
            self.EASY: 3.0,
        }[rating]
        return base * (1.0 - difficulty * 0.5)

    def get_due_cards(self, cards: list[dict]) -> list[dict]:
        """Filter cards that are due for review."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        due = []
        for card in cards:
            schedule = card.get("schedule", {})
            if schedule.get("state") == "new":
                due.append(card)
            elif schedule.get("next_review_at"):
                if schedule["next_review_at"] <= now:
                    due.append(card)
        return due


card_generator = FlashcardGenerator()
fsrs = FSRS()
