"""TelecomChatbot theme - synthetic wireless/internet support (conversational).

This theme is conversational: it skips the medical clarifier and renders the
model's free-text ``reply`` verbatim.
"""

from backend.agents.themes.base import ThemeConfig, is_conversational, prompt_for

THEME = ThemeConfig(
    key="telecomchatbot",
    label="TelecomChatbot",
    conversational=is_conversational("telecomchatbot"),
    system_prompt=prompt_for("telecomchatbot"),
)
