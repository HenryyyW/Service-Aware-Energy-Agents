import { Zap, Settings, Brain, Shield } from '../../utils/lucide';
import { useEffect, useState } from 'react';
import { ComplianceChip } from './ComplianceChip';
import { MetricCell } from './MetricCell';
import { StrategyMap } from './StrategyMap';
import { api } from '../../api/client';
import type { TimeStepData } from '../../api/types';

export interface StrategyPanelProps {
  strategy: {
    name: string;
    controller: string;
    total_cost?: number | string;
    carbon_emissions_kg?: number | string;
    grid_import_kwh?: number | string;
    grid_export_kwh?: number | string;
    import_limit_kwh?: number | string;
    export_limit_kwh?: number | string;
    voltage_violations_count?: number | string;
    max_voltage_pu?: number | string;
    run_id?: string;
    status: 'completed' | 'failed' | 'pending';
    power_flow_converged?: boolean;
    // OPF fallback marker from the backend (lmp_opf_fallback_steps / reason).
    // Shown only when the backend provides it; otherwise "no record" so it is
    // never mistaken for a real strategy difference.
    fallback_steps?: number;
    fallback_reason?: string;
  };
  buildings: Array<{
    building_id: string;
    building_type?: string;
    location?: { lat: number; lon: number };
  }>;
  violations?: Array<{
    element: string;
    elementType: string;
    value: number;
    limit: number;
    type: 'voltage' | 'loading';
  }>;
  currentTimestep: number;
  maxTimestep: number;
}

const STRATEGY_ICONS: Record<string, any> = {
  rule_based: Zap,
  mpc: Settings,
  single_agent_rl: Brain,
  multi_agent_rl: Shield,
};

