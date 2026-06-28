"""Quiz generation and exam system (M3)"""
import json
import random
from dataclasses import dataclass
from app.core.api_scheduler import api_client, TaskType, GenerationConfig


@dataclass
class QuizGenerationConfig:
    question_type: str = "single_choice"
    count: int = 10
    difficulty: str = "medium"


class QuizGenerator:
    """Generate questions via API, handle validation and storage."""

    TYPE_TO_TEMPLATE = {
        "single_choice": ("quiz_gen", "single_choice"),
        "multi_choice": ("quiz_gen", "multi_choice"),
        "true_false": ("quiz_gen", "true_false"),
        "fill_blank": ("quiz_gen", "fill_blank"),
        "short_answer": ("quiz_gen", "short_answer"),
        "calculation": ("quiz_gen", "calculation"),
        "formula": ("quiz_gen", "formula"),
        "coding": ("quiz_gen", "coding"),
        "material_analysis": ("quiz_gen", "material_analysis"),
    }

    async def generate_questions(
        self,
        chunk_texts: list[str],
        question_type: str = "single_choice",
        count: int = 10,
        model: str = "deepseek-chat",
        difficulty: str = "medium",
    ) -> list[dict]:
        """Generate questions from chunk texts with simplified interface.

        Used by QuestionBankAgent for batch generation.
        """
        knowledge_text = "\n\n".join(chunk_texts)
        config = QuizGenerationConfig(
            question_type=question_type,
            count=count,
            difficulty=difficulty,
        )
        return await self.generate(knowledge_text, config, model)

    async def generate(
        self,
        knowledge_text: str,
        config: QuizGenerationConfig,
        model: str = "deepseek-chat",
    ) -> list[dict]:
        """Generate quiz questions from knowledge text."""
        from app.prompts import prompt_engine

        cat, name = self.TYPE_TO_TEMPLATE.get(
            config.question_type, ("quiz_gen", "single_choice")
        )

        messages = prompt_engine.render(
            cat, name,
            knowledge_points=knowledge_text,
            count=config.count,
            difficulty=config.difficulty,
        )

        result = await api_client.generate(
            task_type=TaskType.QUIZ_GEN,
            messages=messages,
            prompt_template_id=f"{cat}.{name}",
            generation_content=knowledge_text + config.question_type + str(config.count),
            config=GenerationConfig(model=model),
        )
        return self._parse_questions(result.content)

    async def generate_variants(
        self,
        error_question: dict,
        count: int = 3,
        model: str = "deepseek-chat",
    ) -> list[dict]:
        """Generate variant questions based on an error question."""
        from app.prompts import prompt_engine

        prompt_text = f"""原题：{error_question.get('question_text', '')}
正确答案：{error_question.get('correct_answer', '')}
解析：{error_question.get('analysis', '')}

请生成{count}道同类型、同知识点的变式题。"""

        cat, name = self.TYPE_TO_TEMPLATE.get(
            error_question.get("question_type", "single_choice"),
            ("quiz_gen", "single_choice"),
        )

        messages = prompt_engine.render(
            cat, name,
            knowledge_points=prompt_text,
            count=count,
            difficulty=error_question.get("difficulty", "medium"),
        )

        result = await api_client.generate(
            task_type=TaskType.VARIANT_QUESTION,
            messages=messages,
            prompt_template_id=f"{cat}.{name}",
            generation_content=prompt_text,
            config=GenerationConfig(model=model),
        )
        return self._parse_questions(result.content)

    def _parse_questions(self, content: str) -> list[dict]:
        """Parse and validate question JSON from API response."""
        try:
            data = json.loads(content)
            questions = data.get("questions", data if isinstance(data, list) else [])
            return questions
        except json.JSONDecodeError:
            return []


