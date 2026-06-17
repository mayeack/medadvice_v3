"""BenefitsAdvice theme - employee benefits / HR plan guidance."""

from backend.agents.themes.base import ThemeConfig, is_conversational, prompt_for

THEME = ThemeConfig(
    key="benefitsadvice",
    label="BenefitsAdvice",
    conversational=is_conversational("benefitsadvice"),
    system_prompt=prompt_for("benefitsadvice"),
)
