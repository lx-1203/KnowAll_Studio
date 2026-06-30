"""Study Plan API routes - learning roadmap, goals, and reminders"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from app.database import get_db
from app.models import StudyPlan, StudyGoal, StudyReminder
from app.core.auth import get_optional_user, get_user_id, load_user_api_keys

router = APIRouter(prefix="/api/v1/study", tags=["study"])


class GeneratePlanRequest(BaseModel):
    knowledge_text: str = ""
    document_id: str | None = None
    plan_duration_weeks: int = 4
    model: str = "deepseek-chat"


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

@router.post("/generate-plan")
async def generate_study_plan(
    req: GeneratePlanRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_optional_user),
):
    """AI generates a structured study plan from knowledge text or document."""
    user_id = get_user_id(current_user)
    await load_user_api_keys(user_id, db)
    json, Document, DocumentChunk = None, None, None
    knowledge_text = req.knowledge_text

    # If document_id provided, fetch chunks
    if req.document_id and not knowledge_text:
        from sqlalchemy import select
        from app.models import Document, DocumentChunk
        result = await db.execute(select(Document).where(Document.id == req.document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(404, "Document not found")
        result = await db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.doc_id == req.document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        chunks = result.scalars().all()
        knowledge_text = "\n\n".join(c.text_content for c in chunks)
        # Cap at token budget
        MAX_CHARS = 4000
        if len(knowledge_text) > MAX_CHARS:
            knowledge_text = knowledge_text[:MAX_CHARS] + "\n\n...(content truncated)"

    if not knowledge_text.strip():
        raise HTTPException(400, "Please provide knowledge_text or document_id")

    import json
    from app.core.assistant import assistant

    prompt = f"""你是一位学习规划专家。请根据以下知识点内容，制定一份{req.plan_duration_weeks}周的学习计划。

知识点内容：
{knowledge_text[:4000]}

请输出严格JSON格式的学习计划，包含计划名称、整体描述、按周拆分的学习目标（每个目标含标题和优先级high/medium/low）：

{{"name": "计划名称", "description": "整体描述", "goals": [{{"title": "目标标题", "priority": "high/medium/low", "week": 1}}]}}"""

    try:
        response = await assistant.chat(prompt, "tutor", None, req.model, user_id=user_id)
        data = json.loads(response)
    except Exception as e:
        raise HTTPException(500, f"AI规划生成失败: {str(e)}")

    # Create plan with goals
    plan = StudyPlan(
        user_id=user_id,
        name=data.get("name", "AI生成学习计划"),
        description=data.get("description", ""),
    )
    db.add(plan)
    await db.flush()

    goal_count = 0
    for i, g in enumerate(data.get("goals", [])):
        goal = StudyGoal(
            plan_id=plan.id,
            title=g.get("title", ""),
            description=g.get("description", g.get("title", "")),
            priority=g.get("priority", "medium"),
            order_index=i,
        )
        db.add(goal)
        goal_count += 1

    await db.commit()
    return {"plan_id": plan.id, "name": plan.name, "goal_count": goal_count}


@router.post("/plans")
async def create_plan(
    req: CreatePlanRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_optional_user),
):
    """Create a new study plan with optional goals."""
    user_id = get_user_id(current_user)
    plan = StudyPlan(
        user_id=user_id,
        name=req.name,
        description=req.description,
        target_end_date=datetime.fromisoformat(req.target_end_date) if req.target_end_date else None,
    )
    db.add(plan)
    await db.flush()

    for i, g in enumerate(req.goals or []):
        due = None
        if g.get("due_date"):
            try:
                due = datetime.fromisoformat(g["due_date"])
            except (ValueError, TypeError):
                pass  # Skip invalid dates
        goal = StudyGoal(
            plan_id=plan.id,
            title=g.get("title", ""),
            description=g.get("description", ""),
            priority=g.get("priority", "medium"),
            due_date=due,
            order_index=i,
        )
        db.add(goal)

    await db.commit()
    return {"plan_id": plan.id, "name": plan.name, "goal_count": len(req.goals or [])}


@router.get("/plans")
async def list_plans(
    limit: int = 1000,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List all study plans with progress."""
    result = await db.execute(
        select(StudyPlan).order_by(StudyPlan.updated_at.desc()).offset(offset).limit(limit)
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

    # Get max order_index (use MAX, not COUNT - deleted goals leave gaps)
    order_result = await db.execute(
        select(func.coalesce(func.max(StudyGoal.order_index), -1)).where(StudyGoal.plan_id == req.plan_id)
    )
    max_order = (order_result.scalar() or -1) + 1

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
async def create_reminder(
    req: CreateReminderRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_optional_user),
):
    """Create a study reminder."""
    user_id = get_user_id(current_user)
    reminder = StudyReminder(
        user_id=user_id,
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
async def get_due_reminders(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_optional_user),
):
    """Get reminders that are due now and unread."""
    user_id = get_user_id(current_user)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    result = await db.execute(
        select(StudyReminder)
        .where(StudyReminder.user_id == user_id, StudyReminder.remind_at <= now, StudyReminder.is_read == False)
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


class GenerateEnhancedPlanRequest(BaseModel):
    summary_id: str
    plan_type: str = "both"  # short / long / both
    daily_hours: float = 2.0
    start_date: str | None = None
    ebbinghaus_enabled: bool = True


@router.post("/generate-plan-enhanced")
async def generate_plan_enhanced(
    req: GenerateEnhancedPlanRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """Generate enhanced study plan with Ebbinghaus review nodes."""
    await load_user_api_keys(get_user_id(current_user), db)

    from app.core.agents.study_plan_agent import StudyPlanAgent

    config = {
        "study_plan": {
            "type": req.plan_type,
            "daily_hours": req.daily_hours,
        },
        "start_date": req.start_date,
    }

    # Get document_id from summary
    from app.models import KnowledgeSummary
    summary = await db.get(KnowledgeSummary, req.summary_id)
    if not summary:
        raise HTTPException(404, "Summary not found")

    agent = StudyPlanAgent()
    result = await agent.run(
        summary_id=req.summary_id,
        document_id=summary.document_id,
        config=config,
    )

    if result.status == "error":
        raise HTTPException(500, result.error or "Plan generation failed")

    return result


@router.get("/plans/{plan_id}/ebbinghaus")
async def get_plan_ebbinghaus(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get Ebbinghaus review nodes for a study plan."""
    from app.models import StudyPlan
    plan = await db.get(StudyPlan, plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found")

    return {
        "plan_id": plan.id,
        "ebbinghaus_nodes": plan.ebbinghaus_nodes,
    }
