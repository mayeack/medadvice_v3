#!/usr/bin/env python3
"""Regression: per-provider model discovery (backend/model_catalog.py).

Guards the Settings "Model" dropdown's data source: discovery must (1) populate a
per-provider available-model cache, (2) be best-effort — a failing/unconfigured
provider yields [] without breaking the others, and (3) expose all four providers.
Network-free: the provider probes are stubbed so the test is deterministic.

Run:  venv/bin/python tests/test_model_catalog.py    # exit 0 = pass
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import model_catalog  # noqa: E402

_fails = 0


def check(name: str, cond: bool) -> None:
    global _fails
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")
    if not cond:
        _fails += 1


def test_refresh_populates_and_is_best_effort() -> None:
    orig_probes = model_catalog._PROBES
    orig_loaded = model_catalog._loaded
    try:
        # ollama returns models; anthropic raises (e.g. bad key) -> must degrade to [].
        def _boom(_settings):
            raise RuntimeError("invalid credentials")

        model_catalog._PROBES = {
            "ollama": lambda _s: ["dolphin3:8b", "llama3.2:latest"],
            "anthropic": _boom,
            "openai": lambda _s: [],
            "bedrock": lambda _s: [],
        }
        av = model_catalog.refresh()
        check("refresh returns all four providers",
              set(av.keys()) == {"anthropic", "bedrock", "openai", "ollama"})
        check("a working probe populates its list", av["ollama"] == ["dolphin3:8b", "llama3.2:latest"])
        check("a failing probe degrades to [] (best-effort)", av["anthropic"] == [])
        check("ensure_loaded marks discovery loaded", model_catalog._loaded is True)
        check("available() mirrors the refreshed cache", model_catalog.available()["ollama"] == av["ollama"])
        # available() must hand back copies, not the live lists.
        model_catalog.available()["ollama"].append("mutated")
        check("available() returns copies (no external mutation)",
              "mutated" not in model_catalog.available()["ollama"])
    finally:
        model_catalog._PROBES = orig_probes
        model_catalog._loaded = orig_loaded


def main() -> int:
    try:
        test_refresh_populates_and_is_best_effort()
    except Exception as e:  # noqa: BLE001
        global _fails
        _fails += 1
        print(f"  ERROR {e}")
    print(f"RESULT: {'ok' if not _fails else str(_fails) + ' failed'}")
    return 1 if _fails else 0


if __name__ == "__main__":
    sys.exit(main())
