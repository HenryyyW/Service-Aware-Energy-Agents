import { clsx } from 'clsx';
import { Download, CheckCircle, XCircle, BarChart2, GitCompare } from 'lucide-react';
import { isFeatureEnabled } from '../../config/featureFlags';
import { Button } from '../ui/Button';
import { Select } from '../ui/Input';
import { useSimulationStore } from '../../store/simulationStore';
import { useScenarioStore } from '../../store/scenarioStore';
import type { SimulationRun } from '../../api/types';

interface ScenarioComparisonProps {
  runA?: SimulationRun | null;
  runB?: SimulationRun | null;
  onSelectRunA?: (run: SimulationRun) => void;
  onSelectRunB?: (run: SimulationRun) => void;
  onClear?: () => void;
}

interface MetricConfig {
  key: string;
  label: string;
  unit: string;
  format: (v: number) => string;
  better: 'higher' | 'lower' | 'neutral';
}

const metricGroups: Array<{ label: string; metrics: MetricConfig[] }> = [
  {
    label: 'Energy & Cost',
    metrics: [
      { key: 'total_cost', label: 'Total Cost', unit: '$', format: (v: number) => `$${v.toLocaleString()}`, better: 'lower' },
      { key: 'grid_import_kwh', label: 'Grid Import', unit: 'kWh', format: (v: number) => `${v.toLocaleString()} kWh`, better: 'lower' },
      { key: 'grid_export_kwh', label: 'Grid Export', unit: 'kWh', format: (v: number) => `${v.toLocaleString()} kWh`, better: 'higher' },
      { key: 'peak_demand_kw', label: 'Peak Demand', unit: 'kW', format: (v: number) => `${v.toFixed(1)} kW`, better: 'lower' },
      { key: 'pv_self_consumption', label: 'PV Self-Consumption', unit: '%', format: (v: number) => `${(v * 100).toFixed(1)}%`, better: 'higher' },
      { key: 'pv_curtailment', label: 'PV Curtailment', unit: 'kWh', format: (v: number) => `${v.toLocaleString()} kWh`, better: 'lower' },
      { key: 'battery_throughput_kwh', label: 'Battery Throughput', unit: 'kWh', format: (v: number) => `${v.toLocaleString()} kWh`, better: 'neutral' },
      { key: 'carbon_emissions_kg', label: 'CO₂ Emissions', unit: 'kg', format: (v: number) => `${v.toLocaleString()} kg`, better: 'lower' },
    ],
  },
  {
    label: 'Service & Fairness',
    metrics: [
      { key: 'ev_completion_rate', label: 'EV Completion Rate', unit: '%', format: (v: number) => `${(v * 100).toFixed(1)}%`, better: 'higher' },
      { key: 'avg_ev_soc_at_departure', label: 'Avg EV SOC at Departure', unit: '%', format: (v: number) => `${(v * 100).toFixed(1)}%`, better: 'higher' },
      { key: 'comfort_violation_degree_hours', label: 'Comfort Violations', unit: '°C·h', format: (v: number) => `${v.toFixed(1)}`, better: 'lower' },
      { key: 'flexible_load_completion_rate', label: 'Flex Load Completion', unit: '%', format: (v: number) => `${(v * 100).toFixed(1)}%`, better: 'higher' },
      { key: 'dr_delivery_rate', label: 'DR Delivery Rate', unit: '%', format: (v: number) => `${(v * 100).toFixed(1)}%`, better: 'higher' },
      { key: 'gini_coefficient', label: 'Gini Coefficient', unit: '', format: (v: number) => `${v.toFixed(3)}`, better: 'lower' },
      { key: 'worst_member_savings', label: 'Worst Member Savings', unit: '$', format: (v: number) => `$${v.toFixed(0)}`, better: 'higher' },
    ],
  },
  {
    label: 'Grid Feasibility',
    metrics: [
      { key: 'power_flow_convergence_rate', label: 'PF Convergence', unit: '%', format: (v: number) => `${(v * 100).toFixed(1)}%`, better: 'higher' },
      { key: 'voltage_violations_count', label: 'Voltage Violations', unit: '', format: (v: number) => `${v}`, better: 'lower' },
      { key: 'max_voltage_pu', label: 'Max Voltage', unit: 'p.u.', format: (v: number) => `${v.toFixed(4)}`, better: 'neutral' },
      { key: 'min_voltage_pu', label: 'Min Voltage', unit: 'p.u.', format: (v: number) => `${v.toFixed(4)}`, better: 'neutral' },
      { key: 'max_line_loading_pct', label: 'Max Line Loading', unit: '%', format: (v: number) => `${v.toFixed(1)}%`, better: 'lower' },
      { key: 'max_transformer_loading_pct', label: 'Max Transformer Loading', unit: '%', format: (v: number) => `${v.toFixed(1)}%`, better: 'lower' },
    ],
  },
];

