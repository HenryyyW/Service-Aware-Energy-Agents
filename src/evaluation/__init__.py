"""Evaluation module for metrics, fairness, and plotting."""
from .metrics import (
    compute_energy_metrics,
    compute_service_metrics,
    compute_grid_metrics,
    compute_agent_metrics,
    compute_all_metrics,
    calculate_gini_coefficient
)
from .fairness import (
    compute_fairness_metrics,
    compute_per_member_metrics,
    FairnessAnalyzer
)
from .plots import (
    plot_trajectories,
    plot_kpis,
    plot_grid_diagnostics,
    plot_comparison,
    generate_report_plots
)

__all__ = [
    # metrics
    "compute_energy_metrics",
    "compute_service_metrics", 
    "compute_grid_metrics",
    "compute_agent_metrics",
    "compute_all_metrics",
    "calculate_gini_coefficient",
    # fairness
    "compute_fairness_metrics",
    "compute_per_member_metrics",
    "FairnessAnalyzer",
    # plots
    "plot_trajectories",
    "plot_kpis",
    "plot_grid_diagnostics",
    "plot_comparison",
    "generate_report_plots",
]