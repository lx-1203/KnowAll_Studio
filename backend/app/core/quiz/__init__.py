"""Quiz generation and exam system (M3 — v2 with Bloom's Taxonomy + LLM-as-Judge)"""
import json
import random
import logging
from dataclasses import dataclass, field

from app.core.api_scheduler import api_client, TaskType, GenerationConfig

logger = logging.getLogger(__name__)

# ============================================================
# Bloom's Revised Taxonomy — Cognitive Level Definitions
# ============================================================

BLOOM_LEVELS: dict[str, dict] = {
    "L1_remember": {
        "label": "记忆",
        "verbs": "列出、定义、命名、识别、回忆、描述",
        "instruction": (
            "本次出题目标认知层次为 L1_remember（记忆）。\n"
            "题目应考察学生对事实、术语、基本概念和定义的回忆能力。\n"
            "使用动词如：列出、定义、命名、识别、描述。\n"
            "题目是封闭式的，有唯一确定的答案，不需要推理或分析。"
        ),
        "typical_types": ["single_choice", "true_false", "fill_blank"],
    },
    "L2_understand": {
        "label": "理解",
        "verbs": "解释、总结、举例、分类、比较、说明",
        "instruction": (
            "本次出题目标认知层次为 L2_understand（理解）。\n"
            "题目应考察学生对概念的理解——能否用自己的话解释、举例说明或进行分类。\n"
            "使用动词如：解释、总结、举例、分类、说明、改写。\n"
            "题目要求学生展示对知识的内涵理解，而非简单回忆。"
        ),
        "typical_types": ["single_choice", "multi_choice", "true_false", "fill_blank", "short_answer"],
    },
    "L3_apply": {
        "label": "应用",
        "verbs": "使用、计算、解决、实现、执行、演示",
        "instruction": (
            "本次出题目标认知层次为 L3_apply（应用）。\n"
            "题目应考察学生在新的具体情境中使用所学知识解决问题的能力。\n"
            "使用动词如：使用、计算、解决、实现、执行、演示。\n"
            "题目需要提供具体场景/数据，要求学生运用方法/公式/原理得出结果。"
        ),
        "typical_types": ["calculation", "formula", "coding", "single_choice", "short_answer"],
    },
    "L4_analyze": {
        "label": "分析",
        "verbs": "区分、比较、归因、解构、检查、质疑",
        "instruction": (
            "本次出题目标认知层次为 L4_analyze（分析）。\n"
            "题目应考察学生将材料分解为组成部分、识别因果关系、区分相关与不相关信息的能力。\n"
            "使用动词如：区分、比较、归因、解构、检查、质疑。\n"
            "题目需要包含需要分析的复杂材料或情境，要求学生找出证据、推理关系或结构。"
        ),
        "typical_types": ["short_answer", "material_analysis", "multi_choice", "coding"],
    },
    "L5_evaluate": {
        "label": "评价",
        "verbs": "评估、论证、判断、辩护、批判、推荐",
        "instruction": (
            "本次出题目标认知层次为 L5_evaluate（评价）。\n"
            "题目应考察学生基于标准做出判断的能力——评估方案优劣、论证观点、批判错误论证。\n"
            "使用动词如：评估、论证、判断、辩护、批判、推荐。\n"
            "题目需要提供有争议或需要权衡的情境，要求学生明确给出评价标准和判断理由。"
        ),
        "typical_types": ["material_analysis", "short_answer", "multi_choice"],
    },
    "L6_create": {
        "label": "创造",
        "verbs": "设计、构建、规划、产出、发明、改进",
        "instruction": (
            "本次出题目标认知层次为 L6_create（创造）。\n"
            "题目应考察学生将要素组合成新的、原创性的产品或方案的能力。\n"
            "使用动词如：设计、构建、规划、产出、发明、改进。\n"
            "题目要求开放式的产出，可以有多种合理答案，重点考察创新性和综合运用能力。"
        ),
        "typical_types": ["coding", "short_answer", "material_analysis"],
    },
}


def get_cognitive_level_instruction(level: str) -> str:
    """Get the Bloom instruction text for a given cognitive level."""
    if level in BLOOM_LEVELS:
        return BLOOM_LEVELS[level]["instruction"]
    # Default to L2 if unknown
    return BLOOM_LEVELS["L2_understand"]["instruction"]


