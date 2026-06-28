"""Agent orchestration API routes"""
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.core.auth import get_optional_user, get_user_id, load_user_api_keys
from app.core.agents.orchestrator import orchestrator

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


class OrchestrateRequest(BaseModel):
    summary_id: str
    document_id: str
    agents: list[str] | None = None
    language_type: str | None = None
    config: dict | None = None


@router.post("/orchestrate")
async def orchestrate_agents(
    req: OrchestrateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """Run multiple agents in parallel. Returns complete results."""
    await load_user_api_keys(get_user_id(current_user), db)

    result = await orchestrator.orchestrate(
        summary_id=req.summary_id,
        document_id=req.document_id,
        agent_names=req.agents,
        config={
            **(req.config or {}),
            "language_type": req.language_type,
        },
    )
    return result


@router.post("/orchestrate/stream")
async def orchestrate_agents_stream(
    req: OrchestrateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """Run multiple agents with SSE streaming progress."""
    await load_user_api_keys(get_user_id(current_user), db)

    async def event_stream():
        async for event in orchestrator.orchestrate_sse(
            summary_id=req.summary_id,
            document_id=req.document_id,
            agent_names=req.agents,
            config={
                **(req.config or {}),
                "language_type": req.language_type,
            },
        ):
            yield event

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/list")
async def list_agents():
    """List all registered agents and their descriptions."""
    from app.core.agents.base import AgentRegistry

    agents_list = []
    for name in AgentRegistry.list_all():
        agent_cls = AgentRegistry.get(name)
        agents_list.append({
            "name": name,
            "description": agent_cls.description if agent_cls else "",
        })
    return {"agents": agents_list}
