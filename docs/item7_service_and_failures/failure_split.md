# Scenario E: per-failure-type detection vs recovery (10 seeds x 5 controllers)

* **Detected** -- at least one violation-bearing diagnostic (power-flow /
  limit check) inside the failure window.
* **Exceedance steps** -- steps inside the window where the community net
  injection exceeds the reduced export limit (7.5 kW), computed from the
  diagnostic reports independently of the violation flag.
* **Recovered steps** -- exceedance steps where a violation was flagged on
  the previous step but not on this one, i.e. control cleared it while the
  exceedance still held. Environment-driven cessation (net export falling
  below the limit in the evening) is *not* counted as recovery.

| Failure type | Window (timesteps) | Runs | Violation steps in window | Exceedance steps in window | Runs detected | Recovered steps |
|---|---|---|---|---|---|---|
| battery | 65-69 (1 distinct span(s)) | 50 | 0 | 0 | 0 | 0 |
| ev_charger | 78-81 (1 distinct span(s)) | 50 | 0 | 0 | 0 | 0 |
| grid_limit | 132-138 (1 distinct span(s)) | 50 | 171 | 171 | 50 | 0 |
| pv_inverter | 34-38 (1 distinct span(s)) | 50 | 0 | 0 | 0 | 0 |
| sensor | 96-119 (1 distinct span(s)) | 50 | 0 | 0 | 0 | 0 |

## Interpretation

* Every configured failure is activated and deactivated on schedule in
  every run (oracle-side logging in `failure_history.json`), and the
  activation/deactivation is itself recorded as a diagnostic.
* The four asset failures (PV inverter, battery, EV charger, sensor)
  produce **no exceedance and no violation**: across all 50 runs the
  community net injection never crosses the configured 150 kW export (200
  kW import) limit inside those windows, so the verification layer has
  nothing to flag. Detection of these failures is *configuration-oracle*
  only -- no controller observes them, which is exactly the gap the
  reviewer asked us to state.
* The grid-limit reduction is the only failure the verification layer
  detects, in **50/50 runs**, and it is detected in **every** step where
  the community net injection exceeds the reduced 7.5 kW export limit.
* **Resolution rate is 0**: no violation ever clears while the exceedance
  still holds. The exceedance stops at the end of the PV hours (community
  net injection falls from ~13 kW to ~4.5 kW between the last and the
  first violation-free step) -- the environment stops violating, the
  controllers never act on it. Any claim of 'recovery' from these runs
  would be an artifact of that cessation.