def get_cognitive_level_label(level: str) -> str:
    """Get Chinese label for a cognitive level."""
    if level in BLOOM_LEVELS:
        return BLOOM_LEVELS[level]["label"]
    return level


# ============================================================
# Config
# ============================================================

@dataclass
class QuizGenerationConfig:
    question_type: str = "single_choice"
    count: int = 10
    difficulty: str = "medium"               # legacy categorical: easy/medium/hard
    difficulty_score: float = 0.5             # NEW: continuous 0.0-1.0
    cognitive_level: str = "L2_understand"    # NEW: Bloom level
    enable_review: bool = True                # NEW: run LLM-as-Judge after generation
    review_threshold: float = 3.2             # NEW: min total score to pass review


# ============================================================
# QuizGenerator
# ============================================================

class QuizGenerator:
    """Generate questions via API, with optional LLM-as-Judge review."""

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
        difficulty_score: float = 0.5,
        cognitive_level: str = "L2_understand",
        enable_review: bool = True,
    ) -> list[dict]:
        """Generate questions from chunk texts with simplified interface.

        Used by QuestionBankAgent for batch generation.
        """
        knowledge_text = "\n\n".join(chunk_texts)
        config = QuizGenerationConfig(
            question_type=question_type,
            count=count,
            difficulty=difficulty,
            difficulty_score=difficulty_score,
            cognitive_level=cognitive_level,
            enable_review=enable_review,
        )
        return await self.generate(knowledge_text, config, model)

    async def generate(
        self,
        knowledge_text: str,
        config: QuizGenerationConfig,
        model: str = "deepseek-chat",
    ) -> list[dict]:
        """Generate quiz questions from knowledge text.

        Pipeline:
        1. Render prompt with cognitive level instruction
        2. Call LLM to generate questions
        3. (Optional) Run LLM-as-Judge review → revise rejected questions
        """
        from app.prompts import prompt_engine

        cat, name = self.TYPE_TO_TEMPLATE.get(
            config.question_type, ("quiz_gen", "single_choice")
        )

        # Build cognitive level instruction for the prompt
        cognitive_instruction = get_cognitive_level_instruction(config.cognitive_level)

        # Render difficulty_score to a readable string
        diff_label = self._difficulty_label(config.difficulty_score)

        messages = prompt_engine.render(
            cat, name,
            knowledge_points=knowledge_text,
            count=config.count,
            difficulty=config.difficulty,
            difficulty_score=diff_label,
            cognitive_level=config.cognitive_level,
            cognitive_level_instruction=cognitive_instruction,
        )

        result = await api_client.generate(
            task_type=TaskType.QUIZ_GEN,
            messages=messages,
            prompt_template_id=f"{cat}.{name}",
            generation_content=knowledge_text + config.question_type + str(config.count) + config.cognitive_level,
            config=GenerationConfig(model=model),
        )

        questions = self._parse_questions(result.content)

        # If review is enabled, run LLM-as-Judge and auto-revise
        if config.enable_review and questions:
            questions = await self._review_and_refine(
                questions, knowledge_text, config, model
            )

        return questions

    async def generate_variants(
        self,
        error_question: dict,
        count: int = 3,
        model: str = "deepseek-chat",
    ) -> list[dict]:
        """Generate variant questions based on an error question."""
        from app.prompts import prompt_engine

        cognitive_level = error_question.get("cognitive_level", "L2_understand")
        cognitive_instruction = get_cognitive_level_instruction(cognitive_level)

        prompt_text = f"""原题：{error_question.get('question_text', '')}
正确答案：{error_question.get('correct_answer', error_question.get('answer', ''))}
解析：{error_question.get('analysis', '')}

请生成{count}道同类型、同知识点的变式题（更换具体数值/场景/表述，但考察相同知识点）。"""

        qtype = error_question.get("question_type", error_question.get("type", "single_choice"))
        cat, name = self.TYPE_TO_TEMPLATE.get(qtype, ("quiz_gen", "single_choice"))

        difficulty_score = error_question.get("difficulty_score", 0.5)
        diff_label = self._difficulty_label(difficulty_score)

        messages = prompt_engine.render(
            cat, name,
            knowledge_points=prompt_text,
            count=count,
            difficulty=error_question.get("difficulty", "medium"),
            difficulty_score=diff_label,
            cognitive_level=cognitive_level,
            cognitive_level_instruction=cognitive_instruction,
        )

        result = await api_client.generate(
            task_type=TaskType.VARIANT_QUESTION,
            messages=messages,
            prompt_template_id=f"{cat}.{name}",
            generation_content=prompt_text,
            config=GenerationConfig(model=model),
        )
        return self._parse_questions(result.content)

    # -------- LLM-as-Judge Review Pipeline --------

    async def _review_and_refine(
        self,
        questions: list[dict],
        knowledge_text: str,
        config: QuizGenerationConfig,
        model: str,
    ) -> list[dict]:
        """Run LLM-as-Judge review on generated questions, revise or reject low-quality ones."""
        from app.prompts import prompt_engine

        try:
            # Step 1: Review all questions in one batch
            questions_json = json.dumps(questions, ensure_ascii=False, indent=2)
            review_messages = prompt_engine.render(
                "quiz_review", "review_single",
                questions_json=questions_json,
                cognitive_level=config.cognitive_level,
                knowledge_points=knowledge_text,
            )

            review_result = await api_client.generate(
                task_type=TaskType.QUIZ_GEN,
                messages=review_messages,
                prompt_template_id="quiz_review.review_single",
                generation_content=questions_json[:500],
                config=GenerationConfig(model=model),
            )

            review_data = self._parse_review(review_result.content)
            reviews = review_data.get("reviews", [])
            summary = review_data.get("summary", {})

            logger.info(
                f"LLM-as-Judge review complete: passed={summary.get('passed', 0)}, "
                f"revise={summary.get('revise', 0)}, rejected={summary.get('rejected', 0)}, "
                f"avg_total={summary.get('average_total', 0)}"
            )

            # Step 2: Build review lookup by question_id
            review_map = {r.get("question_id"): r for r in reviews}

            # Step 3: Process each question
            final_questions = []
            for q in questions:
                qid = q.get("id", "")
                review = review_map.get(qid)
                if not review:
                    # No review → keep as-is
                    q["reviewed"] = False
                    final_questions.append(q)
                    continue

                decision = review.get("decision", "pass")
                q["review_scores"] = review.get("scores", {})
                q["review_total"] = review.get("total_score", 0)

                if decision == "pass":
                    q["reviewed"] = True
                    q["review_decision"] = "pass"
                    final_questions.append(q)

                elif decision == "revise":
                    # Try to auto-revise
                    try:
                        revised = await self._revise_question(q, review, config, model)
                        if revised:
                            revised["reviewed"] = True
                            revised["review_decision"] = "revised"
                            final_questions.append(revised)
                        else:
                            q["reviewed"] = True
                            q["review_decision"] = "revise_failed"
                            final_questions.append(q)
                    except Exception as e:
                        logger.warning(f"Revision failed for question {qid}: {e}")
                        q["reviewed"] = True
                        q["review_decision"] = "revise_error"
                        final_questions.append(q)

                else:  # reject
                    logger.info(f"Question {qid} rejected by LLM-as-Judge (score={q.get('review_total', 0)})")
                    # Don't include rejected questions
                    continue

            rejected_count = len(questions) - len(final_questions)
            if rejected_count > 0:
                logger.info(f"Rejected {rejected_count} low-quality questions")

            return final_questions

        except Exception as e:
            logger.error(f"LLM-as-Judge review failed: {e}", exc_info=True)
            # Fall back to returning original questions without review
            for q in questions:
                q["reviewed"] = False
                q["review_error"] = str(e)
            return questions

    async def _revise_question(
        self,
        question: dict,
        review: dict,
        config: QuizGenerationConfig,
        model: str,
    ) -> dict | None:
        """Revise a single question based on review feedback."""
        from app.prompts import prompt_engine

        cognitive_instruction = get_cognitive_level_instruction(config.cognitive_level)

        revise_messages = prompt_engine.render(
            "quiz_review", "revise_single",
            question_json=json.dumps(question, ensure_ascii=False, indent=2),
            review_json=json.dumps(review, ensure_ascii=False, indent=2),
            cognitive_level=config.cognitive_level,
            cognitive_level_instruction=cognitive_instruction,
        )

        result = await api_client.generate(
            task_type=TaskType.QUIZ_GEN,
            messages=revise_messages,
            prompt_template_id="quiz_review.revise_single",
            generation_content=json.dumps(question)[:500],
            config=GenerationConfig(model=model),
        )

        revised_data = self._parse_review(result.content)
        revised_list = revised_data.get("revised_questions", [])
        if revised_list:
            return revised_list[0]
        return None

    # -------- Parsing Utilities --------

    def _parse_questions(self, content: str) -> list[dict]:
        """Parse and validate question JSON from API response."""
        try:
            data = json.loads(content)
            questions = data.get("questions", data if isinstance(data, list) else [])
            # Normalize fields: ensure each question has core fields
            for q in questions:
                if "cognitive_level" not in q:
                    q["cognitive_level"] = "L2_understand"
                if "difficulty_score" not in q:
                    q["difficulty_score"] = 0.5
                if "answer" not in q and "correct_answer" in q:
                    q["answer"] = q["correct_answer"]
                if "question_type" not in q and "type" in q:
                    q["question_type"] = q["type"]
            return questions
        except json.JSONDecodeError:
            logger.warning("Failed to parse question JSON from LLM response")
            return []

    def _parse_review(self, content: str) -> dict:
        """Parse review JSON from API response."""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Failed to parse review JSON from LLM response")
            return {}

    @staticmethod
    def _difficulty_label(score: float) -> str:
        """Convert a 0-1 difficulty score to a human-readable label."""
        if score <= 0.25:
            return f"很简单 ({score:.2f})"
        elif score <= 0.45:
            return f"偏简单 ({score:.2f})"
        elif score <= 0.60:
            return f"中等 ({score:.2f})"
        elif score <= 0.80:
            return f"偏困难 ({score:.2f})"
        else:
            return f"困难 ({score:.2f})"


