"""Interactive quiz API routes"""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.database import get_db
from app.models import QuestionBank, AnswerRecord, KnowledgeCoverage
from app.core.auth import get_optional_user, get_user_id, load_user_api_keys
from app.core.quiz import exam_engine

router = APIRouter(prefix="/api/v1/quiz/interactive", tags=["interactive_quiz"])

# In-memory session store (in production, use Redis)
_sessions: dict[str, dict] = {}


class StartQuizRequest(BaseModel):
    summary_id: str
    count: int = 10
    mode: str = "sequential"  # sequential / random
    question_types: list[str] | None = None


class SubmitAnswerRequest(BaseModel):
    question_id: str
    user_answer: str
    time_spent_ms: int = 0
    knowledge_point_id: str | None = None


@router.get("/start")
async def start_interactive_quiz(
    summary_id: str,
    count: int = 10,
    mode: str = "sequential",
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """Start an interactive quiz session. Returns first batch of questions."""
    await load_user_api_keys(get_user_id(current_user), db)

    # Find questions linked to this summary's knowledge points
    from app.models import KnowledgePointNode

    # Get coverage entries for this summary
    kp_stmt = select(KnowledgePointNode.id).where(KnowledgePointNode.summary_id == summary_id)
    kp_result = await db.execute(kp_stmt)
    kp_ids = [row[0] for row in kp_result.fetchall()]

    if not kp_ids:
        # Fall back to loading all questions
        q_stmt = select(QuestionBank).limit(count)
    else:
        cov_stmt = select(KnowledgeCoverage.resource_id).where(
            KnowledgeCoverage.knowledge_point_id.in_(kp_ids),
            KnowledgeCoverage.resource_type == "question",
        )
        cov_result = await db.execute(cov_stmt)
        q_ids = [row[0] for row in cov_result.fetchall()]

        if not q_ids:
            return {"session_id": "", "questions": [], "total": 0, "message": "No questions found for this summary. Run Agent orchestration first."}

        q_stmt = select(QuestionBank).where(QuestionBank.id.in_(q_ids)).limit(count)

    q_result = await db.execute(q_stmt)
    questions = q_result.scalars().all()

    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "questions": [
            {
                "id": q.id,
                "question_type": q.question_type,
                "difficulty": q.difficulty,
                "tags": q.tags,
                "question_text": q.question_text,
                "options": q.options,
                "answer": q.correct_answer,
                "analysis": q.analysis,
            }
            for q in questions
        ],
        "answers": {},
        "current_index": 0,
    }

    return {
        "session_id": session_id,
        "questions": _sessions[session_id]["questions"],
        "total": len(questions),
    }


@router.post("/submit")
async def submit_interactive_answer(
    req: SubmitAnswerRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """Submit an answer and get immediate feedback."""
    user_id = get_user_id(current_user)

    # Look up the question
    question = await db.get(QuestionBank, req.question_id)
    if not question:
        raise HTTPException(404, "Question not found")

    # Grade the answer
    result = exam_engine.grade(
        paper={"questions": [{
            "id": question.id,
            "question_type": question.question_type,
            "answer": question.correct_answer,
            "analysis": question.analysis,
        }]},
        user_answers={question.id: req.user_answer},
        time_spent_ms={question.id: req.time_spent_ms},
        knowledge_point_ids={question.id: req.knowledge_point_id or ""},
    )

    detail = result["details"][0] if result["details"] else {}

    # Save answer record
    record = AnswerRecord(
        user_id=user_id,
        question_id=req.question_id,
        user_answer=req.user_answer,
        is_correct=detail.get("is_correct", False),
        time_spent_ms=req.time_spent_ms,
        attempt_count=1,
        knowledge_point_ids=[req.knowledge_point_id] if req.knowledge_point_id else [],
    )
    db.add(record)
    await db.commit()

    return {
        "is_correct": detail.get("is_correct", False),
        "correct_answer": detail.get("correct_answer", ""),
        "analysis": detail.get("analysis", ""),
        "stats": {},  # Session stats computed client-side
    }


@router.get("/session/{session_id}/stats")
async def get_session_stats(session_id: str):
    """Get stats for an interactive quiz session."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found or expired")

    answers = session.get("answers", {})
    total = len(answers)
    correct = sum(1 for a in answers.values() if a.get("is_correct"))

    return {
        "total_answered": total,
        "correct": correct,
        "accuracy": round(correct / max(1, total), 4),
        "time_spent_total_ms": sum(a.get("time_spent_ms", 0) for a in answers.values()),
        "questions_detail": list(answers.values()),
    }
