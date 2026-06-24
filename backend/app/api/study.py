"""Study Plan API routes - learning roadmap, goals, and reminders"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from app.database import get_db
from app.models import StudyPlan, StudyGoal, StudyReminder

router = APIRouter(prefix="/api/v1/study", tags=["study"])


class CreatePlanRequest(BaseModel):
    name: str
    description: str = ""
    target_end_date: str | None = None
    goals: list[dict] = []


class CreateGoalRequest(BaseModel):
    plan_id: str
    title: str
    description: str = ""
    priority: str = "medium"
    due_date: str | None = None


class CreateReminderRequest(BaseModel):
    plan_id: str | None = None
    goal_id: str | None = None
    message: str
    remind_at: str
    repeat_daily: bool = False


# ===== Study Plans =====

@router.post("/plans")
async def create_plan(req: CreatePlanRequest, db: AsyncSession = Depends(get_db)):
    """Create a new study plan with optional goals."""
    plan = StudyPlan(
        name=req.name,
        description=req.description,
        target_end_date=datetime.fromisoformat(req.target_end_date) if req.target_end_date else None,
    )
    db.add(plan)
    await db.flush()

    for i, g in enumerate(req.goals or []):
        goal = StudyGoal(
            plan_id=plan.id,
            title=g.get("title", ""),
            description=g.get("description", ""),
            priority=g.get("priority", "medium"),
            due_date=datetime.fromisoformat(g["due_date"]) if g.get("due_date") else None,
            order_index=i,
        )
        db.add(goal)

    await db.commit()
    return {"plan_id": plan.id, "name": plan.name, "goal_count": len(req.goals or [])}


@router.get("/plans")
async def list_plans(db: AsyncSession = Depends(get_db)):
    """List all study plans with progress."""
    result = await db.execute(
        select(StudyPlan).order_by(StudyPlan.updated_at.desc())
    )
    plans = result.scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "progress": p.progress,
            "status": p.status,
            "target_end_date": p.target_end_date.isoformat() if p.target_end_date else None,
            "created_at": p.created_at.isoformat(),
        }
        for p in plans
    ]


@router.get("/plans/{plan_id}")
async def get_plan(plan_id: str, db: AsyncSession = Depends(get_db)):
    """Get a study plan with all its goals."""
    result = await db.execute(select(StudyPlan).where(StudyPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "Study plan not found")

    result = await db.execute(
        select(StudyGoal).where(StudyGoal.plan_id == plan_id).order_by(StudyGoal.order_index)
    )
    goals = result.scalars().all()

    return {
        "id": plan.id,
        "name": plan.name,
        "description": plan.description,
        "progress": plan.progress,
        "status": plan.status,
        "target_end_date": plan.target_end_date.isoformat() if plan.target_end_date else None,
        "created_at": plan.created_at.isoformat(),
        "goals": [
            {
                "id": g.id,
                "title": g.title,
                "description": g.description,
                "priority": g.priority,
                "completed": g.completed,
                "completed_at": g.completed_at.isoformat() if g.completed_at else None,
                "due_date": g.due_date.isoformat() if g.due_date else None,
                "order_index": g.order_index,
            }
            for g in goals
        ],
    }


@router.put("/plans/{plan_id}")
async def update_plan(plan_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    """Update a study plan."""
    result = await db.execute(select(StudyPlan).where(StudyPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "Study plan not found")

    if "name" in data:
        plan.name = data["name"]
    if "description" in data:
        plan.description = data["description"]
    if "status" in data:
        plan.status = data["status"]
    if "progress" in data:
        plan.progress = data["progress"]
    if "target_end_date" in data and data["target_end_date"]:
        plan.target_end_date = datetime.fromisoformat(data["target_end_date"])

    await db.commit()
    return {"status": "updated", "plan_id": plan.id}


@router.delete("/plans/{plan_id}")
async def delete_plan(plan_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a study plan and all its goals."""
    result = await db.execute(select(StudyPlan).where(StudyPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "Study plan not found")
    await db.delete(plan)
    await db.commit()
    return {"status": "deleted"}


# ===== Goals =====

@router.post("/goals")
async def create_goal(req: CreateGoalRequest, db: AsyncSession = Depends(get_db)):
    """Add a goal to a study plan."""
    result = await db.execute(select(StudyPlan).where(StudyPlan.id == req.plan_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Study plan not found")

    # Get max order_index
    order_result = await db.execute(
        select(func.count(StudyGoal.id)).where(StudyGoal.plan_id == req.plan_id)
    )
    max_order = order_result.scalar() or 0

    goal = StudyGoal(
        plan_id=req.plan_id,
        title=req.title,
        description=req.description,
        priority=req.priority,
        due_date=datetime.fromisoformat(req.due_date) if req.due_date else None,
        order_index=max_order,
    )
    db.add(goal)
    await db.commit()
    return {"goal_id": goal.id, "title": goal.title}


@router.put("/goals/{goal_id}/toggle")
async def toggle_goal(goal_id: str, db: AsyncSession = Depends(get_db)):
    """Toggle goal completion status."""
    result = await db.execute(select(StudyGoal).where(StudyGoal.id == goal_id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(404, "Goal not found")

    goal.completed = not goal.completed
    goal.completed_at = datetime.now(timezone.utc).replace(tzinfo=None) if goal.completed else None
    await db.flush()

    # Recalculate plan progress
    result = await db.execute(
        select(func.count(StudyGoal.id)).where(StudyGoal.plan_id == goal.plan_id)
    )
    total_goals = result.scalar() or 1
    result = await db.execute(
        select(func.count(StudyGoal.id)).where(
            StudyGoal.plan_id == goal.plan_id,
            StudyGoal.completed == True,
        )
    )
    completed_goals = result.scalar() or 0

    result = await db.execute(select(StudyPlan).where(StudyPlan.id == goal.plan_id))
    plan = result.scalar_one_or_none()
    if plan:
        plan.progress = round(completed_goals / max(total_goals, 1) * 100, 1)
        if plan.progress >= 100:
            plan.status = "completed"

    await db.commit()
    return {"goal_id": goal.id, "completed": goal.completed, "plan_progress": round(completed_goals / max(total_goals, 1) * 100, 1)}


@router.delete("/goals/{goal_id}")
async def delete_goal(goal_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a goal."""
    result = await db.execute(select(StudyGoal).where(StudyGoal.id == goal_id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(404, "Goal not found")
    await db.delete(goal)
    await db.commit()
    return {"status": "deleted"}


# ===== Reminders =====

@router.post("/reminders")
async def create_reminder(req: CreateReminderRequest, db: AsyncSession = Depends(get_db)):
    """Create a study reminder."""
    reminder = StudyReminder(
        plan_id=req.plan_id,
        goal_id=req.goal_id,
        message=req.message,
        remind_at=datetime.fromisoformat(req.remind_at),
        repeat_daily=req.repeat_daily,
    )
    db.add(reminder)
    await db.commit()
    return {"reminder_id": reminder.id, "message": reminder.message}


@router.get("/reminders/due")
async def get_due_reminders(db: AsyncSession = Depends(get_db)):
    """Get reminders that are due now and unread."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    result = await db.execute(
        select(StudyReminder)
        .where(StudyReminder.remind_at <= now, StudyReminder.is_read == False)
        .order_by(StudyReminder.remind_at)
    )
    reminders = result.scalars().all()
    return {
        "count": len(reminders),
        "reminders": [
            {
                "id": r.id,
                "message": r.message,
                "remind_at": r.remind_at.isoformat(),
                "is_read": r.is_read,
                "repeat_daily": r.repeat_daily,
                "plan_id": r.plan_id,
                "goal_id": r.goal_id,
            }
            for r in reminders
        ],
    }


@router.post("/reminders/{reminder_id}/read")
async def mark_reminder_read(reminder_id: str, db: AsyncSession = Depends(get_db)):
    """Mark a reminder as read."""
    result = await db.execute(select(StudyReminder).where(StudyReminder.id == reminder_id))
    rem = result.scalar_one_or_none()
    if not rem:
        raise HTTPException(404, "Reminder not found")
    rem.is_read = True
    await db.commit()
    return {"status": "read"}
