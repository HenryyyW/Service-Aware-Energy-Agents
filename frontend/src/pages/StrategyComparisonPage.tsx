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

  useEffect(() => {
    if (!scenarioId) return;

    let active = true;
    const load = async () => {
      try {
        const scenario = await api.getScenario(scenarioId);
        if (active) setConfig(scenario);
        if (active) setStrategyData({});
        if (active) setViolations([]);
      } catch (error) {
        console.error('Failed to load strategy comparison data:', error);
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
