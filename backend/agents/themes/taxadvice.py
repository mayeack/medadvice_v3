"""TaxAdvice theme - general tax information (not CPA advice)."""

from backend.agents.themes.base import ThemeConfig, is_conversational, prompt_for

THEME = ThemeConfig(
    key="taxadvice",
    label="TaxAdvice",
    conversational=is_conversational("taxadvice"),
    system_prompt=prompt_for("taxadvice"),
)
