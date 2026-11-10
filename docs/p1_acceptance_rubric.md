# P1 — NL → ScenarioConfig acceptance rubric (corpus + scoring)

Owner: Research Engineer · Date: 2026-11-10 · Status: ready for verification
Companion data: `experiments/reference/p1_nl_corpus.json` (16 items) · Deterministic checks: `experiments/p1_score_corpus.py`
Consumers: Backend/Simulation Engineer A (pipeline owner) and Project Partner (verification gate) — mock-free; every criterion is checkable against the real pipeline with no LLM spend in the checking itself.

---

## 1. What the corpus is

16 natural-language scenario descriptions, each with a machine-readable rubric. 12 **complete** items cover the eight scenario domains (buildings, PV, battery, EV, flexible load, tariff, weather, grid — plus energy sharing and simulation-window items); 4 **rejection-path** items (2 deliberately incomplete, 2 out-of-range) exercise the "name the field, never silently auto-correct" contract from `docs/nl_config_confirm_design.md`.

A run of the corpus = for each item: A's pipeline parses the NL text into a `ScenarioConfig`, the config goes through `POST /api/scenarios` (create), `GET /api/scenarios/{id}/validate`, and a simulation of the configured window. Each of the five criteria below is scored pass/fail per item.

## 2. The five criteria (per item)

| # | Criterion | Pass condition | Check (mock-free) |
|---|-----------|----------------|-------------------|
| C1 | **Plans a complete config** | The parsed config contains exactly the sections/instances the item's `plans_complete_config` demands (no missing sections, no invented assets, no stock-default padding) | Deterministic: compare parsed config's section counts against the rubric (`p1_score_corpus.py`, C1 checks) |
| C2 | **Required fields present** | Every path in the item's `required_fields` exists with the right type in the parsed config | Deterministic: path walk against the parsed config (C2 checks) |
| C3 | **Values in range** | Every stated value matches the NL text, and every unstated-but-loaded value satisfies the semantic range (SOC ∈ [0,1] with soc_min < initial < soc_max, positive limits, valid enums, overnight EV windows, internally consistent flexible loads) | Deterministic: the item's `values_in_range` list, each checked programmatically (C3 checks) |
| C4 | **Scenario simulates clean** | The simulation of the configured window runs to completion with no exception (complete items) / is **blocked before running** with the named field (rejection items) | Runtime: run the scenario via the simulator on the parsed config; record exit status. For rejection items, C4 passes iff the run does not start and the named field is surfaced |
| C5 | **Round-trips through POST /scenarios** | `POST /api/scenarios` accepts the config (201), `GET /api/scenarios/{id}` returns an equivalent config, and `GET /api/scenarios/{id}/validate` returns the expected `valid`/`errors`/`warnings` | Runtime: live API calls against the backend; compare the returned config field-by-field with the submitted one |

**Rejection-path items** invert C1–C3: C1/C2/C3 pass iff the pipeline does **not** plan the invalid/incomplete artifact and **does** name the offending field (per the design spec: "Never silently drop or auto-correct a field"). A silently defaulted capacity, a clamped negative limit, or a dropped SOC bound are FAILs, not passes.

**Provenance is not scored here.** The confirm-screen confidence chips (`given`/`assumed`/`default`) are Frontend scope (`docs/nl_config_confirm_design.md`); the corpus checks values, not their provenance display.

## 3. Scoring

- **Item score** = pass iff all five criteria pass (C1–C5 for complete items; the inverted C1–C3 plus C4/C5 for rejection items).
- **Corpus score** = fraction of the 16 items passing.
- **Acceptance bar (pre-registered with the PM), evaluated over the FULL corpus — the record of decision:**
  - **≥ 14 / 16 items pass**, **and**
  - **all 8 domains covered by at least one passing complete item**, **and**
  - **all 4 rejection-path items pass** (a missed rejection is a safety-relevant miss, not a partial credit).
- **Pilot reading (NOT the record):** the PM's sequence runs the pipeline on the **first 10 corpus items** first. When any item is unproduced the report separates the two readings explicitly — the full-corpus bar (which stays FAIL until all 16 exist; missing configs are `MISSING-CONFIG`, never evidence about the pipeline) and a `pilot_reading` tally over the produced subset only (items passed / produced, domains covered, rejection items passed, with the scope stated). A pilot reading never substitutes for the bar: the authoring-acceptance number enters the paper only when the full-corpus bar is evaluated on a complete run.
- Reported per-item with the failing criterion named — the same "report the shape, not just the count" discipline as the code-repair benchmark.
- Two instrument corrections from the scorer self-test (2026-11-10): the `building_type` multiset check is order-insensitive and count-sensitive (the NL states the multiset, not the order); the c01 corpus entry's expected types are the exact per-building list (3x residential) rather than a set-style shorthand.

## 4. Running it

```bash
# 1. Run A's pipeline over the corpus, dumping one ScenarioConfig JSON per item:
#    experiments/p1_pipeline_output/<item_id>.json   (produced by A's harness)
# 2. Deterministic checks (C1-C3 + expected-validation), no server, no LLM:
python3 experiments/p1_score_corpus.py --configs experiments/p1_pipeline_output --report experiments/p1_score_report.json
# 3. Runtime checks (C4 simulate-clean, C5 POST round-trip) recorded by A/PM into the report's runtime section; the scorer merges both into the item verdicts.
```

The scorer is deterministic and mock-free: it reads the corpus, the produced configs, and (optionally) a runtime-results JSON, and emits per-item, per-criterion verdicts plus the corpus score against the acceptance bar.

## 5. What this acceptance protects

The pipeline is the platform's front door (NL → executable config). A config that silently invents a capacity or runs out-of-range physics produces plausible-looking but wrong simulation results downstream; the rejection-path items are the guard against exactly that, which is why they carry zero-partial-credit weight in the bar.
