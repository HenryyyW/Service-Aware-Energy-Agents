# ACM e-Energy Submission Package — Service-Aware Energy Agents

**Target venue**: ACM e-Energy (user-confirmed)
**Status**: M5.3 statistical analysis complete; M5.4 submission package prepared

## Contents

| File | Description |
|---|---|
| `paper_draft.md` | Full paper results section (§5.1–5.9 + caveats) |
| `analysis/` | T4/T5 statistical analysis + benchmark summary |
| `submission_checklist.md` | ACM e-Energy submission checklist |

## Key Results

| Finding | Evidence |
|---|---|
| multi_agent is cost-minimal in every scenario | A: −15.30 ± 0.03 USD vs rule_based (p_Holm < 0.0001) |
| mpc is service-maximal | EV completion 0.93–0.99 (+81 pp vs rule_based) at +104–126 USD |
| centralized ≈ rule_based on cost | −0.07 ± 0.47 USD (p_Holm = 0.72) |
| Scenario E failures are scenario-property | member_cost_coverage 0.80 across all controllers |
| M2a screen: null result | fallback_share 0.0, both arms identical |
| 356 tests pass | Full regression suite green |

## Submission Checklist

- [x] Statistical analysis (T4/T5) with Holm-corrected paired t-tests
- [x] Null ablation documentation (§5.7–5.9)
- [x] Reproducibility (T5): scenario config SHA-256, git commit, seed-pair check
- [x] Caveats documented (7 items, in order)
- [x] Paper venue confirmed: ACM e-Energy
- [ ] Frontend figures (F1–F8): Pending (Product Design Lead)
- [ ] LaTeX formatting: Pending
- [ ] Author list and affiliations: Pending (PM)
