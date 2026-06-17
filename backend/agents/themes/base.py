"""Per-theme configuration primitives.

Each Application Theme becomes its own agent pipeline (a decomposed subgraph)
selected by the supervisor/router. A :class:`ThemeConfig` carries everything the
graph needs to specialize the shared specialist nodes for a domain.

Prompt text and the conversational-theme set are sourced from
``RecommendationEngine`` so there is a single source of truth (no duplicated
prompt strings). The injection / formatting pattern dictionaries also remain on
the engine and are reused by the injection node.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.services.recommendation_engine import RecommendationEngine


@dataclass(frozen=True)
class ThemeConfig:
    """Configuration for one Application Theme's agent pipeline."""

    key: str
    label: str
    conversational: bool
    system_prompt: str

    @property
    def agent_name(self) -> str:
        """Name used for the per-theme domain agent's OTel AgentInvocation."""
        return f"{self.key}_domain_agent"

    @property
    def subgraph_name(self) -> str:
        return f"{self.key}_subgraph"


def prompt_for(theme_key: str) -> str:
    """Return the system prompt for a theme (defaults to medadvice)."""
    prompts = RecommendationEngine.THEME_PROMPTS
    return prompts.get(theme_key, prompts["medadvice"])


def is_conversational(theme_key: str) -> bool:
    """Whether a theme is conversational (skips the medical clarifier)."""
    return theme_key in RecommendationEngine.CONVERSATIONAL_THEMES