export function ScenarioComparison({
  runA,
  runB,
  onSelectRunA,
  onSelectRunB,
  onClear
}: ScenarioComparisonProps) {
  const { runs } = useSimulationStore();
  const { comparisonRunA, comparisonRunB, setComparisonRunA, setComparisonRunB, clearComparison } = useScenarioStore();

  const selectedA = runA || comparisonRunA;
  const selectedB = runB || comparisonRunB;

  const handleSelectA = (run: SimulationRun) => {
    setComparisonRunA(run);
    onSelectRunA?.(run);
  };

  const handleSelectB = (run: SimulationRun) => {
    setComparisonRunB(run);
    onSelectRunB?.(run);
  };

  const handleClear = () => {
    clearComparison();
    onClear?.();
  };

  const getMetricValue = (run: SimulationRun | null, key: string): number | null => {
    if (!run) return null;
    if (run.energy_metrics && key in run.energy_metrics) return (run.energy_metrics as any)[key];
    if (run.service_metrics && key in run.service_metrics) return (run.service_metrics as any)[key];
    if (run.grid_metrics && key in run.grid_metrics) return (run.grid_metrics as any)[key];
    return null;
  };

  const compareValues = (valA: number | null, valB: number | null, better: 'higher' | 'lower' | 'neutral') => {
    if (valA === null || valB === null) return { diff: null, better: null };
    const diff = ((valB - valA) / Math.abs(valA || 1)) * 100;
    let betterSide: 'A' | 'B' | 'equal' = 'equal';
    if (better === 'higher') betterSide = valB > valA ? 'B' : valA > valB ? 'A' : 'equal';
    else if (better === 'lower') betterSide = valB < valA ? 'B' : valA < valB ? 'A' : 'equal';
    return { diff, better: betterSide };
  };

  if (!selectedA && !selectedB) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-display font-semibold text-heading-2 text-text">Scenario Comparison</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <ScenarioSelector
            label="Scenario A"
            runs={runs}
            selected={selectedA}
            onSelect={handleSelectA}
            icon="A"
          />
          <ScenarioSelector
            label="Scenario B"
            runs={runs}
            selected={selectedB}
            onSelect={handleSelectB}
            icon="B"
          />
        </div>

        <div className="glass-card p-8 text-center text-text-muted">
          <GitCompare className="w-16 h-16 mx-auto mb-4 text-text-muted/30" />
          <p className="text-body">Select two scenarios to compare their performance metrics</p>
          <p className="text-caption mt-2">Choose from completed simulation runs</p>
        </div>
      </div>
    );
  }

  if (!selectedA || !selectedB) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-display font-semibold text-heading-2 text-text">Scenario Comparison</h2>
          <Button variant="ghost" size="icon" onClick={handleClear} aria-label="Clear comparison">
            <XCircle className="w-5 h-5" />
          </Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <ScenarioSelector
            label="Scenario A"
            runs={runs}
            selected={selectedA}
            onSelect={handleSelectA}
            icon="A"
          />
          <ScenarioSelector
            label="Scenario B"
            runs={runs}
            selected={selectedB}
            onSelect={handleSelectB}
            icon="B"
          />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="font-display font-semibold text-heading-2 text-text">Scenario Comparison</h2>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={handleClear} aria-label="Clear comparison">
            <XCircle className="w-5 h-5" />
          </Button>
          <Button variant="secondary" onClick={() => {}}>
            <Download className="w-4 h-4 mr-2" />
            Export Report
          </Button>
        </div>
      </div>

      {/* Scenario Selectors */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <SelectedScenarioCard
          run={selectedA}
          label="A"
          color="text-sun"
        />
        <SelectedScenarioCard
          run={selectedB}
          label="B"
          color="text-ev"
        />
      </div>

      {/* Comparison Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SummaryCard
          title="Energy Savings"
          value={calculateSavings(selectedA, selectedB)}
          unit="%"
          icon={<BarChart2 className="w-5 h-5" />}
        />
        <SummaryCard
          title="Service Improvement"
          value={calculateServiceImprovement(selectedA, selectedB)}
          unit="%"
          icon={<CheckCircle className="w-5 h-5" />}
        />
        <SummaryCard
          title="Grid Safety"
          value={calculateGridSafety(selectedA, selectedB)}
          unit="%"
          icon={<GitCompare className="w-5 h-5" />}
        />
      </div>

      {/* Detailed Metric Comparison */}
      <div className="space-y-4">
        {metricGroups.map((group) => (
          <div key={group.label} className="glass-card">
            <div className="p-4 border-b border-border/30">
              <h3 className="font-body font-medium text-body text-text">{group.label}</h3>
            </div>
            <div className="divide-y divide-border/30">
              {group.metrics.map((metric) => {
                const valA = getMetricValue(selectedA, metric.key);
                const valB = getMetricValue(selectedB, metric.key);
                const comparison = compareValues(valA, valB, metric.better as 'higher' | 'lower' | 'neutral');

                return (
                  <div key={metric.key} className="p-4 flex items-center justify-between hover:bg-white/5">
                    <div className="flex-1 min-w-0">
                      <p className="font-body text-body-sm text-text">{metric.label}</p>
                      <p className="text-caption text-text-muted">{metric.unit}</p>
                    </div>
                    <div className="flex items-center gap-4 ml-4">
                      <div className="text-right w-32">
                        <p className="font-mono text-data text-text">{valA !== null ? metric.format(valA) : '—'}</p>
                        <p className="text-caption text-text-muted">Scenario A</p>
                      </div>
                      <div className="flex items-center gap-2">
                        {comparison.diff !== null && (
                          <span className={clsx(
                            'font-mono text-data text-sm px-2 py-0.5 rounded',
                            comparison.better === 'B' ? 'bg-energy/20 text-energy' :
                            comparison.better === 'A' ? 'bg-violation/20 text-violation' :
                            'bg-text-muted/20 text-text-muted'
                          )}>
                            {comparison.better === 'B' ? '+' : ''}{comparison.diff.toFixed(1)}%
                          </span>
                        )}
                        {comparison.diff === null && (
                          <span className="text-caption text-text-muted">—</span>
                        )}
                      </div>
                      <div className="text-right w-32">
                        <p className="font-mono text-data text-text">{valB !== null ? metric.format(valB) : '—'}</p>
                        <p className="text-caption text-text-muted">Scenario B</p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Radar Chart - gated behind feature flag */}
      {isFeatureEnabled('radarChart') && (
        <div className="glass-card p-4">
          <h3 className="font-body font-medium text-body text-text mb-4">Radar Comparison</h3>
          <div className="aspect-square flex items-center justify-center bg-surface/50 rounded-lg border border-border/30">
            <div className="text-center text-text-muted">
              <BarChart2 className="w-12 h-12 mx-auto mb-2 text-text-muted/30" />
              <p>Radar chart visualization</p>
              <p className="text-caption mt-1">(Integrate with recharts or similar)</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ScenarioSelector({ label, runs, selected, onSelect, icon }: {
  label: string;
  runs: SimulationRun[];
  selected: SimulationRun | null;
  onSelect: (run: SimulationRun) => void;
  icon: string;
}) {
  return (
    <div className="glass-card p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="font-display font-semibold text-body text-text">{label}</span>
        <span className="badge badge-sun">{icon}</span>
      </div>
      {selected ? (
        <div className="space-y-2">
          <div className="flex items-center justify-between p-3 bg-surface/50 rounded-lg">
            <div>
              <p className="font-body font-medium text-body text-text">{selected.run_id}</p>
              <p className="text-caption text-text-muted">{selected.scenario_id} · {selected.controller_type}</p>
            </div>
            <Button variant="ghost" size="icon" onClick={() => onSelect({ ...selected, run_id: '' } as any)} aria-label="Clear">
              <XCircle className="w-4 h-4 text-text-muted" />
            </Button>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="p-2 bg-surface/50 rounded">
              <p className="font-mono text-data text-sun">
                {selected.energy_metrics?.total_cost ? `$${selected.energy_metrics.total_cost.toLocaleString()}` : '—'}
              </p>
              <p className="text-caption text-text-muted">Cost</p>
            </div>
            <div className="p-2 bg-surface/50 rounded">
              <p className="font-mono text-data text-energy">
                {selected.energy_metrics?.pv_self_consumption ? `${(selected.energy_metrics.pv_self_consumption * 100).toFixed(0)}%` : '—'}
              </p>
              <p className="text-caption text-text-muted">Self-Con.</p>
            </div>
            <div className="p-2 bg-surface/50 rounded">
              <p className="font-mono text-data text-battery">
                {selected.service_metrics?.ev_completion_rate ? `${(selected.service_metrics.ev_completion_rate * 100).toFixed(0)}%` : '—'}
              </p>
              <p className="text-caption text-text-muted">EV Ready</p>
            </div>
          </div>
        </div>
      ) : (
        <Select
          placeholder="Select scenario..."
          value=""
          onChange={(e) => {
            const run = runs.find(r => r.run_id === e.target.value);
            if (run) onSelect(run);
          }}
          options={runs.map(r => ({ value: r.run_id, label: `${r.run_id} (${r.controller_type})` }))}
        />
      )}
    </div>
  );
}

function SelectedScenarioCard({ run, label, color }: {
  run: SimulationRun;
  label: string;
  color: string;
}) {
  return (
    <div className="glass-card p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="font-display font-semibold text-body text-text">Scenario {label}</span>
        <span className={clsx('badge', color === 'text-sun' ? 'badge-sun' : 'badge-ev')}>{label}</span>
      </div>
      <div className="space-y-2">
        <div className="p-3 bg-surface/50 rounded-lg">
          <p className="font-body font-medium text-body text-text">{run.run_id}</p>
          <p className="text-caption text-text-muted">{run.scenario_id} · {run.controller_type}</p>
        </div>
        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="p-2 bg-surface/50 rounded">
            <p className="font-mono text-data text-sun">
              {run.energy_metrics?.total_cost ? `$${run.energy_metrics.total_cost.toLocaleString()}` : '—'}
            </p>
            <p className="text-caption text-text-muted">Cost</p>
          </div>
          <div className="p-2 bg-surface/50 rounded">
            <p className="font-mono text-data text-energy">
              {run.energy_metrics?.pv_self_consumption ? `${(run.energy_metrics.pv_self_consumption * 100).toFixed(0)}%` : '—'}
            </p>
            <p className="text-caption text-text-muted">Self-Con.</p>
          </div>
          <div className="p-2 bg-surface/50 rounded">
            <p className="font-mono text-data text-battery">
              {run.service_metrics?.ev_completion_rate ? `${(run.service_metrics.ev_completion_rate * 100).toFixed(0)}%` : '—'}
            </p>
            <p className="text-caption text-text-muted">EV Ready</p>
          </div>
        </div>
        <Button variant="ghost" size="sm" className="w-full" onClick={() => {
          // Would open selector modal
        }}>
          Change Selection
        </Button>
      </div>
    </div>
  );
}

function SummaryCard({ title, value, unit, icon }: {
  title: string;
  value: number;
  unit: string;
  icon: React.ReactNode;
}) {
  const isPositive = value > 0;
  const isNegative = value < 0;

  return (
    <div className="glass-card p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="font-body font-medium text-body-sm text-text">{title}</span>
        <div className={clsx('p-2 rounded-lg', isPositive ? 'bg-energy/20' : isNegative ? 'bg-violation/20' : 'bg-text-muted/20')}>
          {icon}
        </div>
      </div>
      <div className="flex items-baseline gap-1">
        <span className={clsx('font-display font-bold text-heading-1', isPositive ? 'text-energy' : isNegative ? 'text-violation' : 'text-text')}>
          {isPositive ? '+' : ''}{value.toFixed(1)}
        </span>
        <span className="text-caption text-text-muted">{unit}</span>
      </div>
      <p className="text-caption text-text-muted mt-1">B vs A</p>
    </div>
  );
}

function calculateSavings(a: SimulationRun, b: SimulationRun): number {
  const costA = a.energy_metrics?.total_cost || 0;
  const costB = b.energy_metrics?.total_cost || 0;
  if (costA === 0) return 0;
  return ((costA - costB) / costA) * 100;
}

function calculateServiceImprovement(a: SimulationRun, b: SimulationRun): number {
  const evA = a.service_metrics?.ev_completion_rate || 0;
  const evB = b.service_metrics?.ev_completion_rate || 0;
  if (evA === 0) return 0;
  return ((evB - evA) / evA) * 100;
}

function calculateGridSafety(a: SimulationRun, b: SimulationRun): number {
  const violA = a.grid_metrics?.voltage_violations_count || 0;
  const violB = b.grid_metrics?.voltage_violations_count || 0;
  if (violA === 0 && violB === 0) return 0;
  if (violA === 0) return -100;
  return ((violA - violB) / violA) * 100;
}