# ============================================================
# ExamEngine
# ============================================================

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
        if config.get("cognitive_level_filter"):
            pool = [q for q in pool if q.get("cognitive_level") in config["cognitive_level_filter"]]

        # Shuffle
        random.shuffle(pool)

        # Select questions based on difficulty mix (supports both legacy and continuous)
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
        elif "difficulty_range" in config:
            # New: filter by continuous difficulty_score range
            dr = config["difficulty_range"]
            range_pool = [
                q for q in pool
                if dr[0] <= q.get("difficulty_score", 0.5) <= dr[1]
            ]
            random.shuffle(range_pool)
            selected = range_pool[:total]

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

        Returns detailed per-question results with scores and analysis.
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

            is_correct = self._check_answer(
                user_answer, correct_answer,
                q.get("question_type", q.get("type", "")),
            )

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
                "cognitive_level": q.get("cognitive_level", ""),
                "difficulty_score": q.get("difficulty_score", 0.5),
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
        """Check if user answer matches correct answer.

        Strategies per question type, enhanced for Chinese educational context.
        """
        user = user.strip()
        correct = str(correct).strip()

        if not user:
            return False

        if qtype == "multi_choice":
            # Compare sorted option sets
            user_chars = set(user.upper().replace(",", "").replace(" ", "").replace("，", ""))
            correct_chars = set(correct.upper().replace(",", "").replace(" ", "").replace("，", ""))
            return user_chars == correct_chars

        if qtype in ("short_answer", "fill_blank", "material_analysis"):
            # Enhanced semantic-aware checking
            user_clean = user.strip().lower()
            correct_clean = correct.strip().lower()

            if len(user_clean) <= 1:
                return False
            if user_clean == correct_clean:
                return True

            # Extract keywords: Chinese chars, 2+ char alphanumeric tokens
            import re
            correct_words = set(re.findall(r'[\u4e00-\u9fff]+|[a-z0-9]{2,}', correct_clean))
            if not correct_words:
                return user_clean in correct_clean
            user_words = set(re.findall(r'[\u4e00-\u9fff]+|[a-z0-9]{2,}', user_clean))
            if not user_words:
                return False
            overlap = len(user_words & correct_words) / len(correct_words)
            return overlap >= 0.5

        if qtype == "calculation":
            # Numeric comparison with tolerance
            try:
                user_num = float(user.replace(",", "").replace("，", ""))
                correct_num = float(correct.replace(",", "").replace("，", ""))
                return abs(user_num - correct_num) < 0.01
            except (ValueError, TypeError):
                # Fall back to normalized string comparison
                return user.replace(" ", "").lower() == correct.replace(" ", "").lower()

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

        # Default: case-insensitive exact match after trimming
        return user.upper() == correct.upper()


# ============================================================
# Singleton instances
# ============================================================

quiz_generator = QuizGenerator()
exam_engine = ExamEngine()
