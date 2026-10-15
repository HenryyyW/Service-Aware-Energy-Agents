"""Service-Aware Energy Agents package."""
from .schemas import *
from .simulation import CityLearnAdapter, PandapowerAdapter, SimulationCoupler
from .controllers import BaseController, RuleBasedController
from .evaluation import compute_all_metrics, compute_fairness_metrics, generate_report_plots

__version__ = "0.1.0"

__all__ = [
    # schemas (re-exported from schemas.__init__)
    # simulation
    "CityLearnAdapter",
    "PandapowerAdapter", 
    "SimulationCoupler",
    # controllers
    "BaseController",
    "RuleBasedController",
    # evaluation
    "compute_all_metrics",
    "compute_fairness_metrics",
    "generate_report_plots",
]