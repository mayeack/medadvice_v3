"""MedAdvice theme - general medical guidance (default)."""

from backend.agents.themes.base import ThemeConfig, is_conversational, prompt_for

THEME = ThemeConfig(
    key="medadvice",
    label="MedAdvice",
    conversational=is_conversational("medadvice"),
    system_prompt=prompt_for("medadvice"),
)
