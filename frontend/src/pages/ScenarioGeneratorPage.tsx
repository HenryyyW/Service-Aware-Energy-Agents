import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { clsx } from 'clsx';
import {
  FileText,
  Zap,
  Play,
  AlertTriangle,
  AlertCircle,
  CheckCircle,
  Copy,
  RefreshCw,
  Building2,
  Sun,
  Battery,
  Car,
  Network,
} from '../utils/lucide';
import { Button } from '../components/ui/Button';
import { Textarea } from '../components/ui/Input';
import { api } from '../api/client';
import { useScenarioStore } from '../store/scenarioStore';
import type { ScenarioConfig } from '../api/types';

/* -------------------------------------------------------------------------- */
/* Mock NL -> config agent. Replace with Backend A's real pipeline via prop.   */
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


/* -------------------------------------------------------------------------- */
/* Provenance / confidence chip                                               */
/* -------------------------------------------------------------------------- */
type Provenance = 'given' | 'assumed' | 'default' | 'missing';

const PROVENANCE_CHIP: Record<Provenance, { glyph: string; label: string }> = {
  given: { glyph: '✓', label: 'given' },
  assumed: { glyph: '~', label: 'assumed' },
  default: { glyph: '↻', label: 'default' },
  missing: { glyph: '!', label: 'missing' },
};

const CONFIDENCE_STYLE: Record<Provenance, string> = {
  given: 'bg-transparent border-border text-text-muted',
  assumed: 'bg-sun/10 border-sun/30 text-sun',
  default: 'bg-grid/10 border-grid/30 text-grid',
  missing: 'bg-violation/10 border-violation/30 text-violation',
};

function ConfidenceChip({ prov, tooltip }: { prov: Provenance; tooltip?: string }) {
  const chip = PROVENANCE_CHIP[prov];
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded text-caption font-medium border',
        CONFIDENCE_STYLE[prov]
      )}
      title={tooltip}
    >
      <span className="text-caption">{chip.glyph}</span>
      {chip.label}
    </span>
  );
}

/* -------------------------------------------------------------------------- */
/* Field-level diff vs. existing scenario                                     */
/* -------------------------------------------------------------------------- */
type DiffKind = 'added' | 'removed' | 'changed';

function buildDiff(existing: ScenarioConfig, parsed: ScenarioConfig) {
  const oldLeaves = new Map(flatten(existing));
  const newLeaves = new Map(flatten(parsed));
  const sections: { section: string; rows: { path: string; kind: DiffKind; old: any; new: any }[] }[] = [];
  for (const [path, newVal] of newLeaves) {
    const oldVal = oldLeaves.get(path);
    if (oldVal === undefined) {
      const section = path.split('.')[0];
      let s = sections.find((x) => x.section === section);
      if (!s) { s = { section, rows: [] }; sections.push(s); }
      s.rows.push({ path, kind: 'added', old: undefined, new: newVal });
    } else if (JSON.stringify(oldVal) !== JSON.stringify(newVal)) {
      const section = path.split('.')[0];
      let s = sections.find((x) => x.section === section);
      if (!s) { s = { section, rows: [] }; sections.push(s); }
      s.rows.push({ path, kind: 'changed', old: oldVal, new: newVal });
    }
  }
  for (const [path] of oldLeaves) {
    if (!newLeaves.has(path)) {
      const section = path.split('.')[0];
      let s = sections.find((x) => x.section === section);
      if (!s) { s = { section, rows: [] }; sections.push(s); }
      s.rows.push({ path, kind: 'removed', old: oldLeaves.get(path), new: undefined });
    }
  }
  return sections;
}

/* -------------------------------------------------------------------------- */
/* Left panel — community summary cards                                       */
/* -------------------------------------------------------------------------- */
const ICON_FOR: Record<string, any> = {
  community: Building2,
  buildings: Building2,
  pv: Sun,
  battery: Battery,
  ev: Car,
  evs: Car,
  flexible_load: Zap,
  flexible_loads: Zap,
  tariff: FileText,
  grid: Network,
  sharing: Zap,
};

