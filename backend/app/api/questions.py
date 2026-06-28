"""Quiz generation, exam papers, and grading API routes (v2 with Bloom + Review)"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.models import DocumentChunk, QuestionBank, ExamPaper, AnswerRecord, ErrorLog
from app.core.quiz import quiz_generator, exam_engine, QuizGenerationConfig
from app.core.auth import get_optional_user, get_user_id, load_user_api_keys

router = APIRouter(prefix="/api/v1/quiz", tags=["quiz"])


class GenerateQuestionsRequest(BaseModel):
    document_id: str
    chunk_ids: list[str] | None = None
    question_type: str = "single_choice"
    count: int = 10
    difficulty: str = "medium"                    # legacy: easy/medium/hard
    difficulty_score: float = 0.5                 # NEW: continuous 0.0-1.0
    cognitive_level: str = "L2_understand"        # NEW: Bloom level
    enable_review: bool = True                    # NEW: LLM-as-Judge review
    preview: bool = True                          # NEW: if True, return questions without auto-saving
    model: str = "deepseek-chat"


class SaveToBankRequest(BaseModel):
    """Batch save selected questions to the question bank."""
    questions: list[dict]
    source_chunk_id: str | None = None


class CreateExamRequest(BaseModel):
    title: str = "试卷"
    question_ids: list[str] | None = None
    config: dict = {}


class SubmitExamRequest(BaseModel):
    paper_id: str
    answers: dict[str, str]
    enable_semantic: bool = True  # NEW: use LLM semantic grading for open-ended questions
    model: str = "deepseek-chat"  # model for semantic grading


@router.post("/generate")
async def generate_questions(
    req: GenerateQuestionsRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_optional_user),
):
    """Generate quiz questions from document chunks (v2 with Bloom + Review)."""
    await load_user_api_keys(get_user_id(current_user), db)
    from sqlalchemy import select

    # Get chunks
    if req.chunk_ids:
        result = await db.execute(
            select(DocumentChunk).where(DocumentChunk.id.in_(req.chunk_ids))
        )
    else:
        result = await db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.doc_id == req.document_id)
            .order_by(DocumentChunk.chunk_index)
        )
    chunks = result.scalars().all()
    if not chunks:
        raise HTTPException(404, "No chunks found")

    # Combine chunk texts for generation (cap at token limit)
    MAX_CHARS = 8000
    knowledge_text = "\n\n".join(c.text_content for c in chunks)
    if len(knowledge_text) > MAX_CHARS:
        knowledge_text = knowledge_text[:MAX_CHARS] + "\n\n...(content truncated)"

    config = QuizGenerationConfig(
        question_type=req.question_type,
        count=req.count,
        difficulty=req.difficulty,
        difficulty_score=req.difficulty_score,
        cognitive_level=req.cognitive_level,
        enable_review=req.enable_review,
    )

    try:
        questions = await quiz_generator.generate(knowledge_text, config, req.model)
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {str(e)}")

    # Build response question dicts (with temporary IDs for preview)
    preview_questions = []
    for i, q in enumerate(questions):
        preview_questions.append({
            "_idx": i,
            "_selected": True,  # default checked
            "question_type": q.get("type", q.get("question_type", req.question_type)),
            "difficulty": q.get("difficulty", req.difficulty),
            "difficulty_score": q.get("difficulty_score", req.difficulty_score),
            "cognitive_level": q.get("cognitive_level", req.cognitive_level),
            "tags": q.get("tags", []),
            "question_text": q.get("question_text", ""),
            "options": q.get("options", []),
            "answer": str(q.get("answer", q.get("correct_answer", ""))),
            "analysis": q.get("analysis", ""),
            "review_scores": q.get("review_scores", {}),
            "review_total": q.get("review_total"),
            "reviewed": q.get("reviewed", False),
            "review_decision": q.get("review_decision", ""),
        })

    if req.preview:
        # Preview mode: return questions without saving
        return {
            "mode": "preview",
            "generated_count": len(preview_questions),
            "reviewed_count": sum(1 for q in questions if q.get("reviewed")),
            "questions": preview_questions,
        }

    # Auto-save mode (backward compatible)
    saved_questions = []
    for q in questions:
        db_q = QuestionBank(
            question_type=q.get("type", q.get("question_type", req.question_type)),
            difficulty=q.get("difficulty", req.difficulty),
            difficulty_score=q.get("difficulty_score", req.difficulty_score),
            cognitive_level=q.get("cognitive_level", req.cognitive_level),
            tags=q.get("tags", []),
            question_text=q.get("question_text", ""),
            options=q.get("options", []),
            correct_answer=str(q.get("answer", q.get("correct_answer", ""))),
            analysis=q.get("analysis", ""),
            review_scores=q.get("review_scores", {}),
            review_total=q.get("review_total"),
            source_chunk_id=chunks[0].id if len(chunks) == 1 else None,
        )
        db.add(db_q)
        saved_questions.append(db_q)

    await db.commit()

    return {
        "mode": "saved",
        "generated_count": len(saved_questions),
        "reviewed_count": sum(1 for q in questions if q.get("reviewed")),
        "questions": [
            {
                "id": q.id,
                "question_type": q.question_type,
                "difficulty": q.difficulty,
                "difficulty_score": q.difficulty_score,
                "cognitive_level": q.cognitive_level,
                "tags": q.tags,
                "question_text": q.question_text,
                "options": q.options,
                "answer": q.correct_answer,
                "analysis": q.analysis,
                "review_scores": q.review_scores,
                "review_total": q.review_total,
            }
            for q in saved_questions
        ],
    }


@router.post("/exam/create")
async def create_exam(req: CreateExamRequest, db: AsyncSession = Depends(get_db)):
    """Create an exam paper from existing questions or auto-generated."""
    from sqlalchemy import select

    if req.question_ids:
        result = await db.execute(
            select(QuestionBank).where(QuestionBank.id.in_(req.question_ids))
        )
        questions = result.scalars().all()
        question_dicts = [
            {
                "id": q.id,
                "question_type": q.question_type,
                "difficulty": q.difficulty,
                "difficulty_score": q.difficulty_score,
                "cognitive_level": q.cognitive_level,
                "tags": q.tags,
                "question_text": q.question_text,
                "options": q.options,
                "answer": q.correct_answer,
                "analysis": q.analysis,
            }
            for q in questions
        ]
        paper_data = {"title": req.title, "questions": question_dicts, "question_ids": [q["id"] for q in question_dicts]}
    else:
        result = await db.execute(select(QuestionBank).limit(200))
        all_questions = result.scalars().all()
        question_dicts = [
            {
                "id": q.id,
                "question_type": q.question_type,
                "difficulty": q.difficulty,
                "difficulty_score": q.difficulty_score,
                "cognitive_level": q.cognitive_level,
                "tags": q.tags,
                "question_text": q.question_text,
                "options": q.options,
                "answer": q.correct_answer,
                "analysis": q.analysis,
            }
            for q in all_questions
        ]
        paper_data = exam_engine.create_paper(question_dicts, req.config | {"title": req.title})

    paper = ExamPaper(
        title=paper_data["title"],
        question_ids=paper_data["question_ids"],
        config=req.config,
    )
    db.add(paper)
    await db.commit()
    await db.refresh(paper)

    return {
        "paper_id": paper.id,
        "title": paper.title,
        "question_count": len(paper_data["question_ids"]),
        "total_score": len(paper_data["question_ids"]) * 5,
        "questions": paper_data.get("questions", question_dicts),
    }


@router.post("/exam/submit")
async def submit_exam(
    req: SubmitExamRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_optional_user),
):
    """Submit exam answers, get graded results with cognitive analysis."""
    from sqlalchemy import select

    user_id = get_user_id(current_user)

    result = await db.execute(select(ExamPaper).where(ExamPaper.id == req.paper_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(404, "Paper not found")

    result = await db.execute(
        select(QuestionBank).where(QuestionBank.id.in_(paper.question_ids))
    )
    questions = result.scalars().all()

    question_dicts = [
        {
            "id": q.id,
            "question_type": q.question_type,
            "question_text": q.question_text,
            "options": q.options,
            "answer": q.correct_answer,
            "analysis": q.analysis,
            "cognitive_level": q.cognitive_level,
            "difficulty_score": q.difficulty_score,
        }
        for q in questions
    ]

    paper_with_qs = {"questions": question_dicts}
    results = await exam_engine.grade_enhanced(
        paper_with_qs, req.answers,
        enable_semantic=req.enable_semantic,
        model=req.model,
    )

    # Save answer records
    for detail in results["details"]:
        record = AnswerRecord(
            user_id=user_id,
            question_id=detail["question_id"],
            paper_id=req.paper_id,
            user_answer=detail["user_answer"],
            is_correct=detail["is_correct"],
        )
        db.add(record)

        if not detail["is_correct"]:
            from sqlalchemy import select as sel
            existing = await db.execute(
                sel(ErrorLog).where(
                    ErrorLog.question_id == detail["question_id"],
                    ErrorLog.user_id == user_id,
                )
            )
            error = existing.scalar_one_or_none()
            if error:
                error.error_count += 1
                error.last_error_at = datetime.now(timezone.utc).replace(tzinfo=None)
            else:
                db.add(ErrorLog(
                    user_id=user_id,
                    question_id=detail["question_id"],
                ))

    await db.commit()

    # Add cognitive breakdown to results
    cognitive_breakdown = {}
    for detail in results["details"]:
        # Find the matching question to get cognitive_level
        q_dict = next((q for q in question_dicts if q["id"] == detail["question_id"]), None)
        cl = q_dict.get("cognitive_level", "unknown") if q_dict else "unknown"
        if cl not in cognitive_breakdown:
            cognitive_breakdown[cl] = {"total": 0, "correct": 0}
        cognitive_breakdown[cl]["total"] += 1
        if detail["is_correct"]:
            cognitive_breakdown[cl]["correct"] += 1

    results["cognitive_breakdown"] = {
        cl: {
            "total": stats["total"],
            "correct": stats["correct"],
            "accuracy": round(stats["correct"] / max(1, stats["total"]) * 100, 1),
        }
        for cl, stats in cognitive_breakdown.items()
    }

    return results


@router.get("/errors")
async def get_error_questions(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_optional_user),
):
    """Get all error questions for the current user."""
    from sqlalchemy import select

    user_id = get_user_id(current_user)
    result = await db.execute(
        select(ErrorLog, QuestionBank)
        .join(QuestionBank, ErrorLog.question_id == QuestionBank.id)
        .where(ErrorLog.user_id == user_id)
        .order_by(ErrorLog.last_error_at.desc())
    )
    rows = result.all()
    return [
        {
            "error_id": err.id,
            "error_count": err.error_count,
            "last_error_at": err.last_error_at.isoformat() if err.last_error_at else None,
            "question": {
                "id": q.id,
                "question_type": q.question_type,
                "difficulty": q.difficulty,
                "difficulty_score": q.difficulty_score,
                "cognitive_level": q.cognitive_level,
                "question_text": q.question_text,
                "options": q.options,
                "answer": q.correct_answer,
                "analysis": q.analysis,
            },
        }
        for err, q in rows
    ]


@router.post("/errors/{error_id}/variants")
async def generate_error_variants(
    error_id: str, count: int = 3,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_optional_user),
):
    """Generate variant questions for a specific error question."""
    await load_user_api_keys(get_user_id(current_user), db)
    from sqlalchemy import select

    result = await db.execute(
        select(ErrorLog, QuestionBank)
        .join(QuestionBank, ErrorLog.question_id == QuestionBank.id)
        .where(ErrorLog.id == error_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(404, "Error entry not found")

    error, question = row

    question_dict = {
        "question_type": question.question_type,
        "question_text": question.question_text,
        "correct_answer": question.correct_answer,
        "analysis": question.analysis,
        "difficulty": question.difficulty,
        "difficulty_score": question.difficulty_score,
        "cognitive_level": question.cognitive_level,
    }

    try:
        variants = await quiz_generator.generate_variants(question_dict, count)
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {str(e)}")

    saved = []
    for v in variants:
        db_q = QuestionBank(
            question_type=question.question_type,
            difficulty=question.difficulty,
            difficulty_score=question.difficulty_score,
            cognitive_level=question.cognitive_level,
            tags=question.tags,
            question_text=v.get("question_text", ""),
            options=v.get("options", []),
            correct_answer=str(v.get("answer", v.get("correct_answer", ""))),
            analysis=v.get("analysis", ""),
            parent_question_id=question.id,
        )
        db.add(db_q)
        saved.append(db_q)

    error.variant_generated = True
    await db.commit()

    return {
        "variant_count": len(saved),
        "questions": [
            {
                "id": q.id,
                "question_type": q.question_type,
                "difficulty_score": q.difficulty_score,
                "cognitive_level": q.cognitive_level,
                "question_text": q.question_text,
                "options": q.options,
                "answer": q.correct_answer,
            }
            for q in saved
        ],
    }


@router.get("/questions")
async def list_questions(
    question_type: str | None = None,
    difficulty: str | None = None,
    cognitive_level: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List questions with optional filters (v2 with cognitive_level)."""
    from sqlalchemy import select

    query = select(QuestionBank)
    if question_type:
        query = query.where(QuestionBank.question_type == question_type)
    if difficulty:
        query = query.where(QuestionBank.difficulty == difficulty)
    if cognitive_level:
        query = query.where(QuestionBank.cognitive_level == cognitive_level)
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    questions = result.scalars().all()
    return [
        {
            "id": q.id,
            "question_type": q.question_type,
            "difficulty": q.difficulty,
            "difficulty_score": q.difficulty_score,
            "cognitive_level": q.cognitive_level,
            "tags": q.tags,
            "question_text": q.question_text[:100] + "..." if len(q.question_text or "") > 100 else q.question_text,
        }
        for q in questions
    ]
