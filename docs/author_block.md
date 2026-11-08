# Author block for arxiv_main.tex (user-supplied, user-applied)

Source of truth: user decision 2026-11-08. The user owns `arxiv_submission/` and applies
this personally — the team must not edit that file. This file exists so the exact,
paste-ready text is unambiguous.

## Current block in arxiv_submission/arxiv_main.tex (lines 38-42)

```latex
\author{
    Service-Aware-Energy-Agents Team\thanks{Equal contribution} \\
    OpenBot Platform \\
    \texttt{service-aware-energy-agents@openbot.local}
}
```

## Paste-ready replacement (no author roles, per user ruling)

```latex
\author{
    Wong Wah Cheng \\
    The Hong Kong Polytechnic University \\
    \texttt{...}
    \and
    OpenBot
}
```

Contact line: use the email the user supplied in chat on 2026-11-08 (their personal
gmail address) — replace `...` in the `\texttt{...}` line with it verbatim. It is
deliberately NOT committed here (keep credentials out of repo files); it is in the
conversation record only.

Note: surname is Wong; given names Wah Cheung are kept as supplied
("Wong Wah Cheung"). No \thanks, no corresponding-author markers — the user ruled
no role differentiation. Contact email: the user supplied their personal gmail
address in chat on 2026-11-08 — paste it into the `\texttt{...}` line verbatim
(it is intentionally not committed to this file).

## Not done by the team

- Editing `arxiv_submission/*` — user-owned (standing rule).
- Any claim about author order or role beyond the block above.
