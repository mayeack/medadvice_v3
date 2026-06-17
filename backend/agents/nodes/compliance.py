"""Compliance / formatting agent node.

Assembles the complete display text exactly as the frontend renders it (severity
badge + escalation warning + message body). This is the ``response_text`` that
the governance node logs to Splunk.
"""

from __future__ import annotations

from typing import Any, Dict

from backend.telemetry import otel


def compliance_node(state: Dict[str, Any]) -> Dict[str, Any]:
    with otel.agent_span("compliance_agent", theme=state.get("theme")):
        display_text_parts = []
        severity = state.get("severity")
        if severity:
            display_text_parts.append(severity.value)
        if state.get("should_escalate"):
            display_text_parts.append("\u26a0\ufe0f ESCALATED FOR REVIEW")
        display_text_parts.append(state["final_message"])
        complete_display_text = "\n".join(display_text_parts)

    return {"complete_display_text": complete_display_text}
