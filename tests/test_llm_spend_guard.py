"""Paid-LLM spend guard tests (the 2026-11-08 DashScope incident guard).

Contract: a run proceeds only with (a) the authorized NIM/laguna model
configured or intended, or (b) an explicit SAEA_ALLOW_DASHSCOPE=1 opt-in
on a paid-vendor endpoint; everything else aborts.

All env mutation goes through monkeypatch (auto-reverted); assigning
os.environ directly here would leak into later tests.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.llm_spend_guard import (  # noqa: E402
    OPT_IN_ENV,
    enforce_authorized_llm,
    is_paid_vendor_endpoint,
    opted_in,
)

GUARD_ENV_KEYS = (
    "LLM_BASE_URL",
    "LLM_PROVIDER",
    "LLM_MODEL",
    "AGENT_BACKEND",
    OPT_IN_ENV,
)

MAAS_URL = "https://ws-xxx.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
DASHSCOPE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
NIM_URL = "https://integrate.api.nvidia.com/v1"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in GUARD_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


def test_defaults_are_a_paid_vendor_endpoint(monkeypatch):
    # No env at all: provider defaults to dashscope -> silent spend hazard.
    assert is_paid_vendor_endpoint() is True


def test_dashscope_base_url_is_paid(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", DASHSCOPE_URL)
    assert is_paid_vendor_endpoint() is True


def test_maas_subdomain_is_paid(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", MAAS_URL)
    assert is_paid_vendor_endpoint() is True


def test_nim_base_url_is_not_paid(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", NIM_URL)
    assert is_paid_vendor_endpoint() is False


def test_explicit_nvidia_provider_is_not_paid(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "nvidia")
    assert is_paid_vendor_endpoint() is False


def test_explicit_local_backend_is_not_paid(monkeypatch):
    # AGENT_BACKEND=ollama:<model> must not trip on the dashscope provider
    # default (a local model spends nothing, even a qwen-named one).
    monkeypatch.setenv("AGENT_BACKEND", "ollama:qwen2.5-coder:7b")
    assert is_paid_vendor_endpoint() is False
    assert "not a paid hosted vendor" in enforce_authorized_llm()


def test_silent_defaults_abort(monkeypatch):
    with pytest.raises(SystemExit):
        enforce_authorized_llm()


def test_explicit_dashscope_selection_aborts_without_opt_in(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "dashscope")
    monkeypatch.setenv("LLM_MODEL", "kimi-k2.7-code")
    with pytest.raises(SystemExit):
        enforce_authorized_llm()


def test_hosted_api_backend_still_blocked(monkeypatch):
    # api:<paid model> is exactly the incident's shape.
    monkeypatch.setenv("AGENT_BACKEND", "api:kimi-k2.7-code")
    with pytest.raises(SystemExit):
        enforce_authorized_llm()


def test_opt_in_allows_the_paid_path(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "dashscope")
    monkeypatch.setenv("LLM_MODEL", "kimi-k2.7-code")
    monkeypatch.setenv(OPT_IN_ENV, "1")
    assert opted_in() is True
    assert "opted in" in enforce_authorized_llm()


def test_authorized_model_config_passes(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "poolside/laguna-xs-2.1")
    assert "authorized" in enforce_authorized_llm()


def test_authorized_agent_backend_passes(monkeypatch):
    monkeypatch.setenv("AGENT_BACKEND", "api:poolside/laguna-xs-2.1")
    assert "authorized" in enforce_authorized_llm()


def test_intended_authorized_model_passes_even_with_paid_defaults(monkeypatch):
    assert "authorized" in enforce_authorized_llm(intended="poolside/laguna-xs-2.1")


def test_intended_paid_model_still_aborts(monkeypatch):
    with pytest.raises(SystemExit):
        enforce_authorized_llm(intended="kimi-k2.7-code")
