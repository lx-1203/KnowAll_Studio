"""Agent orchestrator - parallel agent scheduling and coordination"""
import asyncio
import logging
from typing import AsyncGenerator
from app.core.agents.base import BaseAgent, AgentRegistry, AgentResult

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Coordinates parallel execution of multiple agents.

    Features:
    - Parallel execution via asyncio.TaskGroup
    - Independent error isolation (one agent failure doesn't affect others)
    - SSE progress streaming per agent
    - Coverage report generation after all agents complete
    """

    async def orchestrate(
        self,
        summary_id: str,
        document_id: str,
        agent_names: list[str] | None = None,
        config: dict | None = None,
    ) -> dict:
        """Run multiple agents in parallel.

        Args:
            summary_id: Knowledge summary ID
            document_id: Document ID
            agent_names: Specific agents to run (None = all registered)
            config: Shared config passed to all agents

        Returns:
            Dict with per-agent results and coverage report
        """
        if config is None:
            config = {}

        # Create agent instances
        agents = AgentRegistry.create_all(agent_names)

        if not agents:
            logger.warning("No agents to run")
            return {"results": {}, "coverage_report": None}

        # Filter by should_run()
        active_agents = [a for a in agents if a.should_run(document_id, **config)]
        skipped = [a for a in agents if a not in active_agents]

        logger.info(f"Orchestrating {len(active_agents)} agents: {[a.name for a in active_agents]}")

        # Run active agents in parallel
        async def run_agent(agent: BaseAgent) -> AgentResult:
            try:
                return await agent.run(summary_id=summary_id, document_id=document_id, **config)
            except Exception as e:
                logger.error(f"Agent '{agent.name}' failed: {e}", exc_info=True)
                return AgentResult(
                    agent=agent.name,
                    status="error",
                    error=str(e),
                )

        tasks = [run_agent(a) for a in active_agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build results dict
        agent_results: dict[str, AgentResult] = {}
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                agent_results[active_agents[i].name] = AgentResult(
                    agent=active_agents[i].name,
                    status="error",
                    error=str(result),
                )
            else:
                agent_results[active_agents[i].name] = result

        # Add skipped agents
        for agent in skipped:
            agent_results[agent.name] = AgentResult(
                agent=agent.name,
                status="skipped",
            )

        # Generate coverage report
        coverage_report = await self._generate_coverage_report(summary_id)

        return {
            "results": {name: r for name, r in agent_results.items()},
            "coverage_report": coverage_report,
        }

    async def orchestrate_sse(
        self,
        summary_id: str,
        document_id: str,
        agent_names: list[str] | None = None,
        config: dict | None = None,
    ) -> AsyncGenerator[str, None]:
        """Run orchestration with SSE streaming progress events.

        Yields SSE-formatted event strings.
        """
        if config is None:
            config = {}

        agents = AgentRegistry.create_all(agent_names)
        active_agents = [a for a in agents if a.should_run(document_id, **config)]

        # Emit agent_start events
        for agent in active_agents:
            yield f"event: agent_start\ndata: {{\"agent\":\"{agent.name}\",\"status\":\"started\"}}\n\n"

        # Run all agents, collecting results as they complete
        task_results = {}
        queue = asyncio.Queue()

        async def run_and_report(agent: BaseAgent):
            try:
                result = await agent.run(summary_id=summary_id, document_id=document_id, **config)
                await queue.put(("complete", agent.name, result))
            except Exception as e:
                await queue.put(("error", agent.name, str(e)))

        bg_tasks = [asyncio.create_task(run_and_report(a)) for a in active_agents]

        completed = 0
        total = len(active_agents)

        while completed < total:
            event_type, agent_name, data = await queue.get()
            completed += 1

            if event_type == "complete":
                yield f"event: agent_complete\ndata: {{\"agent\":\"{agent_name}\",\"result\":{data.result}}}\n\n"
                task_results[agent_name] = data
            elif event_type == "error":
                yield f"event: agent_error\ndata: {{\"agent\":\"{agent_name}\",\"error\":\"{data}\"}}\n\n"
                task_results[agent_name] = AgentResult(agent=agent_name, status="error", error=data)

        await asyncio.gather(*bg_tasks, return_exceptions=True)

        # Coverage report
        coverage = await self._generate_coverage_report(summary_id)

        yield f"event: orchestrate_complete\ndata: {{\"results\":{task_results},\"coverage_report\":{coverage}}}\n\n"

    async def orchestrate_from_pipeline(
        self,
        summary_id: str,
        document_id: str,
        agent_names: list[str] | None = None,
        config: dict | None = None,
    ) -> dict:
        """Run orchestration from within the Pipeline context.

        This is a pipeline-friendly wrapper around orchestrate() that:
        - Always returns a dict (never raises)
        - Handles the case where summary_id might not have nodes yet
        - Returns results in a format compatible with PipelineState.result

        Args:
            summary_id: Knowledge summary ID (may be newly created)
            document_id: Document ID
            agent_names: Specific agents to run (None = all registered)
            config: Shared config passed to all agents

        Returns:
            Dict with 'results' and 'coverage_report' keys
        """
        try:
            return await self.orchestrate(
                summary_id=summary_id,
                document_id=document_id,
                agent_names=agent_names,
                config=config,
            )
        except Exception as e:
            logger.error(f"orchestrate_from_pipeline failed: {e}", exc_info=True)
            return {
                "results": {},
                "coverage_report": None,
                "error": str(e),
            }

    async def _generate_coverage_report(self, summary_id: str) -> dict | None:
        """Generate coverage report after agent completion."""
        try:
            from app.core.memory.coverage import coverage_engine
            return await coverage_engine.calculate(summary_id)
        except Exception as e:
            logger.warning(f"Failed to generate coverage report: {e}")
            return None


orchestrator = AgentOrchestrator()
