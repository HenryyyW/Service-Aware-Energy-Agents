# ACM e-Energy Submission Checklist

## Content Complete
- [x] §5.1 Experimental setup (T1): 5 scenarios × 5 controllers × 5 seeds (125 runs)
- [x] §5.2 Cost, peak and service (T2, T3): paired deltas vs rule_based, Holm-corrected
- [x] §5.3 Scenario E: failure injection (F5): members_interrupted, cost_coverage
- [x] §5.4 Ablation: verified vs unverified agents (T4, F6): fallback-mode null
- [x] §5.5 Reproducibility (T5): config SHA-256, git commit, seed-pair check
- [x] §5.6 Real-LLM ablation: M2a screen (poolside/laguna-xs-2.1, 24-step)
- [x] §5.7 M2b gate verdict: null result (fallback_share 0.0, no arm divergence)
- [x] §5.8 Validity gate: NOT fallback-dominated (fallback_share 0.0 < 0.25)
- [x] §5.9 Null ablation discussion
- [x] Caveats (7 items, in order)

## Statistical Analysis Complete
- [x] T4 ablation KPIs with mean ± 95% CI per scenario/controller
- [x] T5 reproducibility sweep (scenario config SHA-256, git commit, seed-pair check)
- [x] Paired deltas with Holm correction (family-wise error rate controlled)
- [x] Effect sizes reported next to p-values
- [x] M5.2 benchmark: 100 lmp-regime runs on main @ b152037

## Pending (Pre-Submission)
- [ ] Frontend figures (F1–F8): Product Design Lead
- [ ] LaTeX formatting: convert paper_draft.md to ACM template
- [ ] Author list and affiliations: PM to provide
- [ ] Camera-ready figures: Product Design Lead

## Submission Target
- **Venue**: ACM e-Energy (user-confirmed)
- **Format**: ACM format (single column, ~10-12 pages)
- **Deadline**: PM to confirm ACM e-Energy submission date
