"""Game content generator (M5)"""
import json
from app.core.api_scheduler import api_client, TaskType


class GameContentGenerator:
    """Generate game level content via API."""

    async def generate_levels(
        self,
        knowledge_text: str,
        game_type: str = "matching",
        count: int = 5,
        model: str = "deepseek-chat",
    ) -> list[dict]:
        """Generate game levels from knowledge text."""
        from app.prompts import prompt_engine

        template_map = {
            "matching": ("game", "matching"),
            "cloze_ladder": ("game", "cloze_ladder"),
        }

        cat, name = template_map.get(game_type, ("game", "matching"))

        messages = prompt_engine.render(
            cat, name,
            knowledge_points=knowledge_text,
            count=count,
        )

        result = await api_client.generate(
            task_type=TaskType.GAME_GEN,
            messages=messages,
            prompt_template_id=f"{cat}.{name}",
            generation_content=knowledge_text + game_type + str(count),
        )
        return self._parse_levels(result.content, game_type)

    def _parse_levels(self, content: str, game_type: str) -> list[dict]:
        try:
            data = json.loads(content)
            if game_type == "matching":
                return data.get("pairs", data if isinstance(data, list) else [])
            elif game_type == "cloze_ladder":
                return data.get("levels", data if isinstance(data, list) else [])
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []


game_generator = GameContentGenerator()
