"""OpenAI-compatible hosted API LLM backend - the P0-2 resume transport.

Replaces the Ollama-local transport (user order 2026-10-31): the ablation
controllers keep their prompt-callable contract, ``parse_llm_actions``, the
full metric set, and the ``llm_dispatch_v2`` prompt; only the transport
changes. Selected with ``AGENT_BACKEND=api:<model>`` (or
``--llm-backend api:<model>``).

The secret never enters code, configs, or logs: the Bearer token is read from
the ``LLM_API_KEY`` environment variable at call time, and ``LLM_BASE_URL``
(default ``https://api.openai.com/v1``) selects the OpenAI-compatible
endpoint.
"""

import json
import os
import time
import urllib.error
import urllib.request
from typing import List, Optional

# Transient server-side failures worth a retry; everything else (401, 400,
# 404, ...) fails fast because retrying cannot fix an auth or request error.
RETRYABLE_HTTP_STATUSES = frozenset({429, 500, 502, 503, 504})
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_API_MODEL = "gpt-4o-mini"


class ApiPromptCallable:
    """Synchronous ``prompt -> text`` adapter over ``POST {base_url}/chat/completions``.

    Same contract as ``OllamaPromptCallable`` (``src/agents/backend/local.py``):
    the controller owns the versioned dispatch prompt and classifies the raw
    response via ``parse_llm_actions`` (clean/fenced/invalid); this callable
    only ferries text and exposes the same cumulative telemetry attributes
    (``call_count``, ``latency_samples_ms``, ``prompt_tokens``,
    ``completion_tokens``, ``model_digest``) that ``agent_stats()`` aggregates
    into the paper metrics. The dispatch prompt travels as a single user
    message so the prompt bytes (and therefore ``prompt_hash``) are identical
    across transports.

    Behaviour:

    - one logical call = up to ``1 + max_retries`` HTTP attempts; retries
      apply only to 429/5xx with a short linear backoff (``retry_backoff_s``
      x attempt). Timeouts and other network errors fail immediately.
    - a hard per-call socket timeout (``timeout_s``) bounds every attempt.
    - ``usage.prompt_tokens`` / ``usage.completion_tokens`` are captured for
      the real token counts, and the returned model id is stored in
      ``model_digest`` (the manifest field the Ollama path used for the
      sha256 digest).
    - NIM/glm-5.3-flash quirks (live-verified by the PM, 31 Oct 2026): the
      transport speaks HTTP/1.1 unconditionally (``urllib`` does; HTTP/2
      POSTs get a bogus 404 through the egress proxy), and reasoning models
      may return ``content: null`` with the answer inside
      ``message.reasoning_content`` — that text is then used as the raw
      output so ``parse_llm_actions`` classifies it (a fenced JSON inside
      reasoning still counts and is recorded as a formatting violation).
      Request a generous completion budget (``max_tokens >= 512``) so
      reasoning does not starve the answer.
    """

    def __init__(
        self,
        model: str,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.0,
        seed: int = 42,
        timeout_s: float = 120.0,
        max_tokens: int = 512,
        max_retries: int = 2,
        retry_backoff_s: float = 0.5,
    ):
        self.model = model
        self.base_url = (base_url or os.getenv("LLM_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        # When None, the key is read from LLM_API_KEY at call time so a key
        # supplied after construction still works.
        self.api_key = api_key
        self.temperature = temperature
        self.seed = seed
        self.timeout_s = timeout_s
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.retry_backoff_s = retry_backoff_s
        # Cumulative per-call telemetry (deltas are taken by the caller).
        self.call_count = 0
        self.latency_samples_ms: List[float] = []
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.last_error: Optional[str] = None
        # The API's own model id (e.g. "gpt-4o-mini-2024-07-18") from the
        # first successful response; None until then.
        self.model_digest: Optional[str] = None

    def _resolve_api_key(self) -> str:
        key = self.api_key or os.getenv("LLM_API_KEY", "")
        if not key:
            raise RuntimeError(
                "LLM_API_KEY is not set: refusing to call the hosted LLM API "
                "without credentials (set the env var; never hardcode keys)."
            )
        return key

    def _request(self, prompt: str) -> urllib.request.Request:
        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "seed": self.seed,
            "max_tokens": self.max_tokens,
            "stream": False,
        }).encode("utf-8")
        return urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._resolve_api_key()}",
            },
            method="POST",
        )

    def __call__(self, prompt: str) -> str:
        self.call_count += 1
        start = time.perf_counter()
        try:
            return self._call_with_retries(prompt)
        except Exception as exc:
            self.last_error = str(exc)
            raise
        finally:
            self.latency_samples_ms.append((time.perf_counter() - start) * 1000.0)

    def _call_with_retries(self, prompt: str) -> str:
        # Built (and the key resolved) before any HTTP attempt so a missing
        # LLM_API_KEY fails fast with a clear error and never hits the wire.
        request = self._request(prompt)
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            if attempt:
                time.sleep(self.retry_backoff_s * attempt)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                    body = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = ""
                try:
                    detail = exc.read().decode("utf-8", "replace")[:200]
                except Exception:
                    pass
                last_error = RuntimeError(
                    f"LLM API error {exc.code}: {detail or exc.reason}"
                )
                if exc.code not in RETRYABLE_HTTP_STATUSES:
                    raise last_error
                continue
            except Exception as exc:
                # Network failure or timeout: retrying a dead endpoint or an
                # over-long generation only stalls the simulation step.
                raise RuntimeError(f"LLM API request failed: {exc}") from exc
            return self._extract_and_record(body)
        raise last_error or RuntimeError("LLM API call failed after retries")

    def _extract_and_record(self, body: dict) -> str:
        usage = body.get("usage") or {}
        self.prompt_tokens += int(usage.get("prompt_tokens") or 0)
        self.completion_tokens += int(usage.get("completion_tokens") or 0)
        returned_model = body.get("model")
        if returned_model:
            self.model_digest = str(returned_model)
        try:
            message = body["choices"][0]["message"]
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(
                "LLM API returned an unexpected response shape "
                f"(no choices[0].message): {json.dumps(body)[:200]}"
            )
        # Reasoning models (e.g. glm-5.3-flash) may leave content null and put
        # the answer in reasoning_content; hand that text to the controller's
        # parse_llm_actions so in-reasoning JSON is classified and recorded
        # (fenced stays fenced) instead of being dropped as an empty response.
        content = message.get("content")
        if content is None or (isinstance(content, str) and not content.strip()):
            content = message.get("reasoning_content")
        if content is None:
            raise RuntimeError(
                "LLM API response has neither content nor reasoning_content: "
                f"{json.dumps(message)[:200]}"
            )
        return str(content or "")


def api_prompt_callable(
    model: str,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.0,
    seed: int = 42,
    timeout_s: float = 120.0,
    max_tokens: int = 512,
    max_retries: int = 2,
    retry_backoff_s: float = 0.5,
) -> ApiPromptCallable:
    """Build the synchronous prompt -> text adapter the controllers consume."""
    return ApiPromptCallable(
        model=model,
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
        seed=seed,
        timeout_s=timeout_s,
        max_tokens=max_tokens,
        max_retries=max_retries,
        retry_backoff_s=retry_backoff_s,
    )