class ExamEngine:
    """Local exam paper assembly and grading (no API calls)."""

    def create_paper(
        self,
        question_pool: list[dict],
        config: dict,
    ) -> dict:
        pool = [dict(q) for q in question_pool]  # deep copy to avoid mutating original

        # Apply filters
        if config.get("type_filter"):
            pool = [q for q in pool if q.get("question_type") in config["type_filter"]]
        if config.get("tag_filter"):
            pool = [q for q in pool if any(t in q.get("tags", []) for t in config["tag_filter"])]

        # Shuffle
        random.shuffle(pool)

        # Select questions based on difficulty mix
        total = config.get("total_questions", min(20, len(pool)))
        selected = []

        if "difficulty_mix" in config:
            remaining_pool = list(pool)
            for diff, ratio in config["difficulty_mix"].items():
                diff_pool = [q for q in remaining_pool if q.get("difficulty") == diff]
                count = int(total * ratio)
                picked = diff_pool[:count]
                selected.extend(picked)
                for q in picked:
                    if q in remaining_pool:
                        remaining_pool.remove(q)

        # Fill remaining with random questions
        remaining_needed = total - len(selected)
        if remaining_needed > 0:
            already_ids = {q.get("id") for q in selected}
            fillers = [q for q in pool if q.get("id") not in already_ids]
            random.shuffle(fillers)
            selected.extend(fillers[:remaining_needed])

        random.shuffle(selected)

        return {
            "title": config.get("title", "试卷"),
            "question_ids": [q["id"] for q in selected],
            "questions": selected,
            "total_score": len(selected) * 5,
            "config": config,
        }

    def grade(
        self,
        paper: dict,
        user_answers: dict[str, str],
        time_spent_ms: dict[str, int] | None = None,
        knowledge_point_ids: dict[str, str] | None = None,
    ) -> dict:
        """Grade a completed exam paper locally.

        Args:
            paper: Exam paper dict with questions
            user_answers: Dict of question_id -> user answer
            time_spent_ms: Dict of question_id -> time spent in ms
            knowledge_point_ids: Dict of question_id -> kp_id
        """
        questions = paper.get("questions", [])
        results = []
        correct_count = 0
        total_time = 0

        for q in questions:
            qid = q["id"]
            user_answer = user_answers.get(qid, "")
            correct_answer = q.get("answer", q.get("correct_answer", ""))
            q_time = time_spent_ms.get(qid, 0) if time_spent_ms else 0
            q_kp = knowledge_point_ids.get(qid, "") if knowledge_point_ids else ""

            is_correct = self._check_answer(user_answer, correct_answer, q.get("question_type"))

            if is_correct:
                correct_count += 1
            total_time += q_time

            results.append({
                "question_id": qid,
                "user_answer": user_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct,
                "analysis": q.get("analysis", ""),
                "time_spent_ms": q_time,
                "knowledge_point_id": q_kp,
            })

        return {
            "total": len(questions),
            "correct": correct_count,
            "score": correct_count * 5,
            "percentage": round(correct_count / max(1, len(questions)) * 100, 1),
            "time_spent_total_ms": total_time,
            "details": results,
        }

    def _check_answer(self, user: str, correct: str, qtype: str) -> bool:
        """Check if user answer matches correct answer."""
        user = user.strip().upper()
        correct = str(correct).strip().upper()

        if qtype == "multi_choice":
            # Compare sorted lists
            user_set = set(user.replace(",", "").replace(" ", ""))
            correct_set = set(correct.replace(",", "").replace(" ", ""))
            return user_set == correct_set

        if qtype in ("short_answer", "fill_blank", "material_analysis"):
            # Strict checking: reject empty/single-char, use keyword coverage
            user_clean = user.strip().lower()
            correct_clean = correct.strip().lower()
            if not user_clean or len(user_clean) <= 1:
                return False
            if user_clean == correct_clean:
                return True
            # Extract keywords from correct answer (Chinese chars or 2+ char words)
            import re
            correct_words = set(re.findall(r'[\u4e00-\u9fff]|[a-z0-9]{2,}', correct_clean))
            if not correct_words:
                return user_clean in correct_clean
            user_words = set(re.findall(r'[\u4e00-\u9fff]|[a-z0-9]{2,}', user_clean))
            if not user_words:
                return False
            overlap = len(user_words & correct_words) / len(correct_words)
            return overlap >= 0.5

        if qtype == "calculation":
            # Try numeric comparison with tolerance
            try:
                user_num = float(user.replace(",", ""))
                correct_num = float(correct.replace(",", ""))
                return abs(user_num - correct_num) < 0.01
            except (ValueError, TypeError):
                return user == correct

        if qtype == "coding":
            # Normalize whitespace and compare
            import re
            user_norm = re.sub(r"\s+", "", user)
            correct_norm = re.sub(r"\s+", "", correct)
            return user_norm == correct_norm

        if qtype == "formula":
            # Normalize whitespace and case-insensitive
            import re
            user_norm = re.sub(r"\s+", "", user).lower()
            correct_norm = re.sub(r"\s+", "", correct).lower()
            return user_norm == correct_norm

        # Default: exact match
        return user == correct


quiz_generator = QuizGenerator()
exam_engine = ExamEngine()
