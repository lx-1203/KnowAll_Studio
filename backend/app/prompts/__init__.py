"""Prompt template engine - loads YAML templates and renders with context"""
import yaml
from pathlib import Path
from typing import Any

PROMPT_DIR = Path(__file__).parent


class PromptTemplate:
    """A single prompt template with system and user messages."""

    def __init__(self, template_id: str, data: dict):
        self.id = template_id
        self.system = data.get("system", "")
        self.user_template = data.get("user_template", "")
        self.output_schema = data.get("output_schema", {})
        self.description = data.get("description", "")

    def render(self, **kwargs) -> list[dict[str, str]]:
        """Render the prompt into chat messages format."""
        messages = []
        if self.system:
            formatted_system = self.system.format(**kwargs)
            messages.append({"role": "system", "content": formatted_system.strip()})
        user_content = self.user_template.format(**kwargs)
        messages.append({"role": "user", "content": user_content.strip()})
        return messages

    def render_system_only(self, **kwargs) -> str:
        """Render just the system prompt with variables."""
        return self.system.format(**kwargs)


class PromptEngine:
    """Loads and manages all prompt templates."""

    def __init__(self):
        self._templates: dict[str, dict[str, PromptTemplate]] = {}
        self._load_all()

    def _load_all(self):
        """Load all YAML prompt files."""
        for yaml_file in PROMPT_DIR.glob("*.yaml"):
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict):
                category = yaml_file.stem
                self._templates[category] = {}
                for name, template_data in data.items():
                    if isinstance(template_data, dict):
                        template_id = f"{category}.{name}"
                        self._templates[category][name] = PromptTemplate(template_id, template_data)

    def get(self, category: str, name: str) -> PromptTemplate:
        """Get a template by category and name. e.g. ('knowledge_tree', 'standard')"""
        if category not in self._templates:
            raise ValueError(f"Unknown prompt category: {category}. Available: {list(self._templates.keys())}")
        if name not in self._templates[category]:
            raise ValueError(f"Unknown template '{name}' in '{category}'. Available: {list(self._templates[category].keys())}")
        return self._templates[category][name]

    def render(self, category: str, name: str, **kwargs) -> list[dict[str, str]]:
        """Shortcut to get and render a template."""
        return self.get(category, name).render(**kwargs)

    def list_templates(self) -> dict[str, list[str]]:
        """List all available templates."""
        return {cat: list(templates.keys()) for cat, templates in self._templates.items()}


prompt_engine = PromptEngine()
