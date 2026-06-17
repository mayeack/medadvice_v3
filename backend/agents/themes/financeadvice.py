"""FinanceAdvice theme - personal finance literacy (not CFP advice)."""

from backend.agents.themes.base import ThemeConfig, is_conversational, prompt_for

THEME = ThemeConfig(
    key="financeadvice",
    label="FinanceAdvice",
    conversational=is_conversational("financeadvice"),
    system_prompt=prompt_for("financeadvice"),
)
