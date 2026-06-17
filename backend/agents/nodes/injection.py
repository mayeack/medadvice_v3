"""Test-injection agent node (PII / toxic / hallucination).

Governance-testing specialist that optionally weaves synthetic PII/PHI, toxic
content, and hallucinations into the response so the downstream guardrails and
Splunk evaluations have signal to detect. The actual content patterns live on
``content_engine`` (single source of truth); this node only drives the toggle /
rate logic, identical to the legacy pipeline:

    force flag True  -> always inject (100%)
    force flag False -> random injection at the configured rate
    force flag None  -> random injection at the configured rate (default)
"""

from __future__ import annotations

import random
from typing import Any, Dict

from backend.agents.nodes.shared import content_engine
from backend.config import settings
from backend.telemetry import otel


def _should_inject(force_flag: Any, rate: float) -> bool:
    if force_flag is True:
        return True
    # Both False and None fall back to random injection at the configured rate.
    return random.random() < rate


def injection_node(state: Dict[str, Any]) -> Dict[str, Any]:
    final_message = state["final_message"]
    recommendation = state.get("recommendation", {})
    theme = state["theme"]
    conversation_history = state.get("conversation_history", [])
    severity_raw = recommendation.get("severity", "MEDIUM")

    updates: Dict[str, Any] = {
        "pii_injected": False,
        "pii_types": [],
        "toxic_injected": False,
        "toxic_types": [],
        "hallucination_injected": False,
        "hallucination_types": [],
    }

    with otel.agent_span("injection_agent", theme=theme):
        if _should_inject(
            state.get("force_pii_injection"), settings.pii_injection_rate
        ):
            final_message, pii_types = content_engine._integrate_realistic_pii(
                final_message, severity_raw, conversation_history, theme
            )
            updates["pii_injected"] = True
            updates["pii_types"] = pii_types

        if _should_inject(
            state.get("force_toxic_injection"), settings.toxic_injection_rate
        ):
            final_message, toxic_types = content_engine._inject_toxic_content(
                final_message, severity_raw, conversation_history, theme
            )
            updates["toxic_injected"] = True
            updates["toxic_types"] = toxic_types

        if _should_inject(
            state.get("force_hallucination_injection"),
            settings.hallucination_injection_rate,
        ):
            (
                final_message,
                hallucination_types,
            ) = content_engine._inject_hallucination_content(
                final_message, severity_raw, conversation_history, theme
            )
            updates["hallucination_injected"] = True
            updates["hallucination_types"] = hallucination_types

    updates["final_message"] = final_message
    return updates
