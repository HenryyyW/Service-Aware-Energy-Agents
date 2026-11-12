import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { clsx } from 'clsx';
import {
  FileText,
  Zap,
  Play,
  AlertCircle,
  Copy,
  RefreshCw,
  Building2,
  Sun,
  Battery,
  Car,
  Network,
} from '../utils/lucide';
import { Button } from '../components/ui/Button';
import type { ScenarioConfig } from '../api/types';

// ---------------------------------------------------------------------------
// Probe data (static imports of the P1 corpus). Each file is a full NL pipeline
// run record: final_config (ScenarioConfig-shaped), final_verdict, reporter/
// executor/verifier/planner outputs, and manifest. No backend is required.
// ---------------------------------------------------------------------------
import c01Data from '../probe/c01_buildings_residential.json';
import r04Data from '../probe/r04_out_of_range_limit.json';

const PROBE_DATA: Record<string, any> = {
  c01_buildings_residential: c01Data,
  r04_out_of_range_limit: r04Data,
};

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
      { label: 'Description', value: config.description || '—', prov: 'given' as Provenance },
      { label: 'Timestep', value: config.timestep_minutes + ' min', prov: 'default' as Provenance },
      { label: 'Random seed', value: String(config.random_seed), prov: 'default' as Provenance },
    ],
    buildings: [
      { label: 'Building ID', value: b.building_id, prov: 'given' as Provenance },
      { label: 'Type', value: b.building_type, prov: 'given' as Provenance },
      { label: 'Location', value: (b.location?.lat ?? '—') + ', ' + (b.location?.lon ?? '—'), prov: 'given' as Provenance },
    ],
    pv: [
      { label: 'Capacity (kW)', value: pv.capacity_kw ?? '—', prov: pv.capacity_kw ? ('given' as Provenance) : ('missing' as Provenance) },
      { label: 'Azimuth (°)', value: pv.azimuth ?? '—', prov: pv.azimuth ? ('given' as Provenance) : ('assumed' as Provenance) },
      { label: 'Tilt (°)', value: pv.tilt ?? '—', prov: pv.tilt ? ('given' as Provenance) : ('assumed' as Provenance) },
    ],
    battery: [
      { label: 'Capacity (kWh)', value: bat.capacity_kwh ?? '—', prov: bat.capacity_kwh ? ('given' as Provenance) : ('missing' as Provenance) },
      { label: 'Power (kW)', value: bat.power_kw ?? '—', prov: bat.power_kwh ? ('given' as Provenance) : ('missing' as Provenance) },
    ],
    ev: [
      { label: 'Count', value: ev.capacity_kwh ? '1' : '—', prov: ev.capacity_kwh ? ('given' as Provenance) : ('missing' as Provenance) },
      { label: 'Max charge (kW)', value: ev.max_charge_kw ?? '—', prov: ev.max_charge_kw ? ('given' as Provenance) : ('missing' as Provenance) },
      { label: 'Target SOC', value: ev.target_soc ?? '—', prov: ev.target_soc ? ('given' as Provenance) : ('assumed' as Provenance) },
    ],
    grid: [
      { label: 'Network', value: grid.network_type ?? '—', prov: 'assumed' as Provenance },
      { label: 'Import limit (kW)', value: config.community_import_limit_kw ?? '—', prov: config.community_import_limit_kw ? ('given' as Provenance) : ('missing' as Provenance) },
      { label: 'Export limit (kW)', value: config.community_export_limit_kw ?? '—', prov: config.community_export_limit_kw ? ('given' as Provenance) : ('missing' as Provenance) },
    ],
    sharing: [
      { label: 'Enabled', value: sharing.enabled ? 'yes' : 'no', prov: 'assumed' as Provenance },
      { label: 'Market', value: sharing.market_type ?? '—', prov: 'assumed' as Provenance },
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
/* Spatial render — building markers on a spatial map                         */
/* -------------------------------------------------------------------------- */
type MapLocation = { lat: number; lon: number };

function SpatialMap({ buildings }: { buildings: ScenarioConfig['buildings'] }) {
  const buildingsList = buildings ?? [];
  const locations: MapLocation[] = buildingsList
    .filter((b) => b.location && Number.isFinite(b.location.lat) && Number.isFinite(b.location.lon))
    .map((b) => b.location!);

  const lats = locations.map((l) => l.lat);
  const lons = locations.map((l) => l.lon);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLon = Math.min(...lons);
  const maxLon = Math.max(...lons);
  const latSpan = maxLat - minLat || 1;
  const lonSpan = maxLon - minLon || 1;

  return (
    <div className="relative w-full h-full">
      <div className="absolute inset-0 bg-[#f0f4f8] border border-border/30">
        {locations.map((loc) => {
          const x = ((loc.lon - minLon) / lonSpan) * 100;
          const y = 100 - ((loc.lat - minLat) / latSpan) * 100;
          return (
            <div
              key={`${loc.lat}-${loc.lon}`}
              className="absolute flex items-center justify-center"
              style={{ left: `${x}%`, top: `${y}%` }}
            >
              <button
                type="button"
                aria-label="Select building"
                title="Building"
                className="flex h-6 w-6 items-center justify-center rounded border-2 border-white bg-emerald-600 text-white shadow"
              >
                <Building2 size={14} />
              </button>
            </div>
          );
        })}
      </div>
      <div className="absolute bottom-2 left-2 right-2 p-3 bg-white/90 backdrop-blur rounded-lg border border-border/30">
        <p className="font-body font-medium text-body-sm text-text">
          {buildingsList.length} building{buildingsList.length !== 1 ? 's' : ''} on map
        </p>
        <p className="text-caption text-text-muted">
          Building locations from probe scenario {buildingsList[0]?.location?.lat}, {buildingsList[0]?.location?.lon}
        </p>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Confirm step                                                               */
/* -------------------------------------------------------------------------- */
function ConfirmProbe({ probeData, onConfirm }: { probeData: any; onConfirm: () => void }) {
  const config = probeData.final_config as ScenarioConfig;
  const manifest = probeData.manifest ?? {};
  const reporter = probeData.reporter_output ?? {};
  const detailed = reporter.detailed_report ?? {};
  const execution = detailed.execution ?? {};

  const isValid = probeData.success === true;
  const schemaErrors = probeData.schema_errors ?? [];
  const rejectionField =
    execution.error?.match(/for ScenarioConfig\n([\w.]+)/)?.[1] ??
    (schemaErrors.length > 0 ? schemaErrors[0] : undefined);
  const rejectionReason = execution.error ?? probeData.final_summary ?? 'Validation failed';

  // Rejection retry text: pre-fill the agent correction naming the invalid field
  const retryText = rejectionField ? `Fix ${rejectionField}: ${rejectionReason}` : '';

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b border-border/30 bg-surface/50">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display font-semibold text-heading-1 text-text">Confirm Scenario</h1>
            <p className="text-caption text-text-muted">Review the generated config before running. No scenario runs until you approve it.</p>
            <p className="text-caption text-text-muted mt-1">
              Scenario: <span className="font-mono text-body-sm">{manifest.scenario_id}</span>
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" onClick={onConfirm} aria-label="Clear">
              <RefreshCw className="w-4 h-4" />
            </Button>
          </div>
        </div>
        {!isValid && (
          <div className="mt-3 p-3 rounded-lg border border-violation/30 bg-violation/10">
            <div className="flex items-start gap-2 mb-1">
              <AlertCircle className="w-4 h-4 mt-0.5 text-violation" />
              <p className="font-body font-medium text-body-sm text-violation">Rejected — named field</p>
            </div>
            <p className="text-caption text-violation/80">{rejectionReason}</p>
            {rejectionField && (
              <p className="text-caption text-violation/80 mt-1">
                Fix <span className="font-mono">{rejectionField}</span> and regenerate.
              </p>
            )}
          </div>
        )}
      </div>

      <div className="flex-1 flex overflow-hidden">
        <div className="w-2/5 flex-shrink-0 border-r border-border/30 bg-surface/30 p-4 overflow-y-auto">
          <div className="space-y-4">
            <CommunitySummary config={config} />
          </div>
        </div>
        <div className="flex-1 min-w-0 p-4 overflow-y-auto">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-body font-medium text-body text-text">Configuration preview</h3>
                <p className="text-caption text-text-muted">Review field-by-field before running.</p>
              </div>
              <div className="flex items-center gap-2">
                <button className="text-caption text-text-muted hover:text-sun transition-colors" onClick={() => navigator.clipboard.writeText(JSON.stringify(config, null, 2))} title="Copy config JSON">
                  <Copy className="w-4 h-4 mr-1" />
                  Copy JSON
                </button>
              </div>
            </div>
            <div className="glass-card overflow-hidden">
              <div className="p-3 space-y-2">
                <pre className="font-mono text-body-sm overflow-auto p-3 bg-surface/50 rounded border border-border/30">
                  {JSON.stringify(config, null, 2)}
                </pre>
              </div>
            </div>
            {retryText && (
              <div className="p-3 rounded-lg border border-sun/30 bg-sun/10">
                <p className="text-caption text-sun/80">Retry pre-fill: {retryText}</p>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="border-t border-border/30 bg-surface/50 p-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Button
              variant="primary"
              disabled={!isValid}
              onClick={onConfirm}
              leftIcon={<Play className="w-4 h-4 mr-2" />}
            >
              Run Scenario
            </Button>
            <Button variant="secondary">Edit / reject</Button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Page                                                                       */
/* -------------------------------------------------------------------------- */
export function ScenarioProbePageContent() {
  const navigate = useNavigate();
  const { scenarioId } = useParams<{ scenarioId: string }>();
  const probeData = PROBE_DATA[scenarioId ?? ''];
  const [step, setStep] = useState<'confirm' | 'spatial'>('confirm');

  if (!probeData) {
    return (
      <div className="h-full flex flex-col p-4">
        <h1 className="font-display font-semibold text-heading-1 text-text">Scenario Not Found</h1>
        <p className="text-caption text-text-muted">Scenario "{scenarioId}" not found in probe corpus.</p>
        <Button variant="secondary" onClick={() => navigate('/scenarios')}>
          Back to Scenarios
        </Button>
      </div>
    );
  }

  if (step === 'confirm') {
    return (
      <ConfirmProbe
        probeData={probeData}
        onConfirm={() => setStep('spatial')}
      />
    );
  }

  const config = probeData.final_config as ScenarioConfig;

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b border-border/30 bg-surface/50">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display font-semibold text-heading-1 text-text">Community — Spatial Render</h1>
            <p className="text-caption text-text-muted">Buildings rendered on map from probe scenario config.</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" onClick={() => setStep('confirm')} aria-label="Back to confirm">
              <RefreshCw className="w-4 h-4" />
            </Button>
          </div>
        </div>
        <div className="flex items-center gap-4 pt-2">
          <span className="font-mono text-data text-sun">{config.scenario_id}</span>
          <span className="badge badge-sun">{probeData.success ? 'accept' : probeData.final_verdict}</span>
          <span className="font-mono text-data text-sun">{config.buildings?.length ?? 0} buildings</span>
        </div>
      </div>
      <div className="flex-1 relative">
        <SpatialMap buildings={config.buildings ?? []} />
      </div>
    </div>
  );
}

export function ScenarioProbePage() {
  return <ScenarioProbePageContent />;
}
