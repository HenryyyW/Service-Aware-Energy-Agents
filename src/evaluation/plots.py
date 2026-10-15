"""Plotting functions for experiment results and reports."""
from typing import List, Dict, Any, Optional
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import os


def plot_trajectories(
    history: List[Dict[str, Any]],
    output_path: str,
    scenario_config: Dict[str, Any]
):
    """Plot key trajectories from simulation history."""
    fig, axes = plt.subplots(4, 1, figsize=(12, 16), sharex=True)
    timesteps = [h['timestep'] for h in history]
    
    # 1. Net demand per building
    ax = axes[0]
    for h in history:
        for key, value in h.get('observations', {}).items():
            if 'net_electricity_consumption' in key:
                building = key.replace('_net_electricity_consumption', '')
                if building not in ax.lines:
                    ax.plot([], [], label=building)
                # This is simplified - would need to track per building over time
    ax.set_ylabel('Net Demand (kW)')
    ax.set_title('Building Net Electricity Consumption')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 2. PV generation
    ax = axes[1]
    for h in history:
        for key, value in h.get('observations', {}).items():
            if 'solar_generation' in key:
                building = key.replace('_solar_generation', '')
                if building not in ax.lines:
                    ax.plot([], [], label=building)
    ax.set_ylabel('PV Generation (kW)')
    ax.set_title('Rooftop PV Generation')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 3. Battery SOC
    ax = axes[2]
    for h in history:
        for key, value in h.get('observations', {}).items():
            if 'battery_soc' in key:
                building = key.replace('_battery_soc', '')
                if building not in ax.lines:
                    ax.plot([], [], label=building)
    ax.set_ylabel('State of Charge')
    ax.set_title('Battery State of Charge')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 4. Grid import/export
    ax = axes[3]
    grid_import = []
    grid_export = []
    for h in history:
        imp = sum(a['value_kw'] for a in h.get('applied_actions', []) 
                  if a.get('action_type') == 'grid_import' and a['value_kw'] > 0)
        exp = sum(-a['value_kw'] for a in h.get('applied_actions', []) 
                  if a.get('action_type') == 'grid_export' and a['value_kw'] < 0)
        grid_import.append(imp)
        grid_export.append(exp)
    ax.plot(timesteps, grid_import, label='Grid Import', color='red')
    ax.plot(timesteps, grid_export, label='Grid Export', color='green')
    ax.set_ylabel('Power (kW)')
    ax.set_xlabel('Timestep')
    ax.set_title('Community Grid Exchange')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_kpis(
    kpis: Dict[str, float],
    baseline_kpis: Optional[Dict[str, float]] = None,
    output_path: str = "kpis.png"
):
    """Plot KPI comparison."""
    categories = list(kpis.keys())
    values = list(kpis.values())
    
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(categories))
    width = 0.35
    
    ax.bar(x - width/2, values, width, label='Agent', color='steelblue')
    
    if baseline_kpis:
        baseline_values = [baseline_kpis.get(c, 0) for c in categories]
        ax.bar(x + width/2, baseline_values, width, label='Baseline', color='lightcoral')
    
    ax.set_ylabel('Value')
    ax.set_title('KPI Comparison')
    ax.set_xticks(x)
    ax.set_xticklabels(categories, rotation=45, ha='right')
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_grid_diagnostics(
    history: List[Dict[str, Any]],
    output_path: str
):
    """Plot grid diagnostics over time."""
    fig, axes = plt.subplots(3, 1, figsize=(12, 12), sharex=True)
    timesteps = [h['timestep'] for h in history]
    
    # Voltage profile
    ax = axes[0]
    voltages = []
    for h in history:
        v_profile = h.get('grid_diagnostics', {}).get('voltage_profile', {})
        if v_profile:
            voltages.append(np.mean(list(v_profile.values())))
        else:
            voltages.append(1.0)
    ax.plot(timesteps, voltages, 'b-', label='Avg Voltage')
    ax.axhline(y=1.05, color='r', linestyle='--', label='Upper Limit (1.05)')
    ax.axhline(y=0.95, color='r', linestyle='--', label='Lower Limit (0.95)')
    ax.axhline(y=1.0, color='k', linestyle='-', alpha=0.3)
    ax.set_ylabel('Voltage (pu)')
    ax.set_title('Bus Voltage Profile')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Line loading
    ax = axes[1]
    line_loadings = []
    for h in history:
        l_profile = h.get('grid_diagnostics', {}).get('loading_profile', {}).get('lines', {})
        if l_profile:
            line_loadings.append(np.max(list(l_profile.values())) * 100)
        else:
            line_loadings.append(0)
    ax.plot(timesteps, line_loadings, 'g-', label='Max Line Loading')
    ax.axhline(y=100, color='r', linestyle='--', label='Limit (100%)')
    ax.set_ylabel('Loading (%)')
    ax.set_title('Line Loading')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Transformer loading
    ax = axes[2]
    trafo_loadings = []
    for h in history:
        t_profile = h.get('grid_diagnostics', {}).get('loading_profile', {}).get('trafos', {})
        if t_profile:
            trafo_loadings.append(np.max(list(t_profile.values())) * 100)
        else:
            trafo_loadings.append(0)
    ax.plot(timesteps, trafo_loadings, 'm-', label='Max Transformer Loading')
    ax.axhline(y=100, color='r', linestyle='--', label='Limit (100%)')
    ax.set_ylabel('Loading (%)')
    ax.set_xlabel('Timestep')
    ax.set_title('Transformer Loading')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_comparison(
    results: List[Dict[str, Any]],
    metric_names: List[str],
    output_path: str
):
    """Plot comparison between multiple experiment runs."""
    fig, axes = plt.subplots(len(metric_names), 1, figsize=(10, 4*len(metric_names)), squeeze=False)
    
    run_names = [r.get('run_id', f'Run {i}') for i, r in enumerate(results)]
    x = np.arange(len(run_names))
    width = 0.8 / len(metric_names)
    
    for i, metric in enumerate(metric_names):
        ax = axes[i, 0]
        values = [r.get('metrics', {}).get(metric, 0) for r in results]
        ax.bar(x, values, width, label=metric)
        ax.set_ylabel(metric)
        ax.set_title(f'{metric} Comparison')
        ax.set_xticks(x)
        ax.set_xticklabels(run_names, rotation=45, ha='right')
        ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_per_member_fairness(
    per_member: List[Dict[str, Any]],
    output_path: str
):
    """Plot per-member fairness metrics."""
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    
    members = [m['member_id'] for m in per_member]
    
    # Cost
    ax = axes[0, 0]
    costs = [m.get('total_cost', 0) for m in per_member]
    ax.bar(members, costs, color='steelblue')
    ax.set_ylabel('Total Cost ($)')
    ax.set_title('Per-Member Total Cost')
    ax.tick_params(axis='x', rotation=45)
    ax.grid(True, alpha=0.3, axis='y')
    
    # PV self-consumption
    ax = axes[0, 1]
    pv_sc = [m.get('pv_self_consumption_kwh', 0) for m in per_member]
    ax.bar(members, pv_sc, color='orange')
    ax.set_ylabel('PV Self-Consumption (kWh)')
    ax.set_title('Per-Member PV Self-Consumption')
    ax.tick_params(axis='x', rotation=45)
    ax.grid(True, alpha=0.3, axis='y')
    
    # Battery cycles
    ax = axes[1, 0]
    cycles = [m.get('battery_cycles', 0) for m in per_member]
    ax.bar(members, cycles, color='green')
    ax.set_ylabel('Battery Cycles')
    ax.set_title('Per-Member Battery Cycling')
    ax.tick_params(axis='x', rotation=45)
    ax.grid(True, alpha=0.3, axis='y')
    
    # Service score
    ax = axes[1, 1]
    scores = [m.get('service_score', 1.0) for m in per_member]
    ax.bar(members, scores, color='purple')
    ax.set_ylabel('Service Score (0-1)')
    ax.set_title('Per-Member Service Score')
    ax.tick_params(axis='x', rotation=45)
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim(0, 1.1)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def generate_report_plots(
    history: List[Dict[str, Any]],
    kpis: Dict[str, float],
    per_member: List[Dict[str, Any]],
    output_dir: str,
    baseline_kpis: Optional[Dict[str, Any]] = None,
    scenario_config: Optional[Dict[str, Any]] = None
):
    """Generate all plots for a report."""
    os.makedirs(output_dir, exist_ok=True)
    
    plot_trajectories(history, os.path.join(output_dir, 'trajectories.png'), scenario_config or {})
    plot_kpis(kpis, baseline_kpis, os.path.join(output_dir, 'kpis.png'))
    plot_grid_diagnostics(history, os.path.join(output_dir, 'grid_diagnostics.png'))
    plot_per_member_fairness(per_member, os.path.join(output_dir, 'fairness.png'))
    
    print(f"Plots saved to {output_dir}")