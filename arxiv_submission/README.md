# arXiv Submission Package

## Contents
```
arxiv_submission/
├── arxiv_main.tex      # Main LaTeX (article class, single column)
├── references.bib      # 15 references (plainnat style)
└── figures/            # 8 PDF figures
    ├── f1_total_cost.pdf
    ├── f1_peak_demand_kw.pdf
    ├── f1_ev_completion_rate.pdf
    ├── f2_total_cost.pdf
    ├── f2_peak_demand_kw.pdf
    ├── f2_ev_completion_rate.pdf
    ├── f3_cost_vs_ev_completion.pdf
    └── f7_cost_vs_service.pdf
```

## Compile
```bash
cd arxiv_submission
pdflatex arxiv_main
bibtex arxiv_main
pdflatex arxiv_main
pdflatex arxiv_main
```
Output: `arxiv_main.pdf` (~12 pages, single column)

## Differences from ACM Version
- **Class**: `article` (not `acmart`)
- **Columns**: Single column (not two-column sigconf)
- **Bibliography**: `plainnat` + `natbib` (not ACM-Reference-Format)
- **Authors**: Simple format (not ACM affiliation blocks)
- **No**: `\shortauthors`, `\begin{acks}`, ACM-specific metadata
- **Figures**: F1-F3 + F7 included; F4/F5/F6 need camera-ready; F8 gated

## Paper Stats
- 175 runs (125 matrix + 50 ablation) on commit `035a52f`, `git_dirty: false`
- 0 failed runs, seed-pair reproducibility confirmed
- 347/347 tests pass
- Sections: Intro, Method, Setup, Results (5 subsections), Discussion, Conclusion
- Tables: 3 (scenarios, deltas, aggressive config)
- Figures: 4 (F1: 3-panel KPI bars, F2: seed strips, F3: Pareto, F7: regime scatter)