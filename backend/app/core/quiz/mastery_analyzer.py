"""Mastery Analyzer - AI-powered knowledge point mastery analysis and review recommendations

Core algorithm:
1. Maps answer records to knowledge points via knowledge_point_ids and KnowledgeCoverage
2. Calculates multi-factor mastery scores for each knowledge point
3. Uses LLM to generate personalized review recommendations for weak points
"""
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, and_, cast, Integer
from app.database import async_session
from app.models import (
    AnswerRecord, QuestionBank, KnowledgePointNode, KnowledgeCoverage,
    ErrorLog,
)

logger = logging.getLogger(__name__)


class MasteryAnalyzer:
    """Analyzes answer records to compute knowledge point mastery and generate review plans."""

    # Weights for multi-factor mastery calculation
    RECENCY_WEIGHT = 0.25       # Recent answers are more indicative
    ACCURACY_WEIGHT = 0.40      # Core metric: correct / total
    CONSISTENCY_WEIGHT = 0.20   # Repeated same error = weaker mastery
    ATTEMPT_WEIGHT = 0.15       # More attempts = higher confidence in the score

    WEAK_THRESHOLD = 0.65       # Mastery below this = weak
    MODERATE_THRESHOLD = 0.85   # Mastery between weak and this = moderate

    async def analyze(self, user_id: str = "local_user") -> dict:
        """Run full mastery analysis for a user.

        Returns:
            {
                "overall_mastery": float,
                "total_knowledge_points": int,
                "weak_points": [...],
                "moderate_points": [...],
                "strong_points": [...],
                "mastery_map": {kp_id: mastery_detail},
                "recommendations": [...],
            }
        """
        async with async_session() as session:
            # 1. Collect all answer records with knowledge point mappings
            answer_data = await self._collect_answer_data(session, user_id)
            if not answer_data:
                return self._empty_result()

            # 2. Calculate mastery for each knowledge point
            mastery_map = {}
            for kp_id, records in answer_data.items():
                mastery_map[kp_id] = self._calculate_mastery(records)

            # 3. Get knowledge point details
            kp_details = await self._get_kp_details(session, list(mastery_map.keys()))

            # 4. Classify and sort
            weak = []
            moderate = []
            strong = []
            for kp_id, score in mastery_map.items():
                detail = {
                    "kp_id": kp_id,
                    "title": kp_details.get(kp_id, {}).get("title", kp_id),
                    "level": kp_details.get(kp_id, {}).get("level", 1),
                    "explanation": kp_details.get(kp_id, {}).get("explanation", ""),
                    "mastery_score": round(score["mastery"], 4),
                    "accuracy": round(score["accuracy"], 4),
                    "total_attempts": score["total_attempts"],
                    "error_count": score["error_count"],
                    "last_attempt_at": score["last_attempt_at"],
                    "recency_score": round(score["recency_score"], 4),
                    "consistency_score": round(score["consistency_score"], 4),
                    "trend": score["trend"],  # "improving" | "declining" | "stable"
                }
                if score["mastery"] < self.WEAK_THRESHOLD:
                    weak.append(detail)
                elif score["mastery"] < self.MODERATE_THRESHOLD:
                    moderate.append(detail)
                else:
                    strong.append(detail)

            # Sort: lowest mastery first
            weak.sort(key=lambda x: x["mastery_score"])
            moderate.sort(key=lambda x: x["mastery_score"])
            strong.sort(key=lambda x: x["mastery_score"], reverse=True)

            # 5. Overall mastery
            if mastery_map:
                overall = sum(m["mastery"] for m in mastery_map.values()) / len(mastery_map)
            else:
                overall = 0.0

            return {
                "overall_mastery": round(overall, 4),
                "total_knowledge_points": len(mastery_map),
                "weak_count": len(weak),
                "moderate_count": len(moderate),
                "strong_count": len(strong),
                "weak_points": weak,
                "moderate_points": moderate,
                "strong_points": strong,
                "mastery_map": {
                    kp_id: {
                        "mastery": round(v["mastery"], 4),
                        "accuracy": round(v["accuracy"], 4),
                        "total_attempts": v["total_attempts"],
                        "error_count": v["error_count"],
                        "trend": v["trend"],
                    }
                    for kp_id, v in mastery_map.items()
                },
            }

    async def analyze_single(self, kp_id: str, user_id: str = "local_user") -> dict:
        """Deep analysis for a single knowledge point."""
        async with async_session() as session:
            records = await self._collect_kp_records(session, kp_id, user_id)
            if not records:
                return {"kp_id": kp_id, "mastery_score": None, "message": "No answer records found"}

            mastery = self._calculate_mastery(records)
            kp_details = await self._get_kp_details(session, [kp_id])

            # Get per-question breakdown
            question_details = []
            for r in records:
                question_details.append({
                    "question_id": r.get("question_id", ""),
                    "question_text": r.get("question_text", "")[:200],
                    "is_correct": r["is_correct"],
                    "user_answer": r.get("user_answer", ""),
                    "time_spent_ms": r.get("time_spent_ms", 0),
                    "answered_at": r.get("answered_at"),
                })

            return {
                "kp_id": kp_id,
                "title": kp_details.get(kp_id, {}).get("title", kp_id),
                "level": kp_details.get(kp_id, {}).get("level", 1),
                "explanation": kp_details.get(kp_id, {}).get("explanation", ""),
                "mastery_score": round(mastery["mastery"], 4),
                "accuracy": round(mastery["accuracy"], 4),
                "total_attempts": mastery["total_attempts"],
                "error_count": mastery["error_count"],
                "last_attempt_at": mastery["last_attempt_at"],
                "recency_score": round(mastery["recency_score"], 4),
                "consistency_score": round(mastery["consistency_score"], 4),
                "trend": mastery["trend"],
                "question_details": question_details,
            }

    async def get_answer_history(
        self,
        user_id: str = "local_user",
        kp_id: str | None = None,
        is_correct: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """Get paginated answer history with question and knowledge point info."""
        async with async_session() as session:
            offset = (page - 1) * page_size

            # Base query
            conditions = [AnswerRecord.user_id == user_id]
            if is_correct is not None:
                conditions.append(AnswerRecord.is_correct == is_correct)

            # Count
            count_stmt = select(func.count(AnswerRecord.id)).where(and_(*conditions))
            count_result = await session.execute(count_stmt)
            total = count_result.scalar() or 0

            # Fetch records
            stmt = (
                select(AnswerRecord)
                .where(and_(*conditions))
                .order_by(AnswerRecord.answered_at.desc())
                .offset(offset)
                .limit(page_size)
            )
            result = await session.execute(stmt)
            records = result.scalars().all()

            # Enrich with question and knowledge point info
            items = []
            for r in records:
                question = await session.get(QuestionBank, r.question_id)
                kp_ids = r.knowledge_point_ids or []

                # Get KP titles
                kp_titles = []
                if kp_ids:
                    kp_stmt = select(KnowledgePointNode.title).where(
                        KnowledgePointNode.id.in_(kp_ids)
                    )
                    kp_result = await session.execute(kp_stmt)
                    kp_titles = [row[0] for row in kp_result.fetchall()]

                # Filter by kp_id if specified
                if kp_id and kp_id not in kp_ids:
                    continue

                items.append({
                    "record_id": r.id,
                    "question_id": r.question_id,
                    "question_text": question.question_text[:300] if question else "(已删除)",
                    "question_type": question.question_type if question else "",
                    "cognitive_level": question.cognitive_level if question else "",
                    "difficulty_score": question.difficulty_score if question else 0.5,
                    "user_answer": r.user_answer,
                    "correct_answer": question.correct_answer if question else "",
                    "is_correct": r.is_correct,
                    "analysis": question.analysis if question else "",
                    "time_spent_ms": r.time_spent_ms,
                    "knowledge_point_ids": kp_ids,
                    "knowledge_point_titles": kp_titles,
                    "answered_at": r.answered_at.isoformat() if r.answered_at else None,
                })

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": items,
            }

    async def get_overall_stats(self, user_id: str = "local_user") -> dict:
        """Get overall answer statistics."""
        async with async_session() as session:
            total_stmt = select(func.count(AnswerRecord.id)).where(
                AnswerRecord.user_id == user_id
            )
            total = (await session.execute(total_stmt)).scalar() or 0

            correct_stmt = select(func.count(AnswerRecord.id)).where(
                AnswerRecord.user_id == user_id,
                AnswerRecord.is_correct == True,
            )
            correct = (await session.execute(correct_stmt)).scalar() or 0

            # Recent 7 days trend
            recent_data = []
            for i in range(7):
                day = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=i)).date()
                next_day = day + timedelta(days=1)
                day_stmt = select(
                    func.count(AnswerRecord.id),
                    func.sum(AnswerRecord.is_correct.cast(int)),
                ).where(
                    AnswerRecord.user_id == user_id,
                    AnswerRecord.answered_at >= day,
                    AnswerRecord.answered_at < next_day,
                )
                day_result = await session.execute(day_stmt)
                row = day_result.one()
                recent_data.append({
                    "date": day.isoformat(),
                    "total": row[0] or 0,
                    "correct": row[1] or 0,
                })

            # Per cognitive level stats
            level_stmt = select(
                QuestionBank.cognitive_level,
                func.count(AnswerRecord.id),
                func.sum(AnswerRecord.is_correct.cast(int)),
            ).join(
                AnswerRecord, AnswerRecord.question_id == QuestionBank.id
            ).where(
                AnswerRecord.user_id == user_id,
            ).group_by(QuestionBank.cognitive_level)
            level_result = await session.execute(level_stmt)
            cognitive_stats = {}
            for row in level_result.all():
                cognitive_stats[row[0]] = {
                    "total": row[1],
                    "correct": row[2] or 0,
                    "accuracy": round((row[2] or 0) / max(row[1], 1), 4),
                }

            return {
                "total_answers": total,
                "correct_answers": correct,
                "overall_accuracy": round(correct / max(total, 1), 4),
                "recent_7_days": recent_data,
                "cognitive_breakdown": cognitive_stats,
            }

    async def generate_review_recommendations(
        self,
        user_id: str = "local_user",
        model: str = "deepseek-chat",
    ) -> dict:
        """Generate AI-powered review recommendations based on mastery analysis."""
        analysis = await self.analyze(user_id)

        if not analysis["weak_points"] and not analysis["moderate_points"]:
            return {
                "has_weak_points": False,
                "message": "所有知识点掌握良好，继续保持！",
                "recommendations": [],
                "analysis": analysis,
            }

        # Build the prompt for AI
        weak_info = []
        for wp in analysis["weak_points"][:10]:  # Top 10 weakest
            weak_info.append({
                "title": wp["title"],
                "mastery": wp["mastery_score"],
                "accuracy": wp["accuracy"],
                "attempts": wp["total_attempts"],
                "errors": wp["error_count"],
                "trend": wp["trend"],
            })

        moderate_info = []
        for mp in analysis["moderate_points"][:5]:
            moderate_info.append({
                "title": mp["title"],
                "mastery": mp["mastery_score"],
                "accuracy": mp["accuracy"],
                "trend": mp["trend"],
            })

        # Try AI generation
        ai_recommendations = await self._call_ai_for_recommendations(
            weak_info, moderate_info, model
        )

        return {
            "has_weak_points": True,
            "weak_point_count": len(analysis["weak_points"]),
            "moderate_point_count": len(analysis["moderate_points"]),
            "overall_mastery": analysis["overall_mastery"],
            "recommendations": ai_recommendations,
            "weak_points_summary": weak_info,
            "moderate_points_summary": moderate_info,
            "analysis": analysis,
        }

    # ========== Private Methods ==========

    async def _collect_answer_data(self, session, user_id: str) -> dict[str, list[dict]]:
        """Collect all answer records grouped by knowledge point."""
        stmt = (
            select(AnswerRecord, QuestionBank)
            .join(QuestionBank, AnswerRecord.question_id == QuestionBank.id)
            .where(AnswerRecord.user_id == user_id)
            .order_by(AnswerRecord.answered_at.desc())
        )
        result = await session.execute(stmt)
        rows = result.all()

        data: dict[str, list[dict]] = defaultdict(list)
        for record, question in rows:
            kp_ids = record.knowledge_point_ids or []
            # Also try to get KPs from coverage table
            if not kp_ids:
                cov_stmt = select(KnowledgeCoverage.knowledge_point_id).where(
                    KnowledgeCoverage.resource_type == "question",
                    KnowledgeCoverage.resource_id == record.question_id,
                )
                cov_result = await session.execute(cov_stmt)
                kp_ids = [row[0] for row in cov_result.fetchall()]

            if not kp_ids:
                # Assign to a synthetic "uncategorized" bucket per question tag
                tag = question.tags[0] if question.tags else "未分类"
                kp_ids = [f"tag:{tag}"]

            for kp_id in kp_ids:
                data[kp_id].append({
                    "question_id": record.question_id,
                    "question_text": question.question_text,
                    "is_correct": record.is_correct,
                    "time_spent_ms": record.time_spent_ms,
                    "user_answer": record.user_answer,
                    "answered_at": record.answered_at,
                })

        return dict(data)

    async def _collect_kp_records(self, session, kp_id: str, user_id: str) -> list[dict]:
        """Collect answer records for a specific knowledge point."""
        # First find questions linked to this KP
        cov_stmt = select(KnowledgeCoverage.resource_id).where(
            KnowledgeCoverage.knowledge_point_id == kp_id,
            KnowledgeCoverage.resource_type == "question",
        )
        cov_result = await session.execute(cov_stmt)
        q_ids = [row[0] for row in cov_result.fetchall()]

        # Also find records with this kp_id in knowledge_point_ids
        stmt = (
            select(AnswerRecord, QuestionBank)
            .join(QuestionBank, AnswerRecord.question_id == QuestionBank.id)
            .where(
                AnswerRecord.user_id == user_id,
                AnswerRecord.knowledge_point_ids.contains([kp_id]),
            )
            .order_by(AnswerRecord.answered_at.desc())
        )
        result = await session.execute(stmt)
        rows = result.all()

        records = []
        seen_qids = set()
        for record, question in rows:
            if record.question_id not in seen_qids:
                seen_qids.add(record.question_id)
                records.append({
                    "question_id": record.question_id,
                    "question_text": question.question_text,
                    "is_correct": record.is_correct,
                    "time_spent_ms": record.time_spent_ms,
                    "user_answer": record.user_answer,
                    "answered_at": record.answered_at,
                })

        return records

    def _calculate_mastery(self, records: list[dict]) -> dict:
        """Calculate multi-factor mastery score for a knowledge point.

        Factors:
        1. Accuracy: ratio of correct to total answers
        2. Recency: exponential decay weight on older answers
        3. Consistency: penalty for repeated errors on the same question
        4. Attempt confidence: more attempts = less uncertainty
        """
        if not records:
            return {
                "mastery": 0.0, "accuracy": 0.0, "total_attempts": 0,
                "error_count": 0, "last_attempt_at": None,
                "recency_score": 0.0, "consistency_score": 1.0, "trend": "stable",
            }

        total = len(records)
        correct = sum(1 for r in records if r["is_correct"])
        error_count = total - correct
        accuracy = correct / total

        # Recency score: exponential decay over days, half-life = 7 days
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        recency_scores = []
        for r in records:
            answered_at = r.get("answered_at")
            if answered_at:
                if isinstance(answered_at, datetime):
                    days_ago = (now - answered_at.replace(tzinfo=None)).days
                else:
                    days_ago = 7  # default
                recency_scores.append(2 ** (-days_ago / 7))
            else:
                recency_scores.append(0.5)
        recency_score = sum(recency_scores) / len(recency_scores)

        # Consistency: check for repeated errors on the same question
        qid_errors = defaultdict(int)
        for r in records:
            if not r["is_correct"]:
                qid_errors[r["question_id"]] += 1
        # More than 1 error on the same question = consistency penalty
        repeated_errors = sum(max(0, c - 1) for c in qid_errors.values())
        consistency_score = max(0.1, 1.0 - (repeated_errors / max(total, 1)))

        # Attempt confidence: sigmoid-like function
        attempt_confidence = min(1.0, total / 5)  # Max confidence at 5+ attempts

        # Trend: compare first half vs second half accuracy
        mid = max(total // 2, 1)
        recent_half = records[:mid]
        older_half = records[mid:]
        recent_acc = sum(1 for r in recent_half if r["is_correct"]) / len(recent_half)
        older_acc = sum(1 for r in older_half if r["is_correct"]) / max(len(older_half), 1)
        if recent_acc > older_acc + 0.1:
            trend = "improving"
        elif recent_acc < older_acc - 0.1:
            trend = "declining"
        else:
            trend = "stable"

        # Combined mastery score
        weighted_accuracy = accuracy * self.ACCURACY_WEIGHT
        weighted_recency = recency_score * self.RECENCY_WEIGHT
        weighted_consistency = consistency_score * self.CONSISTENCY_WEIGHT
        weighted_attempt = attempt_confidence * self.ATTEMPT_WEIGHT

        # Adjust: if accuracy is good, boost slightly; if trend is declining, penalize
        mastery = weighted_accuracy + weighted_recency + weighted_consistency + weighted_attempt
        if trend == "declining":
            mastery *= 0.9
        elif trend == "improving":
            mastery *= 1.05

        mastery = min(1.0, max(0.0, mastery))

        return {
            "mastery": mastery,
            "accuracy": accuracy,
            "total_attempts": total,
            "error_count": error_count,
            "last_attempt_at": records[0].get("answered_at").isoformat() if records[0].get("answered_at") else None,
            "recency_score": recency_score,
            "consistency_score": consistency_score,
            "trend": trend,
        }

    async def _get_kp_details(self, session, kp_ids: list[str]) -> dict:
        """Get knowledge point details (title, level, explanation)."""
        if not kp_ids:
            return {}

        # Filter out synthetic tag-based IDs
        real_ids = [kp for kp in kp_ids if not kp.startswith("tag:")]
        details = {}

        if real_ids:
            stmt = select(KnowledgePointNode).where(KnowledgePointNode.id.in_(real_ids))
            result = await session.execute(stmt)
            for node in result.scalars().all():
                details[node.id] = {
                    "title": node.title,
                    "level": node.level,
                    "explanation": node.explanation or "",
                }

        # Add synthetic tag entries
        for kp in kp_ids:
            if kp.startswith("tag:"):
                tag = kp[4:]
                details[kp] = {"title": f"[标签] {tag}", "level": 1, "explanation": ""}

        return details

    async def _call_ai_for_recommendations(
        self, weak_info: list[dict], moderate_info: list[dict], model: str
    ) -> list[dict]:
        """Use LLM to generate personalized review recommendations."""
        try:
            from app.core.api_scheduler import api_client

            weak_desc = "\n".join(
                f"- {w['title']}: 掌握度{w['mastery']:.0%}, 正确率{w['accuracy']:.0%}, "
                f"尝试{w['attempts']}次, 错误{w['errors']}次, 趋势{w['trend']}"
                for w in weak_info
            )
            moderate_desc = "\n".join(
                f"- {m['title']}: 掌握度{m['mastery']:.0%}, 正确率{m['accuracy']:.0%}, 趋势{m['trend']}"
                for m in moderate_info
            )

            prompt = f"""你是一位学习教练。根据以下学生知识点掌握情况，给出个性化复习建议。

## 薄弱知识点（需重点复习）
{weak_desc if weak_desc else '无'}

## 一般知识点（需巩固）
{moderate_desc if moderate_desc else '无'}

请为每个薄弱知识点生成一条复习建议，格式为 JSON 数组：
[
  {{
    "knowledge_point": "知识点名称",
    "priority": "high/medium",
    "mastery_current": 0.45,
    "suggested_actions": ["具体行动1", "具体行动2"],
    "review_focus": "该知识点最需要强化的方面",
    "estimated_review_time_min": 15,
    "recommended_resources": "建议的学习资源类型"
  }}
]

输出严格 JSON 数组，不要包含其他内容。"""

            response = await api_client.call(
                model=model,
                system="你是专业的学习教练，擅长分析学生薄弱点并制定精准复习计划。只输出 JSON。",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000,
            )

            # Parse the response
            import json
            content = response.get("content", "") if isinstance(response, dict) else str(response)
            # Try to extract JSON array
            start = content.find("[")
            end = content.rfind("]") + 1
            if start >= 0 and end > start:
                recommendations = json.loads(content[start:end])
                return recommendations

            return self._fallback_recommendations(weak_info, moderate_info)

        except Exception as e:
            logger.warning(f"AI recommendation generation failed: {e}")
            return self._fallback_recommendations(weak_info, moderate_info)

    def _fallback_recommendations(self, weak_info: list[dict], moderate_info: list[dict]) -> list[dict]:
        """Generate rule-based recommendations when AI is unavailable."""
        recommendations = []

        for w in weak_info:
            actions = []
            if w["accuracy"] < 0.4:
                actions = [
                    "重新学习该知识点的原始材料",
                    f"从基础题开始练习，当前正确率仅{w['accuracy']:.0%}",
                    "制作该知识点的记忆闪卡，每天复习",
                ]
            elif w["accuracy"] < 0.6:
                actions = [
                    "针对该知识点做3-5道变式练习题",
                    "用自己的话总结该知识点的核心概念",
                    "查看错题解析，理解错误原因",
                ]
            else:
                actions = [
                    "做1-2道高难度综合题检验掌握程度",
                    "尝试向他人讲解该知识点",
                ]

            if w.get("trend") == "declining":
                actions.append("注意：掌握度呈下降趋势，建议尽快复习")

            recommendations.append({
                "knowledge_point": w["title"],
                "priority": "high",
                "mastery_current": w["mastery"],
                "suggested_actions": actions,
                "review_focus": "基础概念理解" if w["accuracy"] < 0.5 else "应用与综合",
                "estimated_review_time_min": 20 if w["accuracy"] < 0.5 else 10,
                "recommended_resources": "教材/课件" if w["accuracy"] < 0.4 else "练习题/模拟测试",
            })

        for m in moderate_info:
            recommendations.append({
                "knowledge_point": m["title"],
                "priority": "medium",
                "mastery_current": m["mastery"],
                "suggested_actions": [
                    "定期回顾该知识点，防止遗忘",
                    "结合其他知识点做综合性练习",
                ],
                "review_focus": "巩固与拓展",
                "estimated_review_time_min": 10,
                "recommended_resources": "思维导图/闪卡",
            })

        return recommendations

    def _empty_result(self) -> dict:
        return {
            "overall_mastery": 0.0,
            "total_knowledge_points": 0,
            "weak_count": 0,
            "moderate_count": 0,
            "strong_count": 0,
            "weak_points": [],
            "moderate_points": [],
            "strong_points": [],
            "mastery_map": {},
        }


mastery_analyzer = MasteryAnalyzer()
