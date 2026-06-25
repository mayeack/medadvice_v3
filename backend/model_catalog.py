"""Discover the models AVAILABLE from each configured AI provider.

Queried at app startup (and on demand from the Settings UI) so the provider's
"Model" field can be a dropdown of real, reachable models instead of free text.

Each provider probe is best-effort: missing credentials or an unreachable endpoint
yields an empty list, never an exception into startup. Probes reuse the provider
SDKs the app already uses for chat (so TLS / proxy / auth behave identically) with
short timeouts so a slow provider can't stall discovery. Results live in a
module-level cache, refreshed in a background thread at startup.
"""
from __future__ import annotations

import logging
import threading
from typing import Callable, Dict, List

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 4.0   # ollama (local)
_SDK_TIMEOUT = 6.0    # anthropic / openai cloud APIs

_lock = threading.Lock()
_loaded = False
_AVAILABLE: Dict[str, List[str]] = {"anthropic": [], "bedrock": [], "openai": [], "ollama": []}


def available() -> Dict[str, List[str]]:
    """Return a copy of the per-provider available-model lists (cache)."""
    with _lock:
        return {k: list(v) for k, v in _AVAILABLE.items()}


def _store(provider: str, models: List[str]) -> None:
    with _lock:
        _AVAILABLE[provider] = models


# --------------------------------------------------------------------------- probes
def _ollama_models(settings) -> List[str]:
    import httpx

    base = (settings.ollama_base_url or "http://localhost:11434").rstrip("/")
    r = httpx.get(f"{base}/api/tags", timeout=_HTTP_TIMEOUT)
    r.raise_for_status()
    return sorted(m["name"] for m in r.json().get("models", []) if m.get("name"))


def _anthropic_models(settings) -> List[str]:
    if not settings.anthropic_api_key:
        return []
    from anthropic import Anthropic

    client = Anthropic(api_key=settings.anthropic_api_key, timeout=_SDK_TIMEOUT)
    # API order is newest-first, which is a good dropdown order — keep it.
    return [m.id for m in client.models.list(limit=1000).data if getattr(m, "id", None)]


def _openai_models(settings) -> List[str]:
    if not settings.openai_api_key:
        return []
    from openai import OpenAI

    client = OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        timeout=_SDK_TIMEOUT,
    )
    return sorted(m.id for m in client.models.list().data if getattr(m, "id", None))


def _bedrock_models(settings) -> List[str]:
    import boto3
    from botocore.config import Config

    client = boto3.client(
        "bedrock",
        region_name=settings.aws_region,
        config=Config(connect_timeout=3, read_timeout=5, retries={"max_attempts": 1}),
    )
    resp = client.list_foundation_models(byOutputModality="TEXT")
    return sorted({m["modelId"] for m in resp.get("modelSummaries", []) if m.get("modelId")})


_PROBES: Dict[str, Callable] = {
    "ollama": _ollama_models,
    "anthropic": _anthropic_models,
    "openai": _openai_models,
    "bedrock": _bedrock_models,
}


# --------------------------------------------------------------------------- refresh
def refresh() -> Dict[str, List[str]]:
    """Re-probe every provider and update the cache. Best-effort per provider."""
    global _loaded
    from backend.config import settings

    for name, probe in _PROBES.items():
        try:
            models = probe(settings)
            _store(name, models)
            logger.info("model_catalog: %s -> %d model(s)", name, len(models))
        except Exception as exc:  # noqa: BLE001 - never break startup/UI on a probe
            _store(name, [])
            logger.info("model_catalog: %s discovery skipped/failed: %s", name, exc)
    _loaded = True
    return available()


def ensure_loaded() -> None:
    """Run a synchronous refresh if discovery hasn't completed yet (bounded by the
    per-probe timeouts). Cheap no-op once the startup refresh has populated."""
    if not _loaded:
        refresh()


def refresh_async() -> None:
    """Kick off discovery in a daemon thread so app startup isn't blocked."""
    threading.Thread(target=refresh, name="model-catalog-refresh", daemon=True).start()
