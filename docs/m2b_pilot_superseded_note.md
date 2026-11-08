# Superseded M2b pilot cells (pre option-A corruption scope)

The first 30-cell launch (2026-11-08 06:19 UTC) was stopped at 27 completed cells
after the PM's option-A ruling: **first-attempt-only corruption, corrective
re-prompts exempt**. In that run the corruptor hit every parsed proposal
(including re-prompts), so `repair_success_rate` was 0 by construction and
pre-registered P2 could not pass — those cells are superseded and are **not**
part of the pilot dataset.

* Location: `/tmp/opencode/m2b_pilot_superseded_preFixA/m2b_pilot/` (outside the repo)
* Telemetry pattern: verified arm `hostile_corrupted_proposals=48`
  (24 first attempts + 24 corrupted re-prompts), `repair_iterations=48`,
  `llm_fallback_steps=24`; unverified arm `hostile_corrupted_proposals=24`,
  `llm_unrepaired_violations=240`, `llm_backend_errors=0`. 15 unverified +
  12 verified cells, all model `poolside/laguna-xs-2.1`, 0 backend errors.
* Pilot dataset starts fresh under option A (`SAEA_LLM_HOSTILE=out_of_bounds`
  with re-prompt exemption) once A's branch is merged; the 2-cell flag smoke
  must first show `repair_success_rate > 0` in the verified arm.
