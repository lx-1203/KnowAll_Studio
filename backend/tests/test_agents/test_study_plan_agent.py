"""Comprehensive tests for StudyPlanAgent.

Tests the Ebbinghaus retention rates, short-term and long-term
study plan generation, and knowledge point referencing.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

from app.core.agents.study_plan_agent import (
    StudyPlanAgent,
    EBBINGHAUS_INTERVALS,
)


# ---------------------------------------------------------------------------
# Helper constants
# ---------------------------------------------------------------------------

FAKE_START_DATE = datetime(2026, 3, 1)


# ---------------------------------------------------------------------------
# _retention_rate() tests
# ---------------------------------------------------------------------------

class TestRetentionRate:
    """Tests for StudyPlanAgent._retention_rate()."""

    def test_known_day_1_returns_58(self):
        """_retention_rate(1) returns 58% retention."""
        agent = StudyPlanAgent()
        assert agent._retention_rate(1) == 58

    def test_known_day_2_returns_44(self):
        """_retention_rate(2) returns 44% retention."""
        agent = StudyPlanAgent()
        assert agent._retention_rate(2) == 44

    def test_known_day_4_returns_36(self):
        """_retention_rate(4) returns 36% retention."""
        agent = StudyPlanAgent()
        assert agent._retention_rate(4) == 36

    def test_known_day_7_returns_28(self):
        """_retention_rate(7) returns 28% retention."""
        agent = StudyPlanAgent()
        assert agent._retention_rate(7) == 28

    def test_known_day_15_returns_21(self):
        """_retention_rate(15) returns 21% retention."""
        agent = StudyPlanAgent()
        assert agent._retention_rate(15) == 21

    def test_known_day_30_returns_20(self):
        """_retention_rate(30) returns 20% retention."""
        agent = StudyPlanAgent()
        assert agent._retention_rate(30) == 20

    def test_unknown_day_returns_20(self):
        """_retention_rate returns 20 for unknown days (e.g., day 3, 5, 99)."""
        agent = StudyPlanAgent()
        assert agent._retention_rate(3) == 20
        assert agent._retention_rate(5) == 20
        assert agent._retention_rate(10) == 20
        assert agent._retention_rate(99) == 20
        assert agent._retention_rate(0) == 20
        assert agent._retention_rate(-1) == 20


# ---------------------------------------------------------------------------
# _build_short_term_plan() tests
# ---------------------------------------------------------------------------

class TestBuildShortTermPlan:
    """Tests for StudyPlanAgent._build_short_term_plan()."""

    def test_produces_correct_number_of_days(self):
        """_build_short_term_plan produces correct number of days based on topic count."""
        agent = StudyPlanAgent()

        # Few topics -> 1 day
        plan_small = agent._build_short_term_plan(
            total_topics=5, daily_hours=2.0, start_date=FAKE_START_DATE
        )
        assert len(plan_small) == 1

        # More topics -> 2 days
        plan_medium = agent._build_short_term_plan(
            total_topics=30, daily_hours=2.0, start_date=FAKE_START_DATE
        )
        assert len(plan_medium) == 2

        # Many topics -> 3 days (max)
        plan_large = agent._build_short_term_plan(
            total_topics=60, daily_hours=2.0, start_date=FAKE_START_DATE
        )
        assert len(plan_large) == 3

    def test_each_day_has_time_slots(self):
        """_build_short_term_plan each day has time slot entries."""
        agent = StudyPlanAgent()
        plan = agent._build_short_term_plan(
            total_topics=20, daily_hours=2.0, start_date=FAKE_START_DATE
        )

        for day_entry in plan:
            assert "day" in day_entry
            assert "date" in day_entry
            assert "hours" in day_entry
            assert len(day_entry["hours"]) > 0

    def test_time_slots_start_at_8am(self):
        """_build_short_term_plan time slots start at 08:00."""
        agent = StudyPlanAgent()
        plan = agent._build_short_term_plan(
            total_topics=10, daily_hours=3.0, start_date=FAKE_START_DATE
        )

        first_day_hours = plan[0]["hours"]
        # First slot should be 08:00-09:00
        assert "08:00" in first_day_hours[0]["hour"]

    def test_number_of_time_slots_matches_daily_hours(self):
        """_build_short_term_plan produces correct number of time slots per day."""
        agent = StudyPlanAgent()
        plan = agent._build_short_term_plan(
            total_topics=10, daily_hours=4.0, start_date=FAKE_START_DATE
        )

        for day_entry in plan:
            assert len(day_entry["hours"]) == 4

    def test_dates_are_consecutive(self):
        """_build_short_term_plan produces consecutive dates across days."""
        agent = StudyPlanAgent()
        plan = agent._build_short_term_plan(
            total_topics=30, daily_hours=2.0, start_date=FAKE_START_DATE
        )

        dates = [day_entry["date"] for day_entry in plan]
        assert dates[0] == "2026-03-01"
        assert dates[1] == "2026-03-02"

    def test_hour_slots_have_required_fields(self):
        """Each hour slot has hour, topic, knowledge_point_ids, and is_review fields."""
        agent = StudyPlanAgent()
        plan = agent._build_short_term_plan(
            total_topics=5, daily_hours=2.0, start_date=FAKE_START_DATE
        )

        hour_slot = plan[0]["hours"][0]
        assert "hour" in hour_slot
        assert "topic" in hour_slot
        assert "knowledge_point_ids" in hour_slot
        assert "is_review" in hour_slot
        assert isinstance(hour_slot["knowledge_point_ids"], list)
        assert isinstance(hour_slot["is_review"], bool)


# ---------------------------------------------------------------------------
# _build_long_term_plan() tests
# ---------------------------------------------------------------------------

class TestBuildLongTermPlan:
    """Tests for StudyPlanAgent._build_long_term_plan()."""

    def test_produces_correct_number_of_weeks(self):
        """_build_long_term_plan produces correct number of weeks based on topics."""
        agent = StudyPlanAgent()

        # Few topics -> 1 week (min)
        plan_small = agent._build_long_term_plan(
            total_topics=3, daily_hours=1.0,
            start_date=FAKE_START_DATE, l1_nodes=[]
        )
        assert len(plan_small) == 1

        # Many topics -> 4 weeks (max)
        plan_large = agent._build_long_term_plan(
            total_topics=40, daily_hours=2.0,
            start_date=FAKE_START_DATE, l1_nodes=[]
        )
        assert len(plan_large) == 4

    def test_each_week_has_seven_days(self):
        """_build_long_term_plan each week has exactly 7 days."""
        agent = StudyPlanAgent()
        plan = agent._build_long_term_plan(
            total_topics=14, daily_hours=2.0,
            start_date=FAKE_START_DATE, l1_nodes=[]
        )

        for week_entry in plan:
            assert "week" in week_entry
            assert "days" in week_entry
            assert len(week_entry["days"]) == 7

    def test_marks_ebbinghaus_review_days_correctly(self):
        """_build_long_term_plan marks Ebbinghaus intervals as review days."""
        agent = StudyPlanAgent()
        plan = agent._build_long_term_plan(
            total_topics=10, daily_hours=2.0,
            start_date=FAKE_START_DATE, l1_nodes=[]
        )

        # Collect all days across all weeks
        all_days = []
        for week_entry in plan:
            all_days.extend(week_entry["days"])

        # Find the absolute day numbers
        for week_idx, week_entry in enumerate(plan):
            for day_entry in week_entry["days"]:
                abs_day = week_idx * 7 + day_entry["day"]

                if abs_day in EBBINGHAUS_INTERVALS:
                    assert day_entry["is_review_day"] is True, (
                        f"Day {abs_day} should be marked as review day "
                        f"(Ebbinghaus interval)"
                    )
                    assert day_entry["ebbinghaus_day"] == abs_day

    def test_non_review_days_are_not_marked(self):
        """_build_long_term_plan non-review days have is_review_day=False."""
        agent = StudyPlanAgent()
        plan = agent._build_long_term_plan(
            total_topics=14, daily_hours=2.0,
            start_date=FAKE_START_DATE, l1_nodes=[]
        )

        for week_idx, week_entry in enumerate(plan):
            for day_entry in week_entry["days"]:
                abs_day = week_idx * 7 + day_entry["day"]
                if abs_day not in EBBINGHAUS_INTERVALS:
                    assert day_entry["is_review_day"] is False, (
                        f"Day {abs_day} should NOT be marked as review day"
                    )
                    assert day_entry["ebbinghaus_day"] is None

    def test_each_day_has_topics(self):
        """_build_long_term_plan each day contains a topics list."""
        agent = StudyPlanAgent()
        plan = agent._build_long_term_plan(
            total_topics=14, daily_hours=2.0,
            start_date=FAKE_START_DATE, l1_nodes=[]
        )

        for week_entry in plan:
            for day_entry in week_entry["days"]:
                assert "topics" in day_entry
                assert isinstance(day_entry["topics"], list)
                assert "hours" in day_entry
                assert "date" in day_entry


# ---------------------------------------------------------------------------
# Ebbinghaus intervals tests
# ---------------------------------------------------------------------------

class TestEbbinghausIntervals:
    """Tests for Ebbinghaus interval constant."""

    def test_ebbinghaus_intervals_are_correct(self):
        """EBBINGHAUS_INTERVALS contains the expected days [1, 2, 4, 7, 15]."""
        assert EBBINGHAUS_INTERVALS == [1, 2, 4, 7, 15]

    def test_ebbinghaus_is_list_of_ints(self):
        """EBBINGHAUS_INTERVALS elements are integers."""
        for interval in EBBINGHAUS_INTERVALS:
            assert isinstance(interval, int)


# ---------------------------------------------------------------------------
# Class attribute tests
# ---------------------------------------------------------------------------

class TestStudyPlanAgentAttributes:
    """Tests for StudyPlanAgent class attributes."""

    def test_name_is_study_plan(self):
        """StudyPlanAgent.name is 'study_plan'."""
        agent = StudyPlanAgent()
        assert agent.name == "study_plan"

    def test_description_is_set(self):
        """StudyPlanAgent.description contains Chinese description text."""
        agent = StudyPlanAgent()
        assert isinstance(agent.description, str)
        assert len(agent.description) > 0
        assert "学习计划" in agent.description or "艾宾浩斯" in agent.description