export function StrategyPanel({ strategy, buildings, violations, currentTimestep, maxTimestep }: StrategyPanelProps) {
  const Icon = STRATEGY_ICONS[strategy.controller] || Zap;

  // Dispatch trace for this strategy's run (best-effort; the run may not have
  // registered trajectory data, in which case we show an explicit empty state).
  const [trajectories, setTrajectories] = useState<TimeStepData[]>([]);

  useEffect(() => {
    if (!strategy.run_id || strategy.status !== 'completed') return;
    let active = true;
    api.getTrajectories(strategy.run_id).then((data: TimeStepData[]) => {
      if (active) setTrajectories(data);
    });
    return () => { active = false; };
  }, [strategy.run_id, strategy.status]);

  // Compliance logic per spec §5
  const isFailed =
    strategy.status !== 'completed' ||
    (typeof strategy.grid_import_kwh === 'number' &&
      typeof strategy.import_limit_kwh === 'number' &&
      strategy.grid_import_kwh > strategy.import_limit_kwh) ||
    (typeof strategy.grid_export_kwh === 'number' &&
      typeof strategy.export_limit_kwh === 'number' &&
      strategy.grid_export_kwh > strategy.export_limit_kwh) ||
    (typeof strategy.voltage_violations_count === 'number' && strategy.voltage_violations_count > 0);

  const isWarning =
    !isFailed &&
    ((typeof strategy.grid_import_kwh === 'number' &&
      typeof strategy.import_limit_kwh === 'number' &&
      strategy.grid_import_kwh > strategy.import_limit_kwh * 0.95) ||
      (typeof strategy.grid_export_kwh === 'number' &&
        typeof strategy.export_limit_kwh === 'number' &&
        strategy.grid_export_kwh > strategy.export_limit_kwh * 0.95) ||
      strategy.power_flow_converged === false);

  const complianceStatus: 'compliant' | 'warning' | 'failed' = isFailed ? 'failed' : isWarning ? 'warning' : 'compliant';

  return (
    <div className="glass-card overflow-hidden flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-3 bg-surface/50 border-b border-border/30">
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-text-muted" />
          <h4 className="font-body font-medium text-body-sm text-text">{strategy.name}</h4>
        </div>
        <ComplianceChip status={complianceStatus} />
      </div>

      {/* KPI Strip */}
      <div className="grid grid-cols-3 gap-2 p-3 bg-surface/30">
        <MetricCell
          label="Cost"
          value={strategy.total_cost}
          unit="$"
          linkHref={strategy.run_id ? `/runs/${strategy.run_id}/report` : undefined}
          linkLabel={`Run ${strategy.run_id} report`}
        />
        <MetricCell
          label="Carbon"
          value={strategy.carbon_emissions_kg}
          unit="kg CO₂"
          linkHref={strategy.run_id ? `/runs/${strategy.run_id}/report` : undefined}
          linkLabel={`Run ${strategy.run_id} report`}
        />
        <MetricCell
          label="Grid Import"
          value={strategy.grid_import_kwh}
          unit="kWh"
          limit={strategy.import_limit_kwh}
          linkHref={strategy.run_id ? `/runs/${strategy.run_id}/report` : undefined}
          linkLabel={`Run ${strategy.run_id} report`}
        />
        <MetricCell
          label="Grid Export"
          value={strategy.grid_export_kwh}
          unit="kWh"
          limit={strategy.export_limit_kwh}
          linkHref={strategy.run_id ? `/runs/${strategy.run_id}/report` : undefined}
          linkLabel={`Run ${strategy.run_id} report`}
        />
      </div>

      {/* Controller fallback — labelled per strategy comparison semantics.
           Shows controller_type, fallback_steps/total_steps, fallback_reason,
           and the effective controller when any step fell back to rule_based. */}
      <div className="p-3 border-b border-border/30 bg-surface/50">
        <div className="flex items-center justify-between mb-1">
          <h5 className="text-caption text-text-muted">Controller Fallback</h5>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] text-text-muted">Controller: {strategy.controller}</span>
          {strategy.fallback_steps !== undefined ? (
            <>
              <span className="badge badge-violation text-[10px]">
                {strategy.fallback_steps}/{maxTimestep + 1} step{strategy.fallback_steps !== 1 ? 's' : ''}
              </span>
              {strategy.fallback_reason && (
                <span className="text-caption text-text-muted">{strategy.fallback_reason}</span>
              )}
              {strategy.fallback_steps > 0 && (
                <span className="text-caption text-violation">Effective controller: rule_based (via fallback)</span>
              )}
            </>
          ) : (
            <span className="text-caption text-text-muted">無紀錄 / no record</span>
          )}
        </div>
      </div>

      {/* Map */}
      <div className="flex-1 p-3 border-b border-border/30">
        <div className="flex items-center justify-between mb-2">
          <h5 className="text-caption text-text-muted">Spatial Layout</h5>
          <span className="text-[10px] text-text-muted">{buildings.length} buildings</span>
        </div>
        <StrategyMap buildings={buildings} violations={violations} />
      </div>

      {/* Dispatch Trace */}
      <div className="p-3 border-t border-border/30 bg-surface/50">
        <div className="flex items-center justify-between">
          <h5 className="text-caption text-text-muted">Dispatch Trace</h5>
          <span className="text-[10px] text-text-muted">{currentTimestep} / {maxTimestep}</span>
        </div>
        <div className="h-24 bg-surface/50 rounded-lg border border-border/30 flex items-center justify-center">
          {trajectories.length === 0 ? (
            <span className="text-[10px] text-text-muted">No dispatch trace data for this run</span>
          ) : (
            <div className="flex flex-col gap-1 text-[10px] text-text-muted">
              <span>Battery: {dispatchKw('battery').toFixed(1)} kW</span>
              <span>EV: {dispatchKw('ev').toFixed(1)} kW</span>
              <span>Flexible load: {dispatchKw('flex').toFixed(1)} kW</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  function dispatchKw(kind: 'battery' | 'ev' | 'flex'): number {
    const step = trajectories.find(t => t.timestep === currentTimestep);
    const actions = step?.applied_actions ?? [];
    let total = 0;
    for (const a of actions) {
      if (kind === 'battery' && (a.action_type === 'battery_charge' || a.action_type === 'battery_discharge')) {
        total += a.value_kw ?? 0;
      } else if (kind === 'ev' && a.action_type === 'ev_charge') {
        total += a.value_kw ?? 0;
      } else if (kind === 'flex' && a.action_type === 'flexible_load') {
        total += a.value_kw ?? 0;
      }
    }
    return total;
  }
}
