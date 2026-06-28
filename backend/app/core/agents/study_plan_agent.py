"""Study Plan Agent - generates short-term and long-term study plans with Ebbinghaus review nodes"""
import logging
from datetime import datetime, timedelta
from app.core.agents.base import BaseAgent, AgentRegistry, AgentResult

logger = logging.getLogger(__name__)

# Ebbinghaus forgetting curve: review at day 1, 2, 4, 7, 15
EBBINGHAUS_INTERVALS = [1, 2, 4, 7, 15]


@AgentRegistry.register("study_plan")
class StudyPlanAgent(BaseAgent):
    """Generates study plans with Ebbinghaus spaced repetition nodes."""

    name = "study_plan"
    description = "基于知识点总结生成学习计划，结合艾宾浩斯遗忘曲线安排复习"

    async def run(self, summary_id: str, document_id: str, **kwargs) -> AgentResult:
        from app.database import async_session
        from app.models import KnowledgeSummary, KnowledgePointNode, StudyPlan, StudyGoal
        from sqlalchemy import select

        config = kwargs.get("config", {})
        plan_type = config.get("study_plan", {}).get("type", "both")
        daily_hours = config.get("study_plan", {}).get("daily_hours", 2.0)
        start_date_str = config.get("start_date")

        try:
            async for session in get_session():
                summary = await session.get(KnowledgeSummary, summary_id)
                if not summary:
                    return AgentResult(agent=self.name, status="error", error="Summary not found")

                # Load nodes
                stmt = select(KnowledgePointNode).where(
                    KnowledgePointNode.summary_id == summary_id
                ).order_by(KnowledgePointNode.level, KnowledgePointNode.sequence)
                result = await session.execute(stmt)
                nodes = result.scalars().all()

                if not nodes:
                    from app.core.knowledge.summary_generator import summary_generator
                    node_dicts = summary_generator.extract_nodes_from_markdown(summary.content_md, document_id)
                    nodes = node_dicts

                # Determine start date
                if start_date_str:
                    start_date = datetime.fromisoformat(start_date_str)
                else:
                    start_date = datetime.now() + timedelta(days=1)

                # Collect L1 topics as planning units
                l1_nodes = [n for n in nodes if (n.level if hasattr(n, 'level') else n.get('level')) == 1]
                l2_l3_nodes = [n for n in nodes if (n.level if hasattr(n, 'level') else n.get('level')) >= 2]

                total_topics = len(l2_l3_nodes) if l2_l3_nodes else len(l1_nodes)

                # Build Ebbinghaus review nodes
                ebbinghaus_nodes = []
                for day in EBBINGHAUS_INTERVALS:
                    ebbinghaus_nodes.append({
                        "day": day,
                        "review": True,
                        "description": f"第{day}天复习 - 根据艾宾浩斯遗忘曲线，此时记忆留存率约为{self._retention_rate(day)}%",
                    })

                short_term_plan = None
                long_term_plan = None

                if plan_type in ("short", "both"):
                    short_term_plan = self._build_short_term_plan(
                        total_topics, daily_hours, start_date
                    )

                if plan_type in ("long", "both"):
                    long_term_plan = self._build_long_term_plan(
                        total_topics, daily_hours, start_date, l1_nodes
                    )

                # Create study plan record
                plan = StudyPlan(
                    name=f"{summary.title if hasattr(summary, 'title') else '学习计划'} - {start_date.strftime('%Y-%m-%d')}",
                    description=f"基于 {total_topics} 个知识点的{'短期+长期' if plan_type == 'both' else plan_type + '期'}学习计划",
                    plan_type=plan_type,
                    daily_hours=daily_hours,
                    knowledge_point_ids=[n.id if hasattr(n, 'id') else n.get('id', '') for n in nodes],
                    ebbinghaus_nodes=ebbinghaus_nodes,
                    target_end_date=start_date + timedelta(days=28) if plan_type in ("long", "both") else start_date + timedelta(days=3),
                )
                session.add(plan)
                await session.commit()
                await session.refresh(plan)

                return AgentResult(
                    agent=self.name,
                    status="success",
                    result={
                        "plan_id": plan.id,
                        "name": plan.name,
                        "plan_type": plan_type,
                        "daily_hours": daily_hours,
                        "short_term_plan": short_term_plan,
                        "long_term_plan": long_term_plan,
                        "ebbinghaus_nodes": ebbinghaus_nodes,
                        "knowledge_point_ids": plan.knowledge_point_ids,
                    },
                )

        except Exception as e:
            logger.error(f"StudyPlanAgent failed: {e}", exc_info=True)
            return AgentResult(agent=self.name, status="error", error=str(e))

    def _build_short_term_plan(self, total_topics: int, daily_hours: float, start_date) -> list[dict]:
        """Build 1-3 day hourly schedule."""
        plan = []
        days = min(3, max(1, total_topics // 15))
        topics_per_day = max(1, total_topics // days)
        hours_per_day = daily_hours

        for day_idx in range(days):
            date = start_date + timedelta(days=day_idx)
            hours = []
            topic_counter = 0
            for hour_idx in range(int(hours_per_day)):
                hour_start = 8 + hour_idx  # Start at 8:00
                hour_str = f"{hour_start:02d}:00-{hour_start+1:02d}:00"
                if topic_counter < topics_per_day:
                    hours.append({
                        "hour": hour_str,
                        "topic": f"学习知识点 {day_idx * topics_per_day + topic_counter + 1} - {min(topics_per_day, total_topics - day_idx * topics_per_day)}",
                        "knowledge_point_ids": [],
                        "is_review": False,
                    })
                    topic_counter += 1
                else:
                    hours.append({
                        "hour": hour_str,
                        "topic": "自由复习/休息",
                        "knowledge_point_ids": [],
                        "is_review": True,
                    })
            plan.append({"day": day_idx + 1, "date": date.strftime("%Y-%m-%d"), "hours": hours})

        return plan

    def _build_long_term_plan(self, total_topics: int, daily_hours: float, start_date, l1_nodes: list) -> list[dict]:
        """Build 1-4 week daily schedule with Ebbinghaus review days."""
        plan = []
        weeks = min(4, max(1, total_topics // 5))
        topics_per_week = max(1, total_topics // weeks)

        for week_idx in range(weeks):
            days = []
            for day_idx in range(7):
                date = start_date + timedelta(days=week_idx * 7 + day_idx)
                day_num = week_idx * 7 + day_idx + 1

                # Check if this day is an Ebbinghaus review day
                is_review = day_num in EBBINGHAUS_INTERVALS
                ebbinghaus_day = day_num if is_review else None

                topics = min(2, total_topics - (week_idx * topics_per_week + day_idx * 2))

                days.append({
                    "day": day_idx + 1,
                    "date": date.strftime("%Y-%m-%d"),
                    "topics": [f"知识点 {week_idx * topics_per_week + day_idx * 2 + i + 1}" for i in range(max(0, topics))],
                    "hours": daily_hours,
                    "is_review_day": is_review,
                    "ebbinghaus_day": ebbinghaus_day,
                })

            plan.append({"week": week_idx + 1, "days": days})

        return plan

    def _retention_rate(self, day: int) -> int:
        """Estimate memory retention rate based on Ebbinghaus curve."""
        rates = {1: 58, 2: 44, 4: 36, 7: 28, 15: 21, 30: 20}
        return rates.get(day, 20)
