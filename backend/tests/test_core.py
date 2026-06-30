"""Core unit tests for KnowAll Studio backend."""
import pytest
import sys
import os

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDocumentParser:
    """Tests for the document parsing engine (M1)."""

    def test_text_cleaner_normalize_whitespace(self):
        from app.core.parsing import cleaner
        result = cleaner.clean("Hello   World\n\n\n\nFoo\n\nBar")
        assert "Hello World" in result
        assert result.count("\n\n") <= 1

    def test_text_cleaner_remove_short_lines(self):
        from app.core.parsing import cleaner
        text = "A valid line\n1\nx\nAnother valid line with content"
        result = cleaner.clean(text)
        assert "A valid line" in result
        assert "Another valid line" in result

    def test_splitter_respects_chunk_size(self):
        from app.core.parsing import splitter
        text = "第一段内容。" * 500  # ~500 Chinese sentences
        chunks = splitter.split(text, total_pages=1)
        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.token_count > 0
            assert len(chunk.content_hash) == 64  # SHA256

    def test_splitter_overlap(self):
        from app.core.parsing import splitter
        # Generate paragraphs that should trigger overlap behavior
        paragraphs = [f"这是第{i}段内容，包含一些知识点和关键词。" for i in range(100)]
        text = "\n".join(paragraphs)
        chunks = splitter.split(text, total_pages=1)
        if len(chunks) > 1:
            # Each chunk should have a unique hash
            hashes = {c.content_hash for c in chunks}
            assert len(hashes) == len(chunks)


class TestAPIKeyCache:
    """Tests for the API cache system (M7)."""

    def test_cache_key_deterministic(self):
        from app.core.api_scheduler.cache import compute_cache_key
        k1 = compute_cache_key("测试内容", "template_1", "deepseek-chat", "config_hash")
        k2 = compute_cache_key("测试内容", "template_1", "deepseek-chat", "config_hash")
        assert k1 == k2

    def test_cache_key_different_content(self):
        from app.core.api_scheduler.cache import compute_cache_key
        k1 = compute_cache_key("内容A", "template_1", "deepseek-chat")
        k2 = compute_cache_key("内容B", "template_1", "deepseek-chat")
        assert k1 != k2

    def test_cache_key_different_model(self):
        from app.core.api_scheduler.cache import compute_cache_key
        k1 = compute_cache_key("内容", "template_1", "deepseek-chat")
        k2 = compute_cache_key("内容", "template_1", "gpt-4o")
        assert k1 != k2


class TestFSRS:
    """Tests for the FSRS spaced repetition algorithm (M4)."""

    def test_new_card_init(self):
        from app.core.memory import fsrs
        state = fsrs.init_card()
        assert state["state"] == "new"
        assert state["review_count"] == 0
        assert state["stability"] == 0.0

    def test_first_review_good(self):
        from app.core.memory import fsrs
        state = fsrs.init_card()
        updated = fsrs.review(state, fsrs.GOOD)
        assert updated["review_count"] == 1
        assert updated["state"] == "review"
        assert updated["stability"] == 0.6  # w[1] from DEFAULT_W
        assert updated["next_review_at"] is not None

    def test_first_review_again(self):
        from app.core.memory import fsrs
        state = fsrs.init_card()
        updated = fsrs.review(state, fsrs.AGAIN)
        assert updated["review_count"] == 1
        assert updated["state"] == "learning"
        assert updated["stability"] <= 0.5

    def test_difficulty_changes_with_ratings(self):
        from app.core.memory import fsrs
        # Start with a card that's been reviewed once
        state = fsrs.init_card()
        state = fsrs.review(state, fsrs.GOOD)

        # Easy rating should decrease difficulty
        easy_state = fsrs.review(state, fsrs.EASY)
        # Hard rating should increase difficulty (relative to previous)
        hard_state = fsrs.review(state, fsrs.HARD)

        # After "easy", difficulty should be less than after "hard"
        assert easy_state["difficulty"] <= hard_state["difficulty"]


class TestExamEngine:
    """Tests for the exam paper assembly and grading engine (M3)."""

    def _make_questions(self, count=20):
        return [
            {
                "id": f"q{i}",
                "question_type": "single_choice",
                "difficulty": "medium" if i % 2 == 0 else "easy",
                "tags": ["测试"],
                "question_text": f"Question {i}",
                "options": [{"label": "A", "text": "Option A"}, {"label": "B", "text": "Option B"}],
                "answer": "A",
                "analysis": f"Analysis {i}",
            }
            for i in range(count)
        ]

    def test_create_paper_basic(self):
        from app.core.quiz import exam_engine
        questions = self._make_questions(30)
        paper = exam_engine.create_paper(questions, {
            "title": "测试卷",
            "total_questions": 10,
        })
        assert len(paper["questions"]) == 10
        assert paper["total_score"] == 50  # 10 * 5
        assert len(paper["question_ids"]) == 10

    def test_create_paper_difficulty_mix(self):
        from app.core.quiz import exam_engine
        questions = self._make_questions(50)
        paper = exam_engine.create_paper(questions, {
            "title": "混合难度卷",
            "total_questions": 20,
            "difficulty_mix": {"easy": 0.5, "medium": 0.5},
        })
        assert len(paper["questions"]) == 20
        easy_count = sum(1 for q in paper["questions"] if q["difficulty"] == "easy")
        medium_count = sum(1 for q in paper["questions"] if q["difficulty"] == "medium")
        assert easy_count + medium_count == 20

    def test_grade_single_choice_correct(self):
        from app.core.quiz import exam_engine
        questions = self._make_questions(3)
        paper = {"questions": questions}
        answers = {"q0": "A", "q1": "A", "q2": "A"}
        result = exam_engine.grade(paper, answers)
        assert result["correct"] == 3
        assert result["score"] == 15
        assert result["percentage"] == 100.0

    def test_grade_mixed_results(self):
        from app.core.quiz import exam_engine
        questions = self._make_questions(3)
        paper = {"questions": questions}
        answers = {"q0": "A", "q1": "B", "q2": ""}  # q1 wrong, q2 unanswered
        result = exam_engine.grade(paper, answers)
        assert result["correct"] == 1
        assert result["percentage"] == pytest.approx(33.3, 0.1)


class TestPromptEngine:
    """Tests for the prompt template system."""

    def test_load_templates(self):
        from app.prompts import prompt_engine
        templates = prompt_engine.list_templates()
        assert "knowledge_tree" in templates
        assert "quiz_gen" in templates
        assert "flashcard" in templates

    def test_render_knowledge_tree(self):
        from app.prompts import prompt_engine
        messages = prompt_engine.render("knowledge_tree", "standard", chunk_text="测试知识点")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "测试知识点" in messages[1]["content"]

    def test_render_quiz(self):
        from app.prompts import prompt_engine
        messages = prompt_engine.render("quiz_gen", "single_choice",
                                         knowledge_points="计算机网络", count=5,
                                         difficulty="medium", difficulty_score=0.5,
                                         cognitive_level="L2_understand",
                                         cognitive_level_instruction="")
        assert len(messages) == 2
        assert "计算机网络" in messages[1]["content"]
        assert "5" in messages[1]["content"]
