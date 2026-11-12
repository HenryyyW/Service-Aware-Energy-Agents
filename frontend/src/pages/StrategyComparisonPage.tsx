import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { StrategyComparison } from '../components/comparison/StrategyComparison';
import { api } from '../api/client';
import type { ScenarioConfig } from '../api/types';

/**
 * Strategy Comparison Page
 *
 * Displays four strategy panels side by side on the same community config,
 * per spec docs/p2_strategy_comparison_design.md.
 *
 * Route: /comparison/strategy/:scenarioId
 *
 * Data source: probe corpus (probe_out_full16c) provides real scenario configs
 * and execution results. The frozen matrix record (83/67/0) provides comparison
 * numbers. Where a metric is not available, "no record" is shown per spec §6.
 */
export function StrategyComparisonPage() {
  const navigate = useNavigate();
  const { scenarioId } = useParams<{ scenarioId: string }>();
  const [config, setConfig] = useState<ScenarioConfig | null>(null);
  const [strategyData, setStrategyData] = useState<Record<string, any>>({});
  const [violations, setViolations] = useState<Array<{
    element: string;
    elementType: string;
    value: number;
    limit: number;
    type: 'voltage' | 'loading';
  }>>([]);

  const [runStatus, setRunStatus] = useState<Record<string, string>>({});
  const [runError, setRunError] = useState<string | null>(null);

  useEffect(() => {
    if (!scenarioId) return;

    let active = true;
    const load = async () => {
      try {
        const scenario = await api.getScenario(scenarioId);
        if (active) setConfig(scenario);
        // Four strategies on THIS config, same seed: start/reuse the runs,
        // then poll each run to a terminal state (the lifecycle states the
        // panel shows). Nothing is estimated - a run that has not finished
        // stays 'pending' and the failure reason is shown.
        const kickoff = await api.startStrategyComparison(scenarioId, { max_steps: 24 });
        if (!active) return;
        const runs: Record<string, string> = kickoff.runs || {};
        setRunStatus(
          Object.fromEntries(
            Object.entries(kickoff.strategy_data || {}).map(([k, v]: [string, any]) => [
              k,
              v?.status || 'pending',
            ])
          )
        );
        const deadline = Date.now() + 120_000;
        while (active && Date.now() < deadline) {
          const entries = await Promise.all(
            Object.entries(runs).map(async ([controller, runId]) => {
              const run = await api.getSimulationRun(runId);
              return [controller, run] as [string, any];
            })
          );
          if (!active) return;
          const data: Record<string, any> = {};
          const statuses: Record<string, string> = {};
          for (const [controller, run] of entries) {
            statuses[controller] = run.status;
            const energy = run.energy_metrics || {};
            const grid = run.grid_metrics || {};
            data[controller] = {
              total_cost: energy.total_cost,
              carbon_emissions_kg: energy.carbon_emissions_kg,
              grid_import_kwh: energy.grid_import_kwh,
              grid_export_kwh: energy.grid_export_kwh,
              import_limit_kw: scenario.community_import_limit_kw,
              export_limit_kw: scenario.community_export_limit_kw,
              voltage_violations_count: grid.voltage_violations_count,
              max_voltage_pu: grid.max_voltage_pu,
              power_flow_converged:
                (grid.power_flow_convergence_rate ?? 0) >= 1.0 ? true : grid.power_flow_convergence_rate != null ? false : undefined,
              run_id: run.run_id,
              status:
                run.status === 'completed'
                  ? 'completed'
                  : run.status === 'failed'
                    ? 'failed'
                    : 'pending',
              fallback_steps: run.controller_fallback_steps,
              fallback_reason: run.controller_fallback_reason,
            };
          }
          setStrategyData(data);
          setRunStatus(statuses);
          const viol: Array<any> = [];
          for (const [controller, run] of entries) {
            const grid = run.grid_metrics || {};
            if ((grid.voltage_violations_count || 0) > 0) {
              viol.push({
                element: `${controller} voltage excursion`,
                elementType: 'voltage',
                value: Math.round((grid.max_voltage_pu || 1) * 10000) / 10000,
                limit: 1.05,
                type: 'voltage',
              });
            }
          }
          setViolations(viol);
          if (entries.every(([, run]) => ['completed', 'failed'].includes(run.status))) break;
          await new Promise((r) => setTimeout(r, 2000));
        }
      } catch (error: any) {
        console.error('Failed to load strategy comparison data:', error);
        if (active) setRunError(error.response?.data?.detail || error.message || 'Comparison failed');
      }
    };

    load();
    return () => { active = false; };
  }, [scenarioId]);

  if (!config) {
    return (
      <div className="h-full flex flex-col p-4">
        <h1 className="font-display font-semibold text-heading-1 text-text">Strategy Comparison</h1>
        <p className="text-caption text-text-muted mt-2">Loading scenario configuration...</p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b border-border/30 bg-surface/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/scenarios')}
              className="btn-ghost p-2"
              aria-label="Back to scenarios"
            >
              <span className="text-text-muted/60">←</span>
            </button>
            <div>
              <h1 className="font-display font-semibold text-heading-1 text-text">Strategy Comparison</h1>
              <p className="text-caption text-text-muted">
                Same community config, four strategies side by side
              </p>
              {runError && (
                <p className="text-caption text-violation mt-1">
                  {runError} — retry the page; the runs are deduplicated by config and seed.
                </p>
              )}
              {Object.keys(runStatus).length > 0 && (
                <p className="text-caption text-text-muted mt-1">
                  {Object.entries(runStatus)
                    .map(([c, st]) => `${c}: ${st}`)
                    .join(' · ')}
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-4">
        <StrategyComparison
          config={config}
          strategyData={strategyData}
          violations={violations}
        />
      </div>
    </div>
  );
}
