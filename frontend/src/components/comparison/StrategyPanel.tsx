import { Zap, Settings, Brain, Shield } from '../../utils/lucide';
import { ComplianceChip } from './ComplianceChip';
import { MetricCell } from './MetricCell';
import { StrategyMap } from './StrategyMap';

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

      {/* OPF fallback marker — only shown when the backend provides it;
           otherwise "no record" so it is never mistaken for a real strategy
           difference. */}
      <div className="p-3 border-b border-border/30 bg-surface/50">
        <div className="flex items-center justify-between mb-1">
          <h5 className="text-caption text-text-muted">OPF Fallback</h5>
        </div>
        <div className="flex items-center gap-2">
          {strategy.fallback_steps !== undefined ? (
            <>
              <span className="badge badge-violation text-[10px]">
                {strategy.fallback_steps} step{strategy.fallback_steps !== 1 ? 's' : ''}
              </span>
              {strategy.fallback_reason && (
                <span className="text-caption text-text-muted">{strategy.fallback_reason}</span>
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
          <span className="text-[10px] text-text-muted">No dispatch trace data</span>
        </div>
      </div>
    </div>
  );
}
