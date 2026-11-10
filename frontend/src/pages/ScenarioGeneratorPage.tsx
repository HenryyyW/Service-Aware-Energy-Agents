import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { clsx } from 'clsx';
import {
  FileText,
  Zap,
  Play,
  AlertTriangle,
  CheckCircle,
  Copy,
  Menu,
  RefreshCw,
} from '../utils/lucide';
import { Button } from '../components/ui/Button';
import { Textarea } from '../components/ui/Input';
import { api } from '../api/client';
import { useScenarioStore } from '../store/scenarioStore';
import type { ScenarioConfig } from '../api/types';

/* -------------------------------------------------------------------------- */
/* Default / reference ScenarioConfig used for the diffable preview.          */
/* -------------------------------------------------------------------------- */
const DEFAULT_SCENARIO: ScenarioConfig = {
  scenario_id: '',
  name: 'New Community',
  description: '',
  community: {
    name: 'New Community',
    buildings: 5,
    simulation_period: '7_days',
    timestep_minutes: 15,
  },
  assets: {
    pv: { penetration: 0.4, orientation: 'rooftop' },
    batteries: { community_capacity_kwh: 800, max_power_kw: 250 },
    evs: { number: 35, charging_power_kw: [7, 22, 60], departure_soc_requirement: 0.8 },
    flexible_loads: { share: 0.15 },
  },
  grid: {
    model: 'simbench_lv_grid_1',
    transformer_capacity_kva: 630,
    voltage_limits_pu: [0.95, 1.05],
    import_limit_kw: 500,
    export_limit_kw: 200,
  },
  control: {
    strategy: 'rule_based',
    objective: [
      'minimize_cost',
      'minimize_peak',
      'maximize_renewable_self_consumption',
      'preserve_ev_service',
      'preserve_comfort',
    ],
  },
  energy_sharing: {
    enabled: false,
    market_type: 'uniform_price',
    settlement_interval: '1h',
    dynamic_pricing: {
      enabled: false,
      pricing_type: 'lmp',
      lmp_update_interval_minutes: 60,
      congestion_cost_method: 'dc_approx',
      loss_factor: 1.0,
      price_cap_per_kwh: 1.0,
      fallback_to_tariff: true,
    },
  },
  random_seed: 42,
  timestep_minutes: 15,
};

/* -------------------------------------------------------------------------- */
/* Mock NL -> config agent. Replace with the real pipeline (Backend A).       */
/* -------------------------------------------------------------------------- */
const EXAMPLES = [
  {
    title: 'High EV Penetration',
    description:
      'Create a renewable energy community with 15 buildings, rooftop PV, building batteries, and 50 EVs. Each EV must reach at least 80% SOC before 07:00. Limit total community grid import to 300 kW.',
  },
  {
    title: 'PV Export Constraints',
    description:
      'Increase PV capacity to 80% penetration. Apply feeder-level export limit of 200 kW. Evaluate voltage rise, reverse power flow, and curtailment.',
  },
  {
    title: 'Local Energy Sharing',
    description:
      'Enable community energy sharing with 10 buildings, uniform price settlement, and battery backup.',
  },
];

function deepGet(obj: any, path: string): any {
  return path.split('.').reduce((acc, key) => (acc && acc[key] !== undefined ? acc[key] : undefined), obj);
}

function flatten(obj: any, prefix = ''): [string, any][] {
  let out: [string, any][] = [];
  for (const [k, v] of Object.entries(obj ?? {})) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      out = out.concat(flatten(v, key));
    } else {
      out.push([key, v]);
    }
  }
  return out;
}

function mockGenerateScenario(description: string): ScenarioConfig {
  const d = description.toLowerCase();
  const config = JSON.parse(JSON.stringify(DEFAULT_SCENARIO));
  const hasEv = /ev|electric.?vehicle|charg/.test(d);
  const hasPv = /pv|solar|photovolta/.test(d);
  const hasBattery = /battery|storage/.test(d);
  const hasSharing = /sharing|settlement|p2p|community pool/.test(d);
  const hasLimit = /limit|cap|kW|kw/.test(d);

  config.name = description.slice(0, 60).trim() || 'Generated Community';
  config.description = description;
  config.random_seed = 42;

  if (hasEv) {
    config.assets.evs.number = 50;
    config.assets.evs.charging_power_kw = [7, 11, 22];
    config.assets.evs.departure_soc_requirement = 0.8;
  }
  if (hasPv) {
    config.assets.pv.penetration = 0.8;
    config.assets.pv.orientation = 'south';
  }
  if (hasBattery) {
    config.assets.batteries.community_capacity_kwh = 1000;
    config.assets.batteries.max_power_kw = 500;
  }
  if (hasSharing) {
    config.energy_sharing.enabled = true;
    config.energy_sharing.market_type = 'uniform_price';
  }
  if (hasLimit) {
    const m = d.match(/(\d+)\s*kW/);
    if (m) config.community_import_limit_kw = parseInt(m[1], 10);
  }

  return config;
}

