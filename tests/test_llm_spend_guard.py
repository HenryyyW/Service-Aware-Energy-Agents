"""Paid-LLM spend guard tests (the 2026-11-08 DashScope incident guard).

Contract: a run proceeds only with (a) the authorized NIM/laguna model
configured or intended, or (b) an explicit SAEA_ALLOW_DASHSCOPE=1 opt-in
on a paid-vendor endpoint; everything else aborts.
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


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in GUARD_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


def test_defaults_are_a_paid_vendor_endpoint():
    # No env at all: provider defaults to dashscope -> silent spend hazard.
    assert is_paid_vendor_endpoint() is True


def test_dashscope_base_url_is_paid():
    os.environ["LLM_BASE_URL"] = (
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    )
    assert is_paid_vendor_endpoint() is True


def test_maas_subdomain_is_paid():
    os.environ["LLM_BASE_URL"] = (
        "https://ws-xxx.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
    )
    assert is_paid_vendor_endpoint() is True


def test_nim_base_url_is_not_paid():
    os.environ["LLM_BASE_URL"] = "https://integrate.api.nvidia.com/v1"
    assert is_paid_vendor_endpoint() is False


def test_explicit_nvidia_provider_is_not_paid():
    os.environ["LLM_PROVIDER"] = "nvidia"
    assert is_paid_vendor_endpoint() is False


def test_silent_defaults_abort():
    with pytest.raises(SystemExit):
        enforce_authorized_llm()


def test_explicit_dashscope_selection_aborts_without_opt_in():
    os.environ["LLM_PROVIDER"] = "dashscope"
    os.environ["LLM_MODEL"] = "kimi-k2.7-code"
    with pytest.raises(SystemExit):
        enforce_authorized_llm()


def test_opt_in_allows_the_paid_path():
    os.environ["LLM_PROVIDER"] = "dashscope"
    os.environ["LLM_MODEL"] = "kimi-k2.7-code"
    os.environ[OPT_IN_ENV] = "1"
    assert opted_in() is True
    status = enforce_authorized_llm()
    assert "opted in" in status


def test_authorized_model_config_passes():
    os.environ["LLM_MODEL"] = "poolside/laguna-xs-2.1"
    status = enforce_authorized_llm()
    assert "authorized" in status


def test_authorized_agent_backend_passes():
    os.environ["AGENT_BACKEND"] = "api:poolside/laguna-xs-2.1"
    status = enforce_authorized_llm()
    assert "authorized" in status


def test_intended_authorized_model_passes_even_with_paid_defaults():
    status = enforce_authorized_llm(intended="poolside/laguna-xs-2.1")
    assert "authorized" in status


def test_intended_paid_model_still_aborts():
    with pytest.raises(SystemExit):
        enforce_authorized_llm(intended="kimi-k2.7-code")
