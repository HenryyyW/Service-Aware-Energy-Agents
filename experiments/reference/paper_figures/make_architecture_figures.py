#!/usr/bin/env python3
"""Publication figures: system architecture + agent workflow (SAEA paper).

Source of truth (verify against the code, not this file):
- `src/simulation/coupling.py`      -- SimulationCoupler.step: CityLearn -> pandapower loop
- `src/simulation/{market,settlement}.py` -- pool/TOU, LMP clearing, P2P matching, settlement
- `src/controllers/`                -- rule_based, mpc, centralized, multi_agent, rl, llm_agent
- `src/coordination/`               -- building/battery/ev/flexible_load agents + aggregator
- `src/agents/multi_agent_loop.py`  -- planner -> coder -> executor -> verifier -> reporter
- `src/agents/{sandbox,repair_loop,verifier}.py` -- sandbox tests, repair loop, repair acceptance
- `backend/app/main.py`, `routers/agent.py`      -- /api + /ws, task state (Redis or in-memory)

Emits vector PDF + SVG and a 600 dpi PNG preview into --out.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon  # noqa: E402

from experiments.paper_figures import style  # noqa: E402

INK = "#212121"
MUTED = "#5f6b6b"
ACCENT = "#005e60"

# (fill, edge) per node kind — low-saturation, grayscale-distinguishable.
COL = {
    "sim": ("#eef4f4", "#005e60"),
    "ctrl": ("#f6f7f7", "#5f6b6b"),
    "agent": ("#eaf4f3", "#0a7d72"),
    "pers": ("#f4f4f4", "#9a9a9a"),
    "surf": ("#eef2f8", "#4a6fa5"),
    "llm": ("#f7f2ea", "#b7791f"),
}


def _box(ax, x, y, w, h, title, lines=(), kind="ctrl", fs=6.4, tfs=7.0):
    fc, ec = COL[kind]
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.4,rounding_size=1.4",
            linewidth=0.9,
            edgecolor=ec,
            facecolor=fc,
        )
    )
    cx = x + w / 2
    ax.text(
        cx,
        y + h - 2.2,
        title,
        ha="center",
        va="top",
        fontsize=tfs,
        fontweight="bold",
        color=INK,
    )
    if lines:
        ax.text(
            cx,
            y + h - 5.6,
            "\n".join(lines),
            ha="center",
            va="top",
            fontsize=fs,
            color=MUTED,
            linespacing=1.3,
        )
    return {
        "cx": cx,
        "cy": y + h / 2,
        "top": y + h,
        "bot": y,
        "left": x,
        "right": x + w,
        "x": x,
        "y": y,
        "w": w,
        "h": h,
    }


def _arrow(
    ax, p, q, color=ACCENT, ls="-", lw=0.9, rad=0.0, label=None, ldy=1.4, lx=0.0
):
    ax.add_patch(
        FancyArrowPatch(
            p,
            q,
            arrowstyle="-|>",
            mutation_scale=7,
            linewidth=lw,
            color=color,
            linestyle=ls,
            shrinkA=2.0,
            shrinkB=2.0,
            connectionstyle=f"arc3,rad={rad}",
        )
    )
    if label:
        ax.text(
            (p[0] + q[0]) / 2 + lx,
            (p[1] + q[1]) / 2 + ldy,
            label,
            ha="center",
            va="bottom",
            fontsize=5.8,
            color=MUTED,
        )


def _elbow(ax, pts, color="#0a7d72", ls="--", lw=0.9):
    """Orthogonal polyline with an arrowhead at the last point (for retry rails)."""
    ax.plot(
        [p[0] for p in pts],
        [p[1] for p in pts],
        color=color,
        ls=ls,
        lw=lw,
        solid_capstyle="round",
        zorder=1,
    )
    ax.annotate(
        "",
        xy=pts[-1],
        xytext=pts[-2],
        arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, shrinkA=0, shrinkB=0),
    )


def _diamond(ax, cx, cy, w, h, text, fs=6.0):
    ax.add_patch(
        Polygon(
            [(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)],
            closed=True,
            linewidth=0.9,
            edgecolor="#5f6b6b",
            facecolor="#fbfbfb",
        )
    )
    ax.text(
        cx, cy, text, ha="center", va="center", fontsize=fs, color=INK, linespacing=1.2
    )
    return {
        "cx": cx,
        "cy": cy,
        "top": cy + h / 2,
        "bot": cy - h / 2,
        "left": cx - w / 2,
        "right": cx + w / 2,
    }


def _canvas(figsize):
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    return fig, ax


def _save(fig, out_dir: Path, stem: str) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for suffix in ("pdf", "svg", "png"):
        p = out_dir / f"{stem}.{suffix}"
        fig.savefig(p, dpi=600 if suffix == "png" else None)
        paths.append(str(p))
    plt.close(fig)
    return paths


def figure_architecture(out_dir: Path) -> list[str]:
    """Closed-loop co-simulation, control, agent workflow, persistence and surfaces."""
    fig, ax = _canvas(style.double_col(4.9))

    # Surfaces (top)
    api = _box(
        ax,
        3,
        84,
        46,
        13,
        "FastAPI service",
        [
            "/api/* (scenarios, simulations, agent,",
            "reports, compare, network)  ·  /ws, /ws/simulation,",
            "/ws/agent, /ws/p2p",
        ],
        kind="surf",
    )
    ui = _box(
        ax,
        53,
        84,
        44,
        13,
        "React frontend",
        ["community canvas · time player ·", "agent workspace · reports · comparison"],
        kind="surf",
    )

    # Agent workflow row
    agent_y, agent_h = 64, 15
    ag = _box(
        ax,
        3,
        agent_y,
        52,
        agent_h,
        "Agent workflow  (LLM-grounded)",
        [
            "planner  →  coder  →  executor (sandbox: syntax + unit tests)",
            "→  verifier (full-sim before/after physics, service, grid)",
            "→  reporter (Markdown + JSON)     repair loop ≤ max_iterations",
        ],
        kind="agent",
    )
    llm = _box(
        ax,
        58,
        agent_y,
        39,
        agent_h,
        "LLM backend",
        ["local / Ollama / hosted API", "(api.py, local.py, remote.py, fallback.py)"],
        kind="llm",
    )

    # Control + coordination row
    ctrl = _box(
        ax,
        3,
        46,
        52,
        14,
        "Control & coordination",
        [
            "rule_based · mpc · centralized · multi_agent · rl · llm_agent (±verified)",
            "building/battery/EV/flexible-load agents + aggregator → kW requests",
        ],
        kind="ctrl",
    )
    mkt = _box(
        ax,
        58,
        46,
        39,
        14,
        "Markets & settlement",
        [
            "pool / TOU · LMP clearing",
            "P2P matching → residual to pool",
            "settlement gate (invar.",
        ],
        kind="ctrl",
    )

    # Closed co-simulation loop
    cl = _box(
        ax,
        3,
        22,
        42,
        20,
        "CityLearn v3 adapter",
        [
            "buildings, rooftop PV, battery,",
            "EVs, flexible loads →",
            "observations + building powers",
        ],
        kind="sim",
    )
    ppp = _box(
        ax,
        55,
        22,
        42,
        20,
        "pandapower adapter",
        [
            "distribution network power flow",
            "voltage / line / transformer loading",
            "→ grid diagnostics (violations)",
        ],
        kind="sim",
    )
    ax.text(
        50,
        42,
        "closed\nloop",
        ha="center",
        va="center",
        fontsize=6.2,
        color=ACCENT,
        style="italic",
        linespacing=1.2,
    )

    # Persistence
    _box(
        ax,
        3,
        4,
        42,
        13,
        "Disk artifacts",
        ["results/<run>/  (trajectories.jsonl,", "grid_diagnostics.jsonl, reports)"],
        kind="pers",
    )
    _box(
        ax,
        55,
        4,
        42,
        13,
        "Task state",
        ["Redis (fallback: in-memory) · P2P ledger", "· settlement records"],
        kind="pers",
    )

    # Arrows
    # UI <-> API
    _arrow(ax, (ui["left"], ui["cy"]), (api["right"], api["cy"]), color=MUTED, lw=0.8)
    # API dispatches a task/run into the agent workflow
    _arrow(
        ax,
        (api["cx"], api["bot"]),
        (ag["cx"], ag["top"]),
        label="task / run",
        lx=13,
        ldy=-0.6,
    )
    # agent writes controller code -> control layer
    _arrow(
        ax, (ag["cx"], ag["bot"]), (ctrl["cx"], ctrl["top"]), label="controller code"
    )
    # LLM backend drives the agent loop
    _arrow(
        ax, (llm["left"], llm["cy"]), (ag["right"], ag["cy"]), color="#b7791f", lw=0.8
    )
    # control -> markets (price signal)
    _arrow(
        ax,
        (ctrl["right"], ctrl["cy"] + 3),
        (mkt["left"], mkt["cy"] + 3),
        color=MUTED,
        ls="--",
        label="prices",
    )
    # control -> co-simulation (kW actions)
    _arrow(ax, (ctrl["cx"], ctrl["bot"]), (cl["cx"], cl["top"]), label="kW actions")
    # CityLearn -> pandapower (building powers), pandapower -> CityLearn (diagnostics)
    _arrow(
        ax,
        (cl["right"], cl["cy"] + 4),
        (ppp["left"], ppp["cy"] + 4),
        label="building powers",
    )
    _arrow(
        ax,
        (ppp["left"], ppp["cy"] - 4),
        (cl["right"], cl["cy"] - 4),
        color="#0a7d72",
        ls="--",
        label="grid diagnostics",
    )
    # diagnostics feed back to control (re-dispatch) — the closed loop
    _arrow(
        ax,
        (ppp["cx"], ppp["top"] - 1),
        (ctrl["right"] - 14, ctrl["bot"]),
        color="#0a7d72",
        ls="--",
        rad=0.22,
        label="re-dispatch",
    )
    # persistence (short dashed drops into the bottom band)
    _arrow(ax, (cl["cx"], cl["bot"]), (cl["cx"], 17), color=MUTED, ls="--")
    _arrow(ax, (ppp["cx"], ppp["bot"]), (ppp["cx"], 17), color=MUTED, ls="--")

    fig.tight_layout(pad=0.2)
    return _save(fig, out_dir, "fig_architecture")


def figure_agent_workflow(out_dir: Path) -> list[str]:
    """Algorithm flow: plan -> code -> execute (sandbox) -> verify -> repair -> report."""
    fig, ax = _canvas(style.single_col(5.2))

    bx, bw = 27, 69  # boxes start at x=27, leaving a left gutter for retry rails
    cx = bx + bw / 2

    def row(y, h, title, lines, kind="agent"):
        return _box(ax, bx, y, bw, h, title, lines, kind=kind, fs=5.9, tfs=6.6)

    start = row(
        89,
        8,
        "Task + grid diagnostics",
        ["Scenario E violations / KPI targets"],
        "ctrl",
    )
    plan = row(78, 8, "Planner", ["parse diagnostics → structured repair plan"])
    code = row(67, 8, "Coder", ["AST-based controller patches"])
    ex = row(
        53,
        10,
        "Executor — sandbox",
        ["syntax check + unit tests", "(subprocess: 60 s, 512 MB)"],
    )
    d1 = _diamond(ax, cx, 46, 34, 8, "tests pass?")
    ver = row(
        28,
        11,
        "Verifier",
        [
            "full-sim before ↔ after metrics:",
            "physics · service · grid",
            "(violations resolved, KPIs not regressed)",
        ],
    )
    d2 = _diamond(ax, cx, 19, 40, 8, "violations resolved?")
    rep = row(6, 8, "Reporter", ["Markdown + JSON with evidence"], "pers")

    _arrow(ax, (start["cx"], start["bot"]), (plan["cx"], plan["top"]))
    _arrow(ax, (plan["cx"], plan["bot"]), (code["cx"], code["top"]))
    _arrow(ax, (code["cx"], code["bot"]), (ex["cx"], ex["top"]))
    _arrow(ax, (ex["cx"], ex["bot"]), (d1["cx"], d1["top"]))
    _arrow(
        ax,
        (d1["cx"], d1["bot"]),
        (ver["cx"], ver["top"]),
        lx=2.5,
        ldy=-1.5,
        label="yes",
    )
    _arrow(ax, (ver["cx"], ver["bot"]), (d2["cx"], d2["top"]))
    _arrow(
        ax,
        (d2["cx"], d2["bot"]),
        (rep["cx"], rep["top"]),
        lx=2.5,
        ldy=-1.5,
        label="yes",
    )

    # Retry rails in the left gutter (orthogonal, rotated labels so nothing overlaps boxes).
    _elbow(
        ax,
        [
            (d1["left"], d1["cy"]),
            (8, d1["cy"]),
            (8, code["cy"]),
            (code["left"], code["cy"]),
        ],
    )
    ax.text(
        6.4,
        (d1["cy"] + code["cy"]) / 2,
        "no — repair ≤ max_iterations",
        rotation=90,
        ha="center",
        va="center",
        fontsize=5.4,
        color=MUTED,
    )
    _elbow(
        ax,
        [
            (d2["left"], d2["cy"]),
            (16, d2["cy"]),
            (16, code["cy"] - 3),
            (code["left"], code["cy"] - 3),
        ],
    )
    ax.text(
        14.4,
        (d2["cy"] + code["cy"]) / 2,
        "no — re-prompt ≤ max_iterations",
        rotation=90,
        ha="center",
        va="center",
        fontsize=5.4,
        color=MUTED,
    )

    fig.tight_layout(pad=0.2)
    return _save(fig, out_dir, "fig_agent_workflow")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="experiments/figures", help="output directory")
    args = parser.parse_args(argv)
    out = Path(args.out)
    for group in (figure_architecture(out), figure_agent_workflow(out)):
        for path in group:
            print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
