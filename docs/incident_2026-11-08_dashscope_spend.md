# Incident record: unauthorized paid-LLM spend (2026-11-08)

Status: contained (no live spend path), guard in place; user-side actions open.
Authorization of record: **poolside/laguna-xs-2.1 on NVIDIA NIM only**;
hosted qwen/kimi vendors are not authorized.

## What happened

On 2026-11-08 the Alibaba/DashScope account backing the OpenBot platform
recorded **754 model calls**: qwen3-coder-flash 693, kimi-k2.7-code 56
(plus 5 wan2.7-image-pro calls that remain unexplained - see Open items).
The calls came from the project's own **M2a experiment arms** running against
DashScope - not from the authorized NIM pipeline and not from a platform-layer
fallback (an earlier "platform fallback" reading was investigated and
corrected).

The kimi arm exhausted the free quota mid-run (HTTP 403). 60 cells produced
after exhaustion were degraded to the rule-based fallback
(`llm_backend_errors=24`, `first_attempt_validity=0.0`) and were quarantined
to `/tmp/opencode/m2a_quota_compromised` - they never entered any reported
number. The re-armed run on the authorized model (`experiments/m2a_rerun_laguna`,
2026-11-08 11:53, 594 laguna references) is the valid dataset.

## Evidence chain

| When (local) | What | Where |
| --- | --- | --- |
| 2026-11-07 17:44 | Commit "switch LLM API to kimi-k2.7-code on DashScope" | repo `42daaf252` (src/agents/backend/{api,config,registry,remote}.py) |
| 2026-11-08 00:17-00:33 | M2a matrix arms ran on kimi/qwen; quota 403 mid-run | `/tmp/opencode/m2a_queue.log`, `m2a_quota_compromised/`, `experiments/m2a_rerun/` |
| 2026-11-08 01:01 | Pre-flight guard commit (abort on 402/403/404) | repo `20c8ce536` |
| 2026-11-08 11:53 | Authorized re-arm on laguna/NIM | `experiments/m2a_rerun_laguna/` |
| 2026-11-08 | Dashboard total: 693 qwen + 56 kimi calls | user's Alibaba usage panel (screenshot on file) |

Contributing causes:
1. **Silent defaults**: `LLM_PROVIDER` defaults to `dashscope`, `LLM_MODEL`
   to `kimi-k2.7-code`, and the API base URL to the DashScope endpoint
   (`src/agents/backend/config.py`, `api.py`). A runner started without
   explicit environment variables spends on a paid vendor by default.
2. Key availability: `DASHSCOPE_API_KEY` exists in multiple agents' key
   stores, so the default path could actually authenticate.
3. The multi-LLM comparison design predates the authorization-of-record
   decision, so the arms ran believing they were sanctioned.

No evidence of intent either way is claimed; the breach is factual: paid
tokens were spent outside the recorded authorization.

## Containment (done, repo-side, reversible)

- No live runners spend (verified: no qwen/kimi/dashscope processes alive).
- **`experiments/llm_spend_guard.py`**: runners must pass before any LLM
  setup. A run proceeds only with the authorized NIM/laguna model
  configured/intended, or with an explicit `SAEA_ALLOW_DASHSCOPE=1` opt-in on
  a paid-vendor endpoint; otherwise the process aborts loudly. Wired into
  `experiments/run_experiment.py` and `experiments/run_code_repair.py`.
- 12 unit tests (`tests/test_llm_spend_guard.py`) pin the contract:
  the bare-defaults case, the maas/dashscope/dashscope-intl hosts, the NIM
  base URL, the authorized-model pass-through, and the opt-in path.

## Open items (user-side)

1. **Rotate the DashScope API key** in the Alibaba console - the only action
   that definitively kills further spend (the current key is in agent key
   stores on this machine).
2. Decide the per-agent key-store cleanup (DASHSCOPE_API_KEY exists in the
   Research Engineer's, this agent's, and one other agent's store).
3. Team notification: who is told, in what wording (evidence ready; no
   accusation of intent is supported).
4. The 5 `wan2.7-image-pro` calls have no identified source.

## Follow-up for the paper

- The 60 quarantined cells are excluded from every reported number.
- The M2a comparison, if any, runs under an explicit `SAEA_ALLOW_DASHSCOPE=1`
  opt-in with the rotated key, or not at all.
