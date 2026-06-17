"""Shared singletons and helpers used by the specialist nodes.

``content_engine`` reuses ``RecommendationEngine`` purely as a content/patterns
library (PII / toxic / hallucination injection, formatting, severity
normalization, AI Defense block handlers). Its ``__init__`` is bypassed so it
does not require an AI client / API key - the agentic graph drives the LLM via
``backend.agents.llm`` instead. This keeps a single source of truth for the
large pattern dictionaries with zero duplication.
"""

from __future__ import annotations

from typing import Any, Dict, List

from backend.services.clarifying_questions import ClarifyingQuestionsService
from backend.services.escalation_rules import EscalationRules
from backend.services.recommendation_engine import RecommendationEngine


class _ContentEngine(RecommendationEngine):
    """RecommendationEngine without the AI-client bootstrap.

    Exposes the pure content helpers and class-level pattern dictionaries while
    avoiding the network/credential setup the orchestrator no longer needs.
    """

    def __init__(self):  # noqa: D401 - intentionally skip base __init__
        # Deliberately do not call super().__init__(): we only use the pure
        # content/formatting helpers and class attributes, not self.ai_client.
        pass


# Shared, stateless services (no API keys required).
content_engine = _ContentEngine()
escalation_rules = EscalationRules()
clarifying_service = ClarifyingQuestionsService()


def build_llm_messages(conversation_history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build role/content message dicts for the LLM from conversation history.

    Mirrors the legacy ``_generate_recommendation`` message assembly: keep only
    user/assistant turns and coerce enum roles to their string value so the
    governance ``input_messages`` payload stays a list of ``{role, content}``
    string dicts (per the Splunk contract).
    """
    messages: List[Dict[str, Any]] = []
    for msg in conversation_history or []:
        role = msg.get("role")
        role = role.value if hasattr(role, "value") else role
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": msg.get("content", "")})
    return messages
