"""LegalAdvice theme - general legal information (not attorney counsel)."""

from backend.agents.themes.base import ThemeConfig, is_conversational, prompt_for

THEME = ThemeConfig(
    key="legaladvice",
    label="LegalAdvice",
    conversational=is_conversational("legaladvice"),
    system_prompt=prompt_for("legaladvice"),
)
