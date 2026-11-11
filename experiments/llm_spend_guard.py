"""Paid-LLM spend guard: no hosted-vendor call without an explicit opt-in.

Why this exists
---------------
On 2026-11-08 the project's M2a experiment arms spent 754 calls
(qwen3-coder-flash 693, kimi-k2.7-code 56) on the Alibaba/DashScope account.
The authorization of record is poolside/laguna-xs-2.1 on NVIDIA NIM; the
DashScope spend was outside it, and part of it ran on an exhausted free
quota. The root cause was silent defaults: LLM_PROVIDER defaults to
"dashscope", LLM_MODEL to "kimi-k2.7-code" and the API base URL to the
DashScope endpoint, so any runner started without explicit environment
variables spent on a paid vendor by default.

The guard
---------
Runners call enforce_authorized_llm() before any LLM setup. A run may
proceed when either
  * the configured/intended model is the authorized one (poolside/... on
    NVIDIA NIM - the authorization of record), or
  * the endpoint is a paid hosted vendor AND the operator opted in with
    SAEA_ALLOW_DASHSCOPE=1 (the deliberate path the sanctioned comparison
    arms use).
Anything else aborts loudly instead of silently spending.

This file is intentionally dependency-free so any runner can import it.
"""

from __future__ import annotations

import os
import sys

# Hosts whose calls spend money on a hosted vendor account.
PAID_VENDOR_HOSTS = (
    "maas.aliyuncs.com",
    "dashscope.aliyuncs.com",
    "dashscope-intl.aliyuncs.com",
)

# Providers that are NOT a paid hosted-vendor account.
_NON_VENDOR_PROVIDERS = ("nvidia", "openai", "anthropic", "ollama", "fallback")

# Model identifiers that are the authorization of record.
AUTHORIZED_MODEL_MARKERS = ("poolside/", "nvidia/")

OPT_IN_ENV = "SAEA_ALLOW_DASHSCOPE"

_POLICY_MESSAGE = (
    "LLM spend guard: this run would call a paid hosted vendor "
    "(DashScope/Alibaba), which is outside the authorization of record "
    "(poolside/laguna-xs-2.1 on NVIDIA NIM). Point LLM_BASE_URL / "
    "LLM_PROVIDER at the authorized endpoint, or set "
    "SAEA_ALLOW_DASHSCOPE=1 to opt in deliberately (the sanctioned "
    "comparison arms use that). Refusing to spend without an explicit "
    "opt-in - see docs/incident_2026-11-08_dashscope_spend.md."
)


def _endpoint_host() -> str:
    base = os.getenv("LLM_BASE_URL", "")
    if "://" in base:
        base = base.split("://", 1)[1]
    return base.split("/", 1)[0].lower()


def is_paid_vendor_endpoint() -> bool:
    backend = os.getenv("AGENT_BACKEND", "")
    if backend and not backend.startswith("api:"):
        # An explicit non-api backend (ollama:, fallback:, ...) is not a
        # hosted-vendor call at all, whatever the provider default says.
        return False
    base = os.getenv("LLM_BASE_URL", "")
    if base:
        host = _endpoint_host()
        return any(host == h or host.endswith("." + h) for h in PAID_VENDOR_HOSTS)
    # No explicit base URL: the config default resolves to the paid vendor,
    # so only an explicitly non-vendor provider avoids the paid path.
    provider = os.getenv("LLM_PROVIDER", "dashscope").lower()
    return provider not in _NON_VENDOR_PROVIDERS


def opted_in() -> bool:
    return os.getenv(OPT_IN_ENV, "").strip().lower() in ("1", "true", "yes")


def _configured_model() -> str:
    return os.getenv("AGENT_BACKEND", "") or os.getenv("LLM_MODEL", "")


def _is_authorized_model(model: str) -> bool:
    low = (model or "").lower()
    return any(marker in low for marker in AUTHORIZED_MODEL_MARKERS)


def enforce_authorized_llm(intended: str | None = None) -> str:
    """Abort the process when a paid-vendor call would happen without opt-in.

    `intended` is the model a runner is hard-wired to use (e.g. the NIM model
    constant), so a runner that already enforces the authorization itself
    never trips the guard. Returns a one-line status when the run may go."""
    model = intended if intended is not None else _configured_model()
    if _is_authorized_model(model):
        return "[spend-guard] authorized model configured (NIM/laguna)"
    if is_paid_vendor_endpoint() and not opted_in():
        raise SystemExit(_POLICY_MESSAGE)
    if is_paid_vendor_endpoint():
        return f"[spend-guard] paid vendor endpoint, opted in via {OPT_IN_ENV}=1"
    return "[spend-guard] endpoint not a paid hosted vendor"


if __name__ == "__main__":  # manual check: python3 experiments/llm_spend_guard.py
    try:
        print(enforce_authorized_llm())
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        raise
