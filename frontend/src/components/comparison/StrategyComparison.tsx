import { useState } from 'react';
import { StrategyPanel } from './StrategyPanel';
import type { ScenarioConfig } from '../../api/types';

/**
 * StrategyComparison - Four equal panels showing rule-based, MPC, single-agent-RL,
 * and multi-agent-RL strategies on the same community config.
 *
 * Metrics come from probe data (P1 corpus runs). Where a metric is not
 * available in the probe data, "no record" is shown per spec §6.
 *
 * Honest-failure rule: a strategy that did not converge or breached a hard
 * limit is rendered as a failed state, never hidden.
 */

const STRATEGIES: Array<{
  name: string;
  controller: string;
  shortName: string;
}> = [
  { name: 'Rule-Based', controller: 'rule_based', shortName: 'RB' },
  { name: 'MPC', controller: 'mpc', shortName: 'MPC' },
  { name: 'Single-Agent RL', controller: 'single_agent_rl', shortName: 'RL-1' },
  { name: 'Multi-Agent RL', controller: 'multi_agent_rl', shortName: 'RL-M' },
];

export interface StrategyComparisonProps {
  /** Probe data for the community config */
  config: ScenarioConfig;
  /** Strategy metrics keyed by controller name */
  strategyData: Record<string, {
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
    fallback_steps?: number;
    fallback_reason?: string;
  }>;
  /** Violations from probe data */
  violations?: Array<{
    element: string;
    elementType: string;
    value: number;
    limit: number;
    type: 'voltage' | 'loading';
  }>;
}

export function StrategyComparison({ config, strategyData, violations }: StrategyComparisonProps) {
  const [currentTimestep, setCurrentTimestep] = useState(0);
  const maxTimestep = config.timestep_minutes ? 24 * 60 / config.timestep_minutes - 1 : 95;

  // Build strategies array with fallback data
  const strategies = STRATEGIES.map((s) => ({
    ...s,
    data: strategyData[s.controller] || {
      status: 'pending' as const,
      total_cost: undefined,
      carbon_emissions_kg: undefined,
      grid_import_kwh: undefined,
      grid_export_kwh: undefined,
      import_limit_kwh: config.community_import_limit_kw,
      export_limit_kwh: config.community_export_limit_kw,
      voltage_violations_count: undefined,
      max_voltage_pu: undefined,
      fallback_steps: undefined,
      fallback_reason: undefined,
    },
  }));

  const handleTimeChange = (value: number) => {
    setCurrentTimestep(value);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-border/30 bg-surface/50">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display font-semibold text-heading-1 text-text">Strategy Comparison</h1>
            <p className="text-caption text-text-muted">
              Same community config, four strategies side by side
            </p>
          </div>
        </div>
      </div>

      {/* Four strategy panels */}
      <div className="flex-1 overflow-auto p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 min-h-[600px]">
          {strategies.map((s) => (
            <StrategyPanel
              key={s.controller}
              strategy={{
                name: s.name,
                controller: s.controller,
                total_cost: s.data.total_cost,
                carbon_emissions_kg: s.data.carbon_emissions_kg,
                grid_import_kwh: s.data.grid_import_kwh,
                grid_export_kwh: s.data.grid_export_kwh,
                import_limit_kwh: s.data.import_limit_kwh,
                export_limit_kwh: s.data.export_limit_kwh,
                voltage_violations_count: s.data.voltage_violations_count,
                max_voltage_pu: s.data.max_voltage_pu,
                run_id: s.data.run_id,
                status: s.data.status,
                power_flow_converged: s.data.power_flow_converged,
                fallback_steps: s.data.fallback_steps,
                fallback_reason: s.data.fallback_reason,
              }}
              buildings={config.buildings ?? []}
              violations={violations}
              currentTimestep={currentTimestep}
              maxTimestep={maxTimestep}
            />
          ))}
        </div>
      </div>

      {/* Shared time scrubber */}
      <div className="border-t border-border/30 bg-surface/50 p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-caption text-text-muted">Time Scrubber (shared across all strategies)</span>
          <span className="text-[10px] text-text-muted">
            {currentTimestep} / {maxTimestep}
          </span>
        </div>
        <div className="relative h-4">
          <div
            className="absolute left-1/2 top-1/2 w-1 h-full bg-border -translate-x-1/2 -translate-y-1/2"
            style={{ left: `${(currentTimestep / maxTimestep) * 100}%` }}
          />
          <input
            type="range"
            min="0"
            max={maxTimestep}
            step="1"
            value={currentTimestep}
            onChange={(e) => handleTimeChange(Number(e.target.value))}
            className="w-full h-2 bg-surface rounded-lg accent-sun"
          />
        </div>
        <div className="flex justify-between mt-1 text-[10px] text-text-muted">
          <span>Timestep 0</span>
          <span className="text-center">Timestep {Math.floor(maxTimestep / 2)}</span>
          <span>Timestep {maxTimestep}</span>
        </div>
      </div>
    </div>
  );
}
