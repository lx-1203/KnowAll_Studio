"""Quiz generation and exam system (M3 — v2 with Bloom's Taxonomy + LLM-as-Judge + KG Relations)"""
import json
import random
import logging
import time
from dataclasses import dataclass, field

from app.core.api_scheduler import api_client, TaskType, GenerationConfig

logger = logging.getLogger(__name__)


# ============================================================
# Pipeline Stats — Track each stage of question generation
# ============================================================

@dataclass
class PipelineStats:
    """Track timing and counts for each stage of the quiz generation pipeline."""
    stage_times: dict[str, float] = field(default_factory=dict)
    stage_counts: dict[str, int] = field(default_factory=dict)
    _current_stage: str = ""
    _start_time: float = 0.0

    def start_stage(self, name: str):
        self._current_stage = name
        self._start_time = time.time()

    def end_stage(self, count: int = 0):
        elapsed = round(time.time() - self._start_time, 3)
        self.stage_times[self._current_stage] = elapsed
        if count:
            self.stage_counts[self._current_stage] = count
        logger.info(f"[Pipeline] {self._current_stage}: {elapsed}s, count={count}")
        return elapsed

    def summary(self) -> dict:
        return {
            "stages": self.stage_times,
            "counts": self.stage_counts,
            "total_time": round(sum(self.stage_times.values()), 3),
        }

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
        diff_label = self._difficulty_label(config.difficulty_score)

        pipeline = PipelineStats()

        # Stage 1: Generation
        pipeline.start_stage("1_generate")
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
        pipeline.end_stage(count=len(questions))

        # Stage 2: Review (LLM-as-Judge)
        if config.enable_review and questions:
            pipeline.start_stage("2_review")
            questions = await self._review_and_refine(questions, knowledge_text, config, model)
            reviewed = sum(1 for q in questions if q.get("reviewed"))
            passed = sum(1 for q in questions if q.get("review_decision") == "pass")
            revised = sum(1 for q in questions if q.get("review_decision") == "revised")
            rejected = sum(1 for q in questions if q.get("review_decision") == "reject")
            pipeline.end_stage(count=len(questions))
            logger.info(
                f"[Pipeline] Review results: {reviewed} reviewed, "
                f"{passed} passed, {revised} revised, {rejected} rejected"
            )

        # Attach pipeline stats to first question for downstream access
        if questions:
            questions[0]["_pipeline_stats"] = pipeline.summary()

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
        """Run LLM-as-Judge review on generated questions, revise or reject low-quality ones.

        Pipeline: Batch Review → Classify (pass/revise/reject) → Revise individually
        """
        from app.prompts import prompt_engine

        try:
            # Step 1: Batch review all questions
            t0 = time.time()
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
            review_time = round(time.time() - t0, 3)

            logger.info(
                f"[Review] Batch review complete in {review_time}s: "
                f"passed={summary.get('passed', 0)}, "
                f"revise={summary.get('revise', 0)}, "
                f"rejected={summary.get('rejected', 0)}, "
                f"avg_total={summary.get('average_total', 0)}"
            )

            # Step 2: Build review lookup by question_id
            review_map = {r.get("question_id"): r for r in reviews}

            # Step 3: Process each question
            final_questions = []
            revise_count = 0
            reject_count = 0
            t_revise = 0.0

            for q in questions:
                qid = q.get("id", "")
                review = review_map.get(qid)
                if not review:
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
                    try:
                        t1 = time.time()
                        revised = await self._revise_question(q, review, config, model)
                        t_revise += time.time() - t1
                        revise_count += 1
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
                    reject_count += 1
                    logger.debug(f"Question {qid} rejected (score={q.get('review_total', 0)})")

            if revise_count > 0:
                logger.info(
                    f"[Review] Revised {revise_count} questions in {round(t_revise, 3)}s "
                    f"(avg {round(t_revise/max(1,revise_count), 3)}s each)"
                )
            if reject_count > 0:
                logger.info(f"[Review] Rejected {reject_count} low-quality questions")

            # Step 4: Re-number question IDs to be sequential
            for i, q in enumerate(final_questions):
                if not q.get("id", "").startswith("cross_"):
                    q["id"] = f"q_{i+1}"

            return final_questions

        except Exception as e:
            logger.error(f"[Review] LLM-as-Judge review failed: {e}", exc_info=True)
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

    # -------- KG Relation-Aware Generation --------

    async def generate_with_relations(
        self,
        knowledge_text: str,
        config: QuizGenerationConfig,
        distractor_hints: str = "",
        cross_topic_hints: list[dict] | None = None,
        model: str = "deepseek-chat",
    ) -> list[dict]:
        """Generate questions enhanced with knowledge graph relation hints.

        Args:
            knowledge_text: Knowledge point content text.
            config: Generation configuration.
            distractor_hints: Pre-formatted confusion pair hints for better distractors.
            cross_topic_hints: Cross-topic relation hints for comprehensive questions.
            model: LLM model.
        """
        from app.prompts import prompt_engine

        cat, name = self.TYPE_TO_TEMPLATE.get(
            config.question_type, ("quiz_gen", "single_choice")
        )

        cognitive_instruction = get_cognitive_level_instruction(config.cognitive_level)
        diff_label = self._difficulty_label(config.difficulty_score)

        # Augment knowledge text with relation hints
        augmented_text = knowledge_text
        if distractor_hints:
            augmented_text = knowledge_text + "\n\n" + distractor_hints

        messages = prompt_engine.render(
            cat, name,
            knowledge_points=augmented_text,
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
            generation_content=augmented_text + config.question_type + str(config.count) + config.cognitive_level,
            config=GenerationConfig(model=model),
        )

        questions = self._parse_questions(result.content)

        if config.enable_review and questions:
            questions = await self._review_and_refine(questions, augmented_text, config, model)

        return questions

    async def generate_cross_topic(
        self,
        node_a: dict,
        node_b: dict,
        relation_type: str,
        relation_description: str,
        model: str = "deepseek-chat",
    ) -> list[dict]:
        """Generate a cross-topic question linking two related knowledge points.

        Uses a specialized prompt that asks the LLM to create questions testing
        the relationship between two concepts (prerequisite, confusion, etc.).
        """
        from app.prompts import prompt_engine

        # Build a standalone generation prompt for cross-topic questions
        cross_prompt = self._build_cross_topic_prompt(
            node_a, node_b, relation_type, relation_description
        )

        messages = [
            {"role": "system", "content": cross_prompt["system"]},
            {"role": "user", "content": cross_prompt["user"]},
        ]

        result = await api_client.generate(
            task_type=TaskType.QUIZ_GEN,
            messages=messages,
            prompt_template_id="quiz_gen.cross_topic",
            generation_content=f"{node_a.get('title','')}_{node_b.get('title','')}_{relation_type}",
            config=GenerationConfig(model=model),
        )

        questions = self._parse_questions(result.content)
        for q in questions:
            q["cross_topic"] = True
            q["cross_topic_sources"] = [
                node_a.get("id", node_a.get("title", "")),
                node_b.get("id", node_b.get("title", "")),
            ]
            q["relation_type"] = relation_type

        return questions

    def _build_cross_topic_prompt(
        self,
        node_a: dict,
        node_b: dict,
        relation_type: str,
        relation_description: str,
    ) -> dict:
        """Build a prompt for cross-topic question generation."""
        title_a = node_a.get("title", "")
        expl_a = node_a.get("explanation", "")[:300]
        title_b = node_b.get("title", "")
        expl_b = node_b.get("explanation", "")[:300]

        rel_labels = {
            "prerequisite": "前置依赖关系",
            "confused_with": "易混淆关系",
            "extends": "扩展延伸关系",
            "analogous_to": "类同关系",
            "contradicts": "对立关系",
            "applies_to": "应用关系",
        }
        rel_label = rel_labels.get(relation_type, "关联关系")

        if relation_type == "prerequisite":
            question_focus = (
                f"考察学生是否理解「{title_a}」是「{title_b}」的前置基础。"
                f"题目应检验：如果不掌握A，为什么学不好B？或者A中的哪个核心概念是B的关键支撑？"
            )
        elif relation_type == "confused_with":
            question_focus = (
                f"辨析「{title_a}」和「{title_b}」的核心区别。"
                f"干扰项应基于两者的典型混淆点设计。"
            )
        elif relation_type == "extends":
            question_focus = (
                f"考察「{title_a}」到「{title_b}」的递进关系。"
                f"题目应检验对扩展逻辑的理解——B在A的基础上增加了什么？"
            )
        else:
            question_focus = f"考察「{title_a}」和「{title_b}」之间的{rel_label}。"

        system = (
            f"你是一位专业命题专家。请生成一道跨知识点综合题，考察两个关联知识点之间的{rel_label}。\n\n"
            f"知识点A：{title_a}\n{expl_a}\n\n"
            f"知识点B：{title_b}\n{expl_b}\n\n"
            f"关系说明：{relation_description}\n\n"
            f"{question_focus}\n\n"
            f"输出格式（严格JSON）：\n"
            f'{{"questions": [{{"id": "cross_1", "type": "single_choice", '
            f'"cognitive_level": "L4_analyze", "difficulty_score": 0.65, '
            f'"tags": ["跨知识点", "{title_a}", "{title_b}"], '
            f'"question_text": "题目内容", '
            f'"options": [{{"label": "A", "text": ""}}, ...], '
            f'"answer": "A", '
            f'"analysis": "详细解析，说明两个知识点的关系和每个选项的对错原因"'
            f'}}]}}\n\n'
            f"只输出JSON。"
        )

        user = (
            f"请为以下两个知识点生成1道{rel_label}综合题：\n"
            f"知识点A：{title_a}\n"
            f"知识点B：{title_b}\n"
            f"关系：{relation_description}\n"
            f"输出JSON："
        )

        return {"system": system, "user": user}

    # -------- Parsing Utilities --------

    def _parse_questions(self, content: str) -> list[dict]:
        """Parse and validate question JSON from API response.

        Handles common LLM output issues: markdown code blocks, extra text around JSON.
        """
        import re

        # Try direct parse first
        try:
            data = json.loads(content)
            questions = data.get("questions", data if isinstance(data, list) else [])
            return self._normalize_questions(questions)
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown code blocks
        code_block_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
        if code_block_match:
            try:
                data = json.loads(code_block_match.group(1))
                questions = data.get("questions", data if isinstance(data, list) else [])
                return self._normalize_questions(questions)
            except json.JSONDecodeError:
                pass

        # Try finding JSON object/array boundaries
        json_match = re.search(r'(\[.*\]|\{.*\})', content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                questions = data.get("questions", data if isinstance(data, list) else [])
                return self._normalize_questions(questions)
            except json.JSONDecodeError:
                pass

        logger.warning("Failed to parse question JSON from LLM response")
        return []

    def _normalize_questions(self, questions: list[dict]) -> list[dict]:
        """Normalize question dicts to ensure consistent field names."""
        for q in questions:
            if "cognitive_level" not in q:
                q["cognitive_level"] = "L2_understand"
            if "difficulty_score" not in q:
                q["difficulty_score"] = 0.5
            if "answer" not in q and "correct_answer" in q:
                q["answer"] = q["correct_answer"]
            if "question_type" not in q and "type" in q:
                q["question_type"] = q["type"]
            elif "question_type" not in q and "type" not in q:
                q["question_type"] = "unknown"
        return questions

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
    """Exam paper assembly and grading — local rules + optional LLM semantic grading."""

    # Question types that benefit from LLM semantic grading
    SEMANTIC_GRADE_TYPES = {"short_answer", "material_analysis", "fill_blank"}

    async def grade_semantic(
        self,
        question_text: str,
        reference_answer: str,
        user_answer: str,
        model: str = "deepseek-chat",
    ) -> dict | None:
        """Grade an open-ended answer using LLM semantic evaluation.

        Returns a dict with scores, feedback, and matched/missed key points,
        or None if the LLM call fails (caller should fall back to local grading).
        """
        from app.prompts import prompt_engine
        from app.core.api_scheduler import api_client as _api, TaskType, GenerationConfig

        if not user_answer or not user_answer.strip():
            return {
                "scores": {"correctness": 0, "completeness": 0, "clarity": 0},
                "total_score": 0,
                "passed": False,
                "feedback": {
                    "strengths": [],
                    "weaknesses": ["未作答"],
                    "suggestion": "请认真作答",
                },
                "key_points_matched": [],
                "key_points_missed": ["(未作答)"],
            }

        try:
            messages = prompt_engine.render(
                "semantic_grade", "grade_semantic",
                question_text=question_text,
                reference_answer=reference_answer,
                user_answer=user_answer,
            )

            result = await _api.generate(
                task_type=TaskType.QUIZ_GEN,
                messages=messages,
                prompt_template_id="semantic_grade.grade_semantic",
                generation_content=question_text[:300] + user_answer[:200],
                config=GenerationConfig(model=model),
            )

            return json.loads(result.content)

        except Exception as e:
            logger.error(f"Semantic grading failed: {e}", exc_info=True)
            return None

    async def grade_enhanced(
        self,
        paper: dict,
        user_answers: dict[str, str],
        time_spent_ms: dict[str, int] | None = None,
        knowledge_point_ids: dict[str, str] | None = None,
        enable_semantic: bool = True,
        model: str = "deepseek-chat",
    ) -> dict:
        """Grade a paper with hybrid local + LLM semantic grading.

        Uses LLM semantic grading for short_answer/material_analysis/fill_blank,
        and local rule-based grading for objective types (choice/true_false/calculation).
        """
        questions = paper.get("questions", [])
        results = []
        correct_count = 0
        total_time = 0
        semantic_graded = 0

        for q in questions:
            qid = q["id"]
            qtype = q.get("question_type", q.get("type", ""))
            user_answer = user_answers.get(qid, "")
            correct_answer = q.get("answer", q.get("correct_answer", ""))
            q_time = time_spent_ms.get(qid, 0) if time_spent_ms else 0
            q_kp = knowledge_point_ids.get(qid, "") if knowledge_point_ids else ""

            # Decide grading strategy
            use_semantic = (
                enable_semantic
                and qtype in self.SEMANTIC_GRADE_TYPES
                and len(user_answer.strip()) > 5
            )

            semantic_result = None
            if use_semantic:
                semantic_result = await self.grade_semantic(
                    question_text=q.get("question_text", ""),
                    reference_answer=str(correct_answer),
                    user_answer=user_answer,
                    model=model,
                )
                if semantic_result:
                    semantic_graded += 1
                    # Pass threshold: total_score >= 6.0
                    is_correct = semantic_result.get("passed", semantic_result.get("total_score", 0) >= 6.0)
                else:
                    # Fall back to local grading
                    is_correct = self._check_answer(user_answer, correct_answer, qtype)
            else:
                is_correct = self._check_answer(user_answer, correct_answer, qtype)

            if is_correct:
                correct_count += 1
            total_time += q_time

            detail = {
                "question_id": qid,
                "user_answer": user_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct,
                "analysis": q.get("analysis", ""),
                "time_spent_ms": q_time,
                "knowledge_point_id": q_kp,
                "cognitive_level": q.get("cognitive_level", ""),
                "difficulty_score": q.get("difficulty_score", 0.5),
                "grading_method": "semantic" if semantic_result else "local",
            }

            if semantic_result:
                detail["semantic_scores"] = semantic_result.get("scores", {})
                detail["semantic_total"] = semantic_result.get("total_score", 0)
                detail["feedback"] = semantic_result.get("feedback", {})
                detail["key_points_matched"] = semantic_result.get("key_points_matched", [])
                detail["key_points_missed"] = semantic_result.get("key_points_missed", [])

            results.append(detail)

        return {
            "total": len(questions),
            "correct": correct_count,
            "score": correct_count * 5,
            "percentage": round(correct_count / max(1, len(questions)) * 100, 1),
            "time_spent_total_ms": total_time,
            "semantic_graded_count": semantic_graded,
            "details": results,
        }

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