function SummaryCard({ title, icon: Icon, rows }: { title: string; icon: any; rows: { label: string; value: string; prov: Provenance }[] }) {
  return (
    <div className="glass-card overflow-hidden">
      <div className="flex items-center gap-2 p-3 bg-surface/50 border-b border-border/30">
        <Icon className="w-4 h-4 text-text-muted" />
        <h4 className="font-body font-medium text-body-sm text-text">{title}</h4>
      </div>
      <div className="p-3 space-y-2">
        {rows.map((r, i) => (
          <div key={i} className="flex items-center gap-3">
            <span className="w-40 flex-shrink-0 text-caption text-text-muted leading-none">{r.label}</span>
            <span className="flex-1 font-mono text-body-sm text-text truncate">{r.value}</span>
            <ConfidenceChip prov={r.prov} />
          </div>
        ))}
      </div>
    </div>
  );
}

function CommunitySummary({ config }: { config: ScenarioConfig }) {
  const b = (config.buildings ?? [])[0] ?? {};
  const pv = b.pv ?? {};
  const bat = b.battery ?? {};
  const ev = b.evs?.[0] ?? {};
  const grid = config.pandapower ?? ({} as any);
  const sharing = config.energy_sharing ?? ({} as any);

  const rows = {
    community: [
      { label: 'Name', value: config.name, prov: 'given' as Provenance },
      { label: 'Description', value: config.description || '\u2014', prov: 'given' as Provenance },
      { label: 'Timestep', value: config.timestep_minutes + ' min', prov: 'default' as Provenance },
      { label: 'Random seed', value: String(config.random_seed), prov: 'default' as Provenance },
    ],
    buildings: [
      { label: 'Building ID', value: b.building_id, prov: 'given' as Provenance },
      { label: 'Type', value: b.building_type, prov: 'given' as Provenance },
      { label: 'Location', value: (b.location?.lat ?? '\u2014') + ', ' + (b.location?.lon ?? '\u2014'), prov: 'given' as Provenance },
    ],
    pv: [
      { label: 'Capacity (kW)', value: pv.capacity_kw ?? '\u2014', prov: pv.capacity_kw ? ('given' as Provenance) : ('missing' as Provenance) },
      { label: 'Azimuth (\u00B0)', value: pv.azimuth ?? '\u2014', prov: pv.azimuth ? ('given' as Provenance) : ('assumed' as Provenance) },
      { label: 'Tilt (\u00B0)', value: pv.tilt ?? '\u2014', prov: pv.tilt ? ('given' as Provenance) : ('assumed' as Provenance) },
    ],
    battery: [
      { label: 'Capacity (kWh)', value: bat.capacity_kwh ?? '\u2014', prov: bat.capacity_kwh ? ('given' as Provenance) : ('missing' as Provenance) },
      { label: 'Power (kW)', value: bat.power_kw ?? '\u2014', prov: bat.power_kw ? ('given' as Provenance) : ('missing' as Provenance) },
    ],
    ev: [
      { label: 'Count', value: ev.capacity_kwh ? '1' : '\u2014', prov: ev.capacity_kwh ? ('given' as Provenance) : ('missing' as Provenance) },
      { label: 'Max charge (kW)', value: ev.max_charge_kw ?? '\u2014', prov: ev.max_charge_kw ? ('given' as Provenance) : ('missing' as Provenance) },
      { label: 'Target SOC', value: ev.target_soc ?? '\u2014', prov: ev.target_soc ? ('given' as Provenance) : ('assumed' as Provenance) },
    ],
    grid: [
      { label: 'Network', value: grid.network_type ?? '\u2014', prov: 'assumed' as Provenance },
      { label: 'Import limit (kW)', value: config.community_import_limit_kw ?? '\u2014', prov: config.community_import_limit_kw ? ('given' as Provenance) : ('missing' as Provenance) },
      { label: 'Export limit (kW)', value: config.community_export_limit_kw ?? '\u2014', prov: config.community_export_limit_kw ? ('given' as Provenance) : ('missing' as Provenance) },
    ],
    sharing: [
      { label: 'Enabled', value: sharing.enabled ? 'yes' : 'no', prov: 'assumed' as Provenance },
      { label: 'Market', value: sharing.market_type ?? '\u2014', prov: 'assumed' as Provenance },
    ],
  };

  const sections = [
    { title: 'Community', icon: Building2, rows: rows.community },
    { title: 'Buildings', icon: Building2, rows: rows.buildings },
    { title: 'PV', icon: Sun, rows: rows.pv },
    { title: 'Battery', icon: Battery, rows: rows.battery },
    { title: 'EV', icon: Car, rows: rows.ev },
    { title: 'Grid', icon: Network, rows: rows.grid },
    { title: 'Sharing', icon: Zap, rows: rows.sharing },
  ];

  return (
    <div className="space-y-3">
      {sections.map((s) => (
        <SummaryCard key={s.title} title={s.title} icon={ICON_FOR[s.title]} rows={s.rows} />
      ))}
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

  const [step, setStep] = useState<'input' | 'confirm'>('input');
  const [description, setDescription] = useState('');
  const [parsed, setParsed] = useState<ScenarioConfig | null>(null);
  const [existing, setExisting] = useState<ScenarioConfig | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [validation, setValidation] = useState<{ valid: boolean; errors: string[]; warnings: string[] } | null>(null);
  const [error, setError] = useState<{ message: string; field?: string } | null>(null);
  const [lastRunId, setLastRunId] = useState<string | null>(null);
  const [planSource, setPlanSource] = useState<string | null>(null);
  const [rejectedFields, setRejectedFields] = useState<string[]>([]);
  const [showDiff, setShowDiff] = useState(false);

  const handleExample = useCallback((ex: (typeof EXAMPLES)[number]) => {
    setDescription(ex.description);
    setError(null);
  }, []);

  const handleGenerate = useCallback(async () => {
    if (!description.trim() || isGenerating) return;
    setError(null);
    setIsGenerating(true);
    try {
      let config: ScenarioConfig | null = null;
      if (propGenerate) {
        // injected generator (tests / previews): returns a config directly
        config = await propGenerate(description.trim());
        setPlanSource('injected');
        setRejectedFields([]);
      } else {
        // the real path: the verified NL->config pipeline behind the API
        const res = await api.generateScenario(description.trim());
        setPlanSource(res.plan_source ?? null);
        setRejectedFields(res.rejected_fields ?? []);
        config = res.config ?? null;
        if (!config) {
          throw new Error(
            res.rejected_fields?.length
              ? `The description cannot be configured as written: ${res.rejected_fields.join(', ')} must be stated`
              : 'The pipeline produced no configuration for this description'
          );
        }
      }
      setParsed(config);
      setCurrentScenario(config);
      setStep('confirm');
      setValidation(null);
      setLastRunId(null);
    } catch (e: any) {
      setError({ message: e.response?.data?.detail || e.message || 'Failed to generate config' });
    } finally {
      setIsGenerating(false);
    }
  }, [description, isGenerating, propGenerate, setCurrentScenario]);

  const handleValidate = useCallback(async () => {
    if (!parsed?.scenario_id) return;
    setIsValidating(true);
    try {
      const v = await api.validateScenario(parsed.scenario_id);
      setValidation(v);
    } catch (e: any) {
      setError({ message: e.response?.data?.detail || 'Validation failed' });
    } finally {
      setIsValidating(false);
    }
  }, [parsed?.scenario_id]);

  const handleRun = useCallback(async () => {
    if (!parsed || isRunning) return;
    setError(null);
    setIsRunning(true);
    try {
      const created = await api.createScenario(parsed);
      addScenario(parsed);
      setLastRunId((created.scenario_id ?? parsed.scenario_id) ?? null);
      navigate(`/scenarios/${created.scenario_id ?? parsed.scenario_id}`);
    } catch (e: any) {
      const detail = e.response?.data?.detail || e.message || 'Run rejected';
      let field: string | undefined;
      const m = detail.match(/field[s]?\s*['"]?([\w.]+)['"]?/i);
      if (m) field = m[1];
      setError({ message: detail, field });
    } finally {
      setIsRunning(false);
    }
  }, [parsed, isRunning, addScenario, navigate]);

  const handleEdit = useCallback(() => {
    setStep('input');
    setValidation(null);
    setError(null);
  }, []);

  const handleClear = useCallback(() => {
    setDescription('');
    setParsed(null);
    setExisting(null);
    setError(null);
    setValidation(null);
    setLastRunId(null);
    setStep('input');
  }, []);

  const diff = existing && parsed ? buildDiff(existing, parsed) : null;

  if (step === 'input') {
    return (
      <div className="h-full flex flex-col">
        <div className="p-4 border-b border-border/30 bg-surface/50">
          <h1 className="font-display font-semibold text-heading-1 text-text">Generate Scenario</h1>
          <p className="text-caption text-text-muted">Describe an energy community in natural language, review the generated config, then run it.</p>
        </div>
        <div className="flex-1 flex overflow-hidden">
          <div className="w-2/5 flex-shrink-0 border-r border-border/30 bg-surface/30 p-4 overflow-y-auto">
            <div className="space-y-4">
              <div className="space-y-2">
                <label className="block text-caption text-text-muted">Community description</label>
                <Textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Describe the community you want to simulate" rows={6} className="font-body" />
                <p className="text-caption text-text-muted">The agent turns this into an executable ScenarioConfig you can review before running.</p>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Button type="button" variant="ghost" size="sm" disabled={isGenerating} onClick={handleGenerate} leftIcon={<Zap className="w-4 h-4 mr-1" />}>
                    {isGenerating ? 'Generating...' : 'Generate config'}
                  </Button>
                </div>
              </div>
              <div className="space-y-2">
                <p className="text-caption text-text-muted">Examples</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {EXAMPLES.map((ex) => (
                    <button key={ex.title} onClick={() => handleExample(ex)} className="glass-card p-3 text-left hover:border-sun/50 transition-colors border border-border/30">
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
          <div className="flex-1 min-w-0 p-4 overflow-y-auto">
            <div className="glass-card p-8 text-center text-text-muted">
              <FileText className="w-16 h-16 mx-auto mb-3 text-text-muted/30" />
              <p className="text-body">Generate a config to preview it here.</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b border-border/30 bg-surface/50">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display font-semibold text-heading-1 text-text">Confirm Scenario</h1>
            <p className="text-caption text-text-muted">Review the generated config before running. No scenario runs until you approve it.</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" onClick={handleClear} aria-label="Clear">
              <RefreshCw className="w-4 h-4" />
            </Button>
          </div>
        </div>
        {planSource === 'rule_based_fallback' && (
          <div className="mt-3 p-3 bg-sun/10 border border-sun/30 text-sun rounded-lg">
            <p className="text-caption font-medium text-sun flex items-center gap-1">
              <span aria-hidden="true">&#9888;</span>
              <span>Preview mode: the coding agent was unavailable for this description, so a deterministic keyword builder produced it. Review every field before running.</span>
            </p>
          </div>
        )}
        {planSource === 'llm' && (
          <div className="mt-3 p-3 bg-energy/10 border border-energy/30 text-energy rounded-lg">
            <p className="text-caption font-medium text-energy flex items-center gap-1">
              <span aria-hidden="true">&#10003;</span>
              <span>Planned by the coding agent (natural-language &rarr; config pipeline).</span>
            </p>
          </div>
        )}
        {rejectedFields.length > 0 && (
          <div className="mt-3 p-3 bg-violation/10 border border-violation/30 text-violation rounded-lg">
            <p className="text-caption font-medium text-violation flex items-center gap-1">
              <span aria-hidden="true">&#9888;</span>
              <span>Named rejections (must be stated before this description can run): {rejectedFields.join(', ')}</span>
            </p>
          </div>
        )}
      </div>

      <div className="flex-1 flex overflow-hidden">
        <div className="w-2/5 flex-shrink-0 border-r border-border/30 bg-surface/30 p-4 overflow-y-auto">
          {parsed && <CommunitySummary config={parsed} />}
        </div>
        <div className="flex-1 min-w-0 p-4 overflow-y-auto">
          {parsed && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-body font-medium text-body text-text">Configuration preview</h3>
                  <p className="text-caption text-text-muted">Review field-by-field before running.</p>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={() => setShowDiff(!showDiff)} className="text-caption text-text-muted hover:text-sun transition-colors">
                    {showDiff ? 'Show summary' : 'Show diff'}
                  </button>
                  <button className="text-caption text-text-muted hover:text-sun transition-colors" onClick={() => navigator.clipboard.writeText(JSON.stringify(parsed, null, 2))} title="Copy config JSON">
                    <Copy className="w-4 h-4 mr-1" />
                    Copy JSON
                  </button>
                </div>
              </div>
              {showDiff && diff && diff.length > 0 ? (
                <div className="glass-card overflow-hidden">
                  <div className="p-3 bg-surface/50 border-b border-border/30">
                    <h4 className="font-body font-medium text-body-sm text-text">Changed fields</h4>
                  </div>
                  <div className="p-3 space-y-2">
                    {diff.map((s) => (
                      <div key={s.section} className="mb-2">
                        <h5 className="text-caption text-text-muted mb-1">{s.section}</h5>
                        {s.rows.map((r) => (
                          <div key={r.path} className="flex items-start gap-2 text-body-sm">
                            <span className="flex-shrink-0 w-48 text-caption text-text-muted leading-none">{r.path}</span>
                            <span className={clsx('flex-1 font-mono', r.kind === 'added' ? 'text-energy' : r.kind === 'removed' ? 'text-violation' : 'text-sun')}>
                              {JSON.stringify(r.new)}
                            </span>
                            {r.kind === 'changed' && <span className="text-caption text-sun">~\u2192 {JSON.stringify(r.old)}</span>}
                            {r.kind === 'added' && <span className="text-caption text-sun">+ added</span>}
                            {r.kind === 'removed' && <span className="text-caption text-violation">- removed</span>}
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <p className="text-caption text-text-muted">No diff available against an existing scenario.</p>
                </div>
              )}
              {validation && (
                <div className={clsx('p-3 rounded-lg border', validation.valid ? 'border-energy/30 bg-energy/10' : 'border-violation/30 bg-violation/10')}>
                  <div className="flex items-start gap-2 mb-1">
                    {validation.valid ? <CheckCircle className="w-4 h-4 mt-0.5 text-energy" /> : <AlertCircle className="w-4 h-4 mt-0.5 text-violation" />}
                    <p className="font-body font-medium text-body-sm">{validation.valid ? 'Valid — ready to run' : 'Validation failed — fix before running'}</p>
                  </div>
                  {validation.errors.length > 0 && (
                    <ul className="text-caption text-violation/80 mt-1 list-disc list-inside space-y-1">
                      {validation.errors.map((e) => <li key={e}>{e}</li>)}
                    </ul>
                  )}
                  {validation.warnings.length > 0 && (
                    <ul className="text-caption text-text-muted mt-1 list-disc list-inside space-y-1">
                      {validation.warnings.map((w) => <li key={w}>{w}</li>)}
                    </ul>
                  )}
                </div>
              )}
              {error && (
                <div className="p-3 rounded-lg border border-violation/30 bg-violation/10">
                  <div className="flex items-start gap-2 mb-1">
                    <AlertCircle className="w-4 h-4 mt-0.5 text-violation" />
                    <p className="font-body font-medium text-body-sm text-violation">{error.field ? `Run rejected — ${error.field}` : 'Run rejected'}</p>
                  </div>
                  <p className="text-caption text-violation/80">{error.message}</p>
                  {error.field && <p className="text-caption text-violation/80 mt-1">Fix <span className="font-mono">{error.field}</span> and regenerate.</p>}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="border-t border-border/30 bg-surface/50 p-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Button
              variant="primary"
              disabled={!parsed || isRunning || Boolean(validation?.valid === false)}
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
            <Button variant="secondary" onClick={handleEdit}>Edit / reject</Button>
            <Button variant="ghost" size="sm" disabled={!parsed?.scenario_id || isValidating} onClick={handleValidate}>
              {isValidating ? 'Validating...' : 'Validate now'}
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
        </div>
      </div>
    </div>
  );
}

export function ScenarioGeneratorPage({ generateScenario }: ScenarioGeneratorPageProps) {
  return <ScenarioGeneratorPageContent generateScenario={generateScenario} />;
}
