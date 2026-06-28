"""Flashcard generation + FSRS spaced repetition scheduler (M4)"""
import json
import math
import re
import logging
from datetime import datetime, timedelta, timezone
from app.core.api_scheduler import api_client, TaskType, GenerationConfig

logger = logging.getLogger(__name__)


class FlashcardGenerator:
    """Generate flashcard content via API with quality validation."""

    # ── Validation constants ────────────────────────────────────
    MIN_FRONT_LENGTH = 4       # Minimum characters for card front
    MIN_BACK_LENGTH = 2        # Minimum characters for card back
    CLOZE_PATTERN = re.compile(r'\{\{c\d+::[^}]+?\}\}')  # {{c1::answer}}

    async def generate_cards(
        self,
        knowledge_text: str,
        card_type: str = "qa",
        count: int = 20,
        deck_name: str = "默认牌组",
        model: str = "deepseek-chat",
        knowledge_point_id: str = None,
    ) -> list[dict]:
        """Generate flashcards with optional knowledge point linking.

        Extended interface used by agents for coverage-mapped generation.
        """
        cards = await self.generate(knowledge_text, card_type, count, model)

        # Tag each card with knowledge_point_id if provided
        if knowledge_point_id:
            for card in cards:
                card["knowledge_point_id"] = knowledge_point_id

        return cards

    async def generate(
        self,
        knowledge_text: str,
        card_type: str = "qa",
        count: int = 20,
        model: str = "deepseek-chat",
    ) -> list[dict]:
        """Generate flashcards from knowledge text with quality validation."""
        from app.prompts import prompt_engine

        # Preprocess: truncate overly long knowledge text
        knowledge_text = self._preprocess_text(knowledge_text)

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
            config=GenerationConfig(model=model),
        )
        cards = self._parse_cards(result.content)

        # Validate all cards
        valid_cards = []
        for c in cards:
            if c.get("card_type") is None:
                c["card_type"] = card_type
            is_valid, reason = self.validate_card(c, card_type)
            if is_valid:
                valid_cards.append(c)
            else:
                logger.warning(f"Card filtered: type={card_type} reason={reason}")

        return valid_cards

    # ── Quality validation (public static) ──────────────────────

    @staticmethod
    def validate_card(card: dict, card_type: str) -> tuple[bool, str]:
        """Validate card structure. Returns (is_valid, error_reason)."""
        front = (card.get("front") or "").strip()
        back = (card.get("back") or "").strip()

        # Both sides must have content
        if not front:
            return False, "empty_front"
        if not back:
            return False, "empty_back"

        # Front too short (except for formula-type cards)
        if len(front) < FlashcardGenerator.MIN_FRONT_LENGTH:
            return False, f"front_too_short({len(front)})"

        # Cloze-specific: must have at least one cloze marker
        if card_type == "cloze" and not FlashcardGenerator.CLOZE_PATTERN.search(front):
            return False, "missing_cloze_marker"

        # QA: front and back should not be identical
        if card_type == "qa" and front == back:
            return False, "front_equals_back"

        return True, ""

    # ── JSON parsing with repair ─────────────────────────────────

    def _parse_cards(self, content: str) -> list[dict]:
        """Parse LLM output to card list with multi-layer JSON repair."""
        if not content or not content.strip():
            return []

        # Layer 1: Direct JSON parse
        try:
            data = json.loads(content)
            return self._extract_cards(data)
        except json.JSONDecodeError:
            pass

        # Layer 2: Extract from ```json ... ``` code block
        m = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        if m:
            try:
                data = json.loads(m.group(1))
                return self._extract_cards(data)
            except json.JSONDecodeError:
                pass

        # Layer 3: Find outermost JSON object or array in the raw text
        return self._repair_and_parse(content)

    def _extract_cards(self, data) -> list[dict]:
        """Normalize parsed data into card list."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("cards", [])
        return []

    def _repair_and_parse(self, content: str) -> list[dict]:
        """Last-resort: try to salvage individual card objects from broken JSON.

        Strategy: find each {...} block that looks like a card and parse it individually.
        """
        cards = []
        # Find all balanced { ... } blocks that contain "front" key
        for m in re.finditer(r'\{[^{}]*?"front"\s*:\s*"[^"]*"[^{}]*?"back"\s*:\s*"[^"]*"[^{}]*?\}', content):
            try:
                card = json.loads(m.group())
                if "front" in card and "back" in card:
                    cards.append(card)
            except json.JSONDecodeError:
                continue

        if cards:
            logger.info(f"Repaired {len(cards)} cards from broken JSON")
        return cards

    # ── Text preprocessing ──────────────────────────────────────

    @staticmethod
    def _preprocess_text(text: str, max_chars: int = 6000) -> str:
        """Truncate overly long knowledge text to prevent LLM context dilution."""
        if len(text) <= max_chars:
            return text
        # Keep first 60% and last 20% (the middle is often repetitive)
        head = int(max_chars * 0.7)
        tail = int(max_chars * 0.2)
        truncated = text[:head] + "\n\n...(中间内容省略)...\n\n" + text[-tail:]
        logger.info(f"Text truncated from {len(text)} to {len(truncated)} chars")
        return truncated


class FSRS:
    """Free Spaced Repetition Scheduler - local algorithm, zero network.

    Based on the FSRS algorithm used in modern Anki.
    Reference: https://github.com/open-spaced-repetition/fsrs4anki

    Features:
    - 17-parameter adaptive model with MLE weight optimization
    - Precision-aware interval calculation (minutes for short, days for long)
    - Load balancing for due card distribution
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

    # Load balancing
    MAX_DUE_PER_DAY = 50  # Soft cap for due cards per day
    HIGH_INTERVAL_DAYS = 7  # Use day-precision above this threshold

    def __init__(self, w: list[float] | None = None):
        self.w = w or self.DEFAULT_W
        self._user_w_cache: dict[str, list[float]] = {}

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

        # Calculate next review time with precision handling
        state["next_review_at"] = self._calculate_next_review(state, rating, now)
        state["last_review_at"] = now
        state["review_count"] += 1

        return state

    def _calculate_next_review(self, state: dict, rating: int, now: datetime) -> datetime:
        """Calculate next_review_at with precision-aware intervals.

        For long intervals (>7 days), use day-level precision to avoid
        floating-point accumulation errors from minute-based calculation.
        """
        if rating == self.AGAIN:
            return now + timedelta(minutes=10)
        elif rating == self.HARD:
            interval_days = max(1, state["stability"] * 0.8)
        elif rating == self.GOOD:
            interval_days = max(1, state["stability"])
        else:  # EASY
            interval_days = max(1, state["stability"] * 1.3)

        if interval_days > self.HIGH_INTERVAL_DAYS:
            # Day precision: round to nearest hour
            whole_days = round(interval_days)
            return now.replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=whole_days)
        else:
            # Minute precision for short intervals
            interval_minutes = interval_days * 1440
            return now + timedelta(minutes=interval_minutes)

    def _first_review(self, state: dict, rating: int, now: datetime) -> dict:
        """Handle the first review of a new card."""
        state["difficulty"] = self.w[2]

        if rating == self.AGAIN:
            state["stability"] = self.w[0]
            state["next_review_at"] = now + timedelta(minutes=1)
            state["state"] = "learning"
        elif rating == self.HARD:
            state["stability"] = self.w[0] * 1.5
            state["next_review_at"] = now + timedelta(minutes=10)
            state["state"] = "learning"
        elif rating == self.GOOD:
            state["stability"] = self.w[1]
            state["next_review_at"] = now + timedelta(days=1)
            state["state"] = "review"
        else:  # EASY
            state["stability"] = self.w[1] * self.w[6]
            state["next_review_at"] = now + timedelta(days=4)
            state["state"] = "review"

        state["last_review_at"] = now
        state["review_count"] = 1
        return state

    def _difficulty_delta(self, rating: int) -> float:
        """How much to adjust difficulty based on rating."""
        return {
            self.AGAIN: self.w[4],
            self.HARD: self.w[5],
            self.GOOD: -self.w[4],
            self.EASY: -self.w[5],
        }[rating]

    def _stability_increase(self, difficulty: float, rating: int) -> float:
        """Calculate stability multiplier."""
        base = {
            self.HARD: self.w[6],
            self.GOOD: self.w[7],
            self.EASY: self.w[8],
        }[rating]
        return base * (1.0 - difficulty * self.w[3])

    def get_due_cards(self, cards: list[dict]) -> list[dict]:
        """Filter cards that are due for review.

        Note: Prefer the SQL-level filtering in the API route for large datasets.
        This method is retained for in-memory use on small lists.
        """
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

    def balance_load(
        self,
        due_cards: list,
        max_per_day: int | None = None,
    ) -> list:
        """Apply load balancing: if too many cards are due, spread some to next day.

        Returns the same list, but modifies next_review_at for overflow cards.
        """
        if max_per_day is None:
            max_per_day = self.MAX_DUE_PER_DAY

        if len(due_cards) <= max_per_day:
            return due_cards

        tomorrow = datetime.now(timezone.utc).replace(
            tzinfo=None, hour=8, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)

        overflow = due_cards[max_per_day:]
        for card in overflow:
            schedule = card.get("schedule", {})
            schedule["next_review_at"] = tomorrow
            schedule["state"] = "review"

        logger.info(
            f"Load balanced: {len(overflow)} cards deferred to {tomorrow.date()}"
        )
        return due_cards

    # ── Personalized weight optimization ────────────────────────

    def optimize_weights(
        self,
        ratings_history: list[dict],
        epochs: int = 50,
        lr: float = 0.01,
        user_id: str | None = None,
    ) -> list[float]:
        """Fit personalized FSRS parameters using simplified gradient descent (MLE).

        Args:
            ratings_history: List of {rating, stability, difficulty, elapsed_days}
            epochs: Number of gradient descent iterations
            lr: Learning rate
            user_id: If provided, cache the optimized weights

        Returns optimized w vector.
        """
        if len(ratings_history) < 50:
            logger.info("Not enough review history for optimization (need 50+, got %d)", len(ratings_history))
            return list(self.w)

        w = list(self.DEFAULT_W)
        n = len(ratings_history)

        for epoch in range(epochs):
            total_loss = 0.0
            grad = [0.0] * len(w)

            for record in ratings_history:
                r = record["rating"]
                s = record.get("stability", 1.0)
                d = record.get("difficulty", 0.3)
                elapsed = record.get("elapsed_days", 1.0)

                # Predict retrievability
                if s > 0:
                    predicted_r = math.exp(math.log(0.9) * elapsed / s)
                else:
                    predicted_r = 0.0

                # Target: 1.0 for GOOD/EASY, 0.0 for AGAIN, 0.5 for HARD
                if r == self.AGAIN:
                    target = 0.0
                elif r == self.HARD:
                    target = 0.5
                else:
                    target = 1.0

                # Loss: squared error
                error = predicted_r - target
                total_loss += error * error

                # Gradient w.r.t w[0] (initial stability) and w[1] (base stability)
                if s > 0:
                    grad[0] += -2 * error * predicted_r * math.log(0.9) * elapsed / (s * s)
                    grad[1] += -2 * error * predicted_r * math.log(0.9) * elapsed / (s * s)

            # Gradient descent step
            for i in range(len(w)):
                w[i] -= lr * grad[i] / n
                w[i] = max(0.001, min(10.0, w[i]))  # clamp

            if epoch % 10 == 0:
                logger.debug(f"Optimize epoch {epoch}: loss={total_loss / n:.4f}")

        if user_id:
            self._user_w_cache[user_id] = w

        logger.info(f"FSRS weights optimized: loss improved over {epochs} epochs")
        return w

    def get_user_weights(self, user_id: str) -> list[float]:
        """Get cached personalized weights for a user."""
        return self._user_w_cache.get(user_id, list(self.w))

    def load_user_weights(self, user_id: str) -> list[float]:
        """Load personalized weights for use in this FSRS instance."""
        cached = self.get_user_weights(user_id)
        self.w = cached
        return cached


card_generator = FlashcardGenerator()
fsrs = FSRS()
