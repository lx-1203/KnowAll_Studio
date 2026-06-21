"""Pipeline API - one-click full chain automation"""
import json
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from app.core.pipeline import pipeline, PipelineStage

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])


class PipelineRequest(BaseModel):
    document_id: str
    model: str = "deepseek-chat"
    question_count: int = Field(default=15, ge=5, le=50)
    question_type: str = "single_choice"
    difficulty: str = "medium"
    card_count: int = Field(default=20, ge=5, le=100)
    card_type: str = "qa"


@router.post("/run")
async def run_pipeline(req: PipelineRequest):
    """Run the full pipeline and return final result (non-streaming)."""
    final_state = None
    async for state in pipeline.run_full_chain(
        document_id=req.document_id,
        model=req.model,
        question_count=req.question_count,
        question_type=req.question_type,
        difficulty=req.difficulty,
        card_count=req.card_count,
        card_type=req.card_type,
    ):
        final_state = state

    if not final_state or final_state.stage == PipelineStage.ERROR:
        raise HTTPException(500, final_state.error if final_state else "Unknown error")

    return {
        "status": "completed",
        **final_state.result,
    }


@router.post("/run/stream")
async def run_pipeline_stream(req: PipelineRequest):
    """Run pipeline with SSE progress streaming."""
    async def event_stream():
        async for state in pipeline.run_full_chain(
            document_id=req.document_id,
            model=req.model,
            question_count=req.question_count,
            question_type=req.question_type,
            difficulty=req.difficulty,
            card_count=req.card_count,
            card_type=req.card_type,
        ):
            data = {
                "stage": state.stage.value,
                "progress": state.progress_pct,
                "message": state.message,
                "error": state.error,
                "result": state.result,
            }
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