/* -------------------------------------------------------------------------- */
/* Diffable config preview                                                    */
/* -------------------------------------------------------------------------- */
type Leaf = { path: string; label: string; generated: any; default: any; changed: boolean };

function buildLeaves(generated: ScenarioConfig): Leaf[] {
  const genLeaves = flatten(generated);
  return genLeaves.map(([path, value]) => {
    const label = path
      .split('.')
      .map((s) => s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, ' '))
      .join(' > ');
    const def = deepGet(DEFAULT_SCENARIO, path);
    return { path, label, generated: value, default: def, changed: JSON.stringify(value) !== JSON.stringify(def) };
  });
}

const TYPE_LABEL: Record<string, string> = {
  community: 'Community',
  assets: 'Assets',
  grid: 'Grid',
  control: 'Control',
  energy_sharing: 'Energy Sharing',
};

function ConfigPreview({ generated }: { generated: ScenarioConfig }) {
  const leaves = buildLeaves(generated);
  const bySection = new Map<string, Leaf[]>();
  for (const leaf of leaves) {
    const section = leaf.path.split('.')[0];
    if (!bySection.has(section)) bySection.set(section, []);
    bySection.get(section)!.push(leaf);
  }

  return (
    <div className="space-y-3">
      {leaves.length === 0 ? (
        <div className="glass-card p-8 text-center text-text-muted">
          <FileText className="w-16 h-16 mx-auto mb-3 text-text-muted/30" />
          <p className="text-body">Generate a config to preview it here.</p>
        </div>
      ) : (
        <>
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle className="w-4 h-4 text-energy" />
            <span className="font-body font-medium text-body-sm text-text">
              Generated configuration ({leaves.filter((l) => l.changed).length} of {leaves.length} fields changed from default)
            </span>
          </div>
          {[...bySection.entries()].map(([section, sectionLeaves]) => (
            <div key={section} className="glass-card overflow-hidden">
              <div className="flex items-center gap-2 p-3 bg-surface/50 border-b border-border/30">
                <Menu className="w-4 h-4 text-text-muted" />
                <h4 className="font-body font-medium text-body-sm text-text">
                  {TYPE_LABEL[section] || section}
                </h4>
              </div>
              <div className="p-3 space-y-1.5">
                {sectionLeaves.map((leaf) => (
                  <div
                    key={leaf.path}
                    className={clsx(
                      'flex items-start gap-2 text-body-sm',
                      leaf.changed ? 'bg-sun/10 border-l-2 border-l-sun pl-2' : 'bg-transparent',
                    )}
                  >
                    <span className="flex-shrink-0 w-48 text-caption text-text-muted leading-none">
                      {leaf.label}
                    </span>
                    {leaf.changed ? (
                      <span className="flex-1 font-mono text-sun">{JSON.stringify(leaf.generated)}</span>
                    ) : (
                      <span className="flex-1 font-mono text-text-muted">{JSON.stringify(leaf.generated)}</span>
                    )}
                    {leaf.changed && <span className="text-caption text-sun">● changed</span>}
                  </div>
                ))}
              </div>
            </div>
          ))}
          <div className="mt-3 flex items-center gap-2">
            <Copy className="w-4 h-4 text-text-muted" />
            <button
              className="text-caption text-text-muted hover:text-sun transition-colors"
              onClick={() => navigator.clipboard.writeText(JSON.stringify(generated, null, 2))}
              title="Copy config JSON"
            >
              Copy config JSON
            </button>
          </div>
        </>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Page                                                                       */
/* -------------------------------------------------------------------------- */
export interface ScenarioGeneratorPageProps {
  generateScenario?: (description: string) => ScenarioConfig | Promise<ScenarioConfig>;
}

export function ScenarioGeneratorPageContent({ generateScenario: propGenerate }: ScenarioGeneratorPageProps) {
  const navigate = useNavigate();
  const { setCurrentScenario, addScenario } = useScenarioStore((s) => ({
    setCurrentScenario: s.setCurrentScenario,
    addScenario: s.addScenario,
  }));
  const generate = propGenerate ?? mockGenerateScenario;

  const [description, setDescription] = useState('');
  const [generated, setGenerated] = useState<ScenarioConfig | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<{ message: string; field?: string } | null>(null);
  const [lastRunId, setLastRunId] = useState<string | null>(null);

  const handleExample = useCallback((ex: (typeof EXAMPLES)[number]) => {
    setDescription(ex.description);
    setError(null);
  }, []);

  const handleGenerate = useCallback(async () => {
    if (!description.trim() || isGenerating) return;
    setError(null);
    setIsGenerating(true);
    try {
      const config = await generate(description.trim());
      setGenerated(config);
      setCurrentScenario(config);
    } catch (e) {
      setError({ message: e instanceof Error ? e.message : 'Failed to generate config' });
    } finally {
      setIsGenerating(false);
    }
  }, [description, isGenerating, generate, setCurrentScenario]);

  const handleRun = useCallback(async () => {
    if (!generated || isRunning) return;
    setError(null);
    setIsRunning(true);
    try {
      const created = await api.createScenario(generated);
      addScenario(generated);
      setLastRunId((created.scenario_id ?? generated.scenario_id) ?? null);
      navigate(`/scenarios/${created.scenario_id || generated.scenario_id}`);
    } catch (e: any) {
      const detail = e.response?.data?.detail || e.message || 'Run rejected';
      let field: string | undefined;
      const m = detail.match(/field[s]?\s*['"]?([\w.]+)['"]?/i);
      if (m) field = m[1];
      setError({ message: detail, field });
    } finally {
      setIsRunning(false);
    }
  }, [generated, isRunning, addScenario, navigate]);

  const handleClear = useCallback(() => {
    setDescription('');
    setGenerated(null);
    setError(null);
    setLastRunId(null);
  }, []);

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-border/30 bg-surface/50">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display font-semibold text-heading-1 text-text">Generate Scenario</h1>
            <p className="text-caption text-text-muted">
              Describe an energy community in natural language, review the generated config, then run it.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" onClick={handleClear} disabled={!generated && !description} aria-label="Clear">
              <RefreshCw className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Left: input + examples */}
        <div className="w-2/5 flex-shrink-0 border-r border-border/30 bg-surface/30 p-4 overflow-y-auto">
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="block text-caption text-text-muted">Community description</label>
              <Textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe the community you want to simulate"
                rows={6}
                className="font-body"
              />
              <p className="text-caption text-text-muted">
                The agent turns this into an executable ScenarioConfig you can review before running.
              </p>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={isGenerating}
                  onClick={handleGenerate}
                  leftIcon={<Zap className="w-4 h-4 mr-1" />}
                >
                  {isGenerating ? 'Generating...' : 'Generate config'}
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-caption text-text-muted">Examples</p>
              <div className="grid gap-2 sm:grid-cols-2">
                {EXAMPLES.map((ex) => (
                  <button
                    key={ex.title}
                    onClick={() => handleExample(ex)}
                    className="glass-card p-3 text-left hover:border-sun/50 transition-colors border border-border/30"
                  >
                    <p className="font-body font-medium text-body-sm text-text mb-1">{ex.title}</p>
                    <p className="text-caption text-text-muted line-clamp-2">{ex.description}</p>
                  </button>
                ))}
              </div>
            </div>

            {error && (
              <div className="p-3 rounded-lg border border-violation/30 bg-violation/10">
                <div className="flex items-start gap-2 mb-1">
                  <AlertTriangle className="w-4 h-4 mt-0.5 text-violation" />
                  <p className="font-body font-medium text-body-sm text-violation">Generation failed</p>
                </div>
                <p className="text-caption text-violation/80">{error.message}</p>
              </div>
            )}
          </div>
        </div>

        {/* Right: config preview */}
        <div className="flex-1 min-w-0 p-4 overflow-y-auto">
          <ConfigPreview generated={generated ?? DEFAULT_SCENARIO} />
        </div>
      </div>

      {/* Bottom bar: RUN + failure + status */}
      <div className="border-t border-border/30 bg-surface/50 p-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Button
              variant="primary"
              disabled={!generated || isRunning}
              onClick={handleRun}
              leftIcon={<Play className="w-4 h-4 mr-2" />}
            >
              {isRunning ? (
                <>
                  <div className="animate-spin w-4 h-4 mr-2 border-2 border-white/30 border-t-white rounded-full" />
                  Running...
                </>
              ) : (
                <>
                  Run Scenario
                </>
              )}
            </Button>
            {lastRunId && (
              <div className="flex items-center gap-2 bg-energy/10 border border-energy/30 rounded-lg px-3 py-2">
                <CheckCircle className="w-4 h-4 text-energy" />
                <div>
                  <p className="font-body font-medium text-body-sm text-text">Scenario created</p>
                  <p className="text-caption text-energy/80 font-mono">{lastRunId}</p>
                </div>
              </div>
            )}
          </div>

          {error && (
            <div className="flex items-start gap-2 w-full sm:w-auto">
              <AlertTriangle className="w-5 h-5 mt-0.5 text-violation" />
              <div>
                <p className="font-body font-medium text-body-sm text-violation">Run rejected</p>
                <p className="text-caption text-violation/80">{error.message}</p>
                {error.field && (
                  <p className="text-caption text-violation/80 mt-1">
                    Fix <span className="font-mono">{error.field}</span> and regenerate.
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function ScenarioGeneratorPage({ generateScenario }: ScenarioGeneratorPageProps) {
  return <ScenarioGeneratorPageContent generateScenario={generateScenario} />;
}
