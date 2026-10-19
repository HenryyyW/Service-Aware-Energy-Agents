import { useMemo } from 'react';
import { clsx } from 'clsx';
import { Zap, AlertTriangle, CheckCircle, TrendingUp, TrendingDown, Download } from 'lucide-react';
import { Button } from '../ui/Button';
import { TimeSeriesChart } from './TimeSeriesChart';
import type { SelectedAsset, GridDiagnostics, TimeStepData } from '../../api/types';

interface GridExplorerProps {
  asset: SelectedAsset;
  gridDiagnostics: GridDiagnostics | undefined;
  trajectories: TimeStepData[];
}

export function GridExplorer({ asset, gridDiagnostics, trajectories }: GridExplorerProps) {
  const { type, id, data } = asset;

  if (!gridDiagnostics) {
    return (
      <div className="glass-card p-4 text-center text-text-muted">
        <Zap className="w-12 h-12 mx-auto mb-3 text-text-muted/30" />
        <p className="text-body-sm">No grid diagnostics available</p>
        <p className="text-caption text-text-muted/50 mt-1">Run a simulation with grid coupling to see voltage and loading data</p>
      </div>
    );
  }

  const voltageViolationSource = gridDiagnostics.violations?.voltage || [];
  const voltageViolations = Array.isArray(voltageViolationSource)
    ? voltageViolationSource
    : Object.entries(voltageViolationSource).map(([bus, violation]) => ({ bus, ...violation }));
  const voltageViolationIds = new Set(voltageViolations.map((violation) => violation.bus));
  const loadingViolationSource = gridDiagnostics.violations?.loading || [];
  const loadingViolations = Array.isArray(loadingViolationSource)
    ? loadingViolationSource
    : Object.entries(loadingViolationSource).map(([element, violation]) => ({ element, ...violation }));
  const loadingViolationIds = new Set(loadingViolations.map((violation) => violation.element));

  // Voltage data for selected element
  const voltageData = useMemo(() => {
    if (type === 'bus' && gridDiagnostics.voltage_profile[id] !== undefined) {
      return [{
        bus: id,
        voltage_pu: gridDiagnostics.voltage_profile[id],
        violation: voltageViolationIds.has(id),
      }];
    }
    return Object.entries(gridDiagnostics.voltage_profile).map(([bus, voltage]) => ({
      bus,
      voltage_pu: voltage,
      violation: voltageViolationIds.has(bus),
    }));
  }, [gridDiagnostics, type, id]);

  // Loading data for selected element
  const loadingData = useMemo(() => {
    if (type === 'feeder' || type === 'transformer') {
      const loading = type === 'feeder'
        ? gridDiagnostics.loading_profile.lines[id]
        : gridDiagnostics.loading_profile.trafos[id];
      if (loading !== undefined) {
        return [{
          element: id,
          loading_pct: loading * 100,
          violation: loadingViolationIds.has(id),
        }];
      }
    }
    return [
      ...Object.entries(gridDiagnostics.loading_profile.lines).map(([line, loading]) => ({
        element: line,
        loading_pct: loading * 100,
        violation: loadingViolationIds.has(line),
        type: 'line' as const,
      })),
      ...Object.entries(gridDiagnostics.loading_profile.trafos).map(([trafo, loading]) => ({
        element: trafo,
        loading_pct: loading * 100,
        violation: loadingViolationIds.has(trafo),
        type: 'transformer' as const,
      })),
    ];
  }, [gridDiagnostics, type, id]);

  // Time series for grid metrics
  const gridTimeSeries = useMemo(() => {
    return trajectories.map(step => {
      const diag = step.grid_diagnostics;
      if (!diag) return { timestep: step.timestep };

      const voltages = Object.values(diag.voltage_profile || {});
      const lineLoadings = Object.values(diag.loading_profile?.lines || {});
      const trafoLoadings = Object.values(diag.loading_profile?.trafos || {});

      return {
        timestep: step.timestep,
        min_voltage: voltages.length ? Math.min(...voltages) : null,
        max_voltage: voltages.length ? Math.max(...voltages) : null,
        avg_voltage: voltages.length ? voltages.reduce((a, b) => a + b, 0) / voltages.length : null,
        max_line_loading: lineLoadings.length ? Math.max(...lineLoadings) * 100 : null,
        max_trafo_loading: trafoLoadings.length ? Math.max(...trafoLoadings) * 100 : null,
        converged: diag.power_flow_converged ? 1 : 0,
      };
    });
  }, [trajectories]);

  const getVoltageStatus = (v: number) => {
    if (v < 0.95) return { label: 'Low', color: 'text-ev', icon: TrendingDown };
    if (v > 1.05) return { label: 'High', color: 'text-violation', icon: TrendingUp };
    return { label: 'Normal', color: 'text-energy', icon: CheckCircle };
  };

  const getLoadingStatus = (l: number) => {
    if (l > 100) return { label: 'Overloaded', color: 'text-violation', icon: AlertTriangle };
    if (l > 80) return { label: 'High', color: 'text-sun', icon: TrendingUp };
    return { label: 'Normal', color: 'text-energy', icon: CheckCircle };
  };

  return (
    <div className="space-y-4">
      {/* Grid Status Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Zap className="w-6 h-6 text-grid" />
          <div>
            <h3 className="font-display font-semibold text-body text-text">Grid Explorer</h3>
            <p className="text-caption text-text-muted">
              {gridDiagnostics.power_flow_converged
                ? <span className="flex items-center gap-1 text-energy"><CheckCircle className="w-3 h-3" /> Power Flow Converged</span>
                : <span className="flex items-center gap-1 text-violation"><AlertTriangle className="w-3 h-3" /> Power Flow Diverged</span>
              }
            </p>
          </div>
        </div>
        <Button variant="ghost" size="icon" aria-label="Download grid data">
          <Download className="w-4 h-4" />
        </Button>
      </div>

      {/* Selected Element Details */}
      {type === 'bus' && voltageData.length === 1 && (
        <div className="glass-card p-4">
          <h4 className="font-body font-medium text-body-sm text-text mb-3">Bus {id} Details</h4>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-caption text-text-muted">Voltage</p>
              <p className="metric-value font-mono text-data text-2xl">{voltageData[0].voltage_pu.toFixed(4)} p.u.</p>
            </div>
            <div>
              <p className="text-caption text-text-muted">Status</p>
              <div className="flex items-center gap-2">
                {(() => {
                  const status = getVoltageStatus(voltageData[0].voltage_pu);
                  const Icon = status.icon;
                  return (
                    <span className={clsx('flex items-center gap-1 font-medium', status.color)}>
                      <Icon className="w-4 h-4" />
                      {status.label}
                    </span>
                  );
                })()}
              </div>
            </div>
            <div>
              <p className="text-caption text-text-muted">Limits</p>
              <p className="metric-value font-mono text-data text-sm">0.95 – 1.05 p.u.</p>
            </div>
            <div>
              <p className="text-caption text-text-muted">Violation</p>
              <p className={clsx('metric-value font-mono', voltageData[0].violation ? 'text-violation' : 'text-energy')}>
                {voltageData[0].violation ? 'Yes' : 'No'}
              </p>
            </div>
          </div>
        </div>
      )}

      {type === 'feeder' && loadingData.length === 1 && (
        <div className="glass-card p-4">
          <h4 className="font-body font-medium text-body-sm text-text mb-3">Feeder {id} Details</h4>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-caption text-text-muted">Loading</p>
              <p className="metric-value font-mono text-data text-2xl">{loadingData[0].loading_pct.toFixed(1)}%</p>
            </div>
            <div>
              <p className="text-caption text-text-muted">Status</p>
              <div className="flex items-center gap-2">
                {(() => {
                  const status = getLoadingStatus(loadingData[0].loading_pct);
                  const Icon = status.icon;
                  return (
                    <span className={clsx('flex items-center gap-1 font-medium', status.color)}>
                      <Icon className="w-4 h-4" />
                      {status.label}
                    </span>
                  );
                })()}
              </div>
            </div>
            <div>
              <p className="text-caption text-text-muted">Limit</p>
              <p className="metric-value font-mono text-data text-sm">100%</p>
            </div>
            <div>
              <p className="text-caption text-text-muted">Violation</p>
              <p className={clsx('metric-value font-mono', loadingData[0].violation ? 'text-violation' : 'text-energy')}>
                {loadingData[0].violation ? 'Yes' : 'No'}
              </p>
            </div>
          </div>
        </div>
      )}

      {type === 'transformer' && loadingData.length === 1 && (
        <div className="glass-card p-4">
          <h4 className="font-body font-medium text-body-sm text-text mb-3">Transformer {id} Details</h4>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-caption text-text-muted">Loading</p>
              <p className="metric-value font-mono text-data text-2xl">{loadingData[0].loading_pct.toFixed(1)}%</p>
            </div>
            <div>
              <p className="text-caption text-text-muted">Status</p>
              <div className="flex items-center gap-2">
                {(() => {
                  const status = getLoadingStatus(loadingData[0].loading_pct);
                  const Icon = status.icon;
                  return (
                    <span className={clsx('flex items-center gap-1 font-medium', status.color)}>
                      <Icon className="w-4 h-4" />
                      {status.label}
                    </span>
                  );
                })()}
              </div>
            </div>
            <div>
              <p className="text-caption text-text-muted">Capacity</p>
              <p className="metric-value font-mono text-data text-sm">{data?.capacity_kva || 630} kVA</p>
            </div>
            <div>
              <p className="text-caption text-text-muted">Violation</p>
              <p className={clsx('metric-value font-mono', loadingData[0].violation ? 'text-violation' : 'text-energy')}>
                {loadingData[0].violation ? 'Yes' : 'No'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Voltage Profile Table */}
      <div className="space-y-2">
        <h4 className="font-body font-medium text-body-sm text-text">Voltage Profile</h4>
        <div className="glass-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/30 bg-surface/50">
                  <th className="text-left p-2 text-caption text-text-muted">Bus</th>
                  <th className="text-right p-2 text-caption text-text-muted">Voltage (p.u.)</th>
                  <th className="text-left p-2 text-caption text-text-muted">Status</th>
                </tr>
              </thead>
              <tbody>
                {voltageData.slice(0, 20).map((v) => {
                  const status = getVoltageStatus(v.voltage_pu);
                  const Icon = status.icon;
                  return (
                    <tr key={v.bus} className="border-b border-border/20 hover:bg-white/5">
                      <td className="p-2 font-mono text-data">{v.bus}</td>
                      <td className="p-2 text-right font-mono text-data">{v.voltage_pu.toFixed(4)}</td>
                      <td className="p-2">
                        <span className={clsx('flex items-center gap-1 font-medium', status.color)}>
                          <Icon className="w-3 h-3" />
                          {status.label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
                {voltageData.length > 20 && (
                  <tr>
                    <td colSpan={3} className="p-2 text-center text-caption text-text-muted">
                      +{voltageData.length - 20} more buses
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Loading Profile Table */}
      <div className="space-y-2">
        <h4 className="font-body font-medium text-body-sm text-text">Loading Profile</h4>
        <div className="glass-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/30 bg-surface/50">
                  <th className="text-left p-2 text-caption text-text-muted">Element</th>
                  <th className="text-left p-2 text-caption text-text-muted">Type</th>
                  <th className="text-right p-2 text-caption text-text-muted">Loading (%)</th>
                  <th className="text-left p-2 text-caption text-text-muted">Status</th>
                </tr>
              </thead>
              <tbody>
                {loadingData.slice(0, 20).map((l: { element: string; loading_pct: number; violation: boolean; type?: string }) => {
                  const status = getLoadingStatus(l.loading_pct);
                  const Icon = status.icon;
                  return (
                    <tr key={l.element} className="border-b border-border/20 hover:bg-white/5">
                      <td className="p-2 font-mono text-data">{l.element}</td>
                      <td className="p-2 text-caption capitalize text-text-muted">{l.type || 'line'}</td>
                      <td className="p-2 text-right font-mono text-data">{l.loading_pct.toFixed(1)}</td>
                      <td className="p-2">
                        <span className={clsx('flex items-center gap-1 font-medium', status.color)}>
                          <Icon className="w-3 h-3" />
                          {status.label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
                {loadingData.length > 20 && (
                  <tr>
                    <td colSpan={4} className="p-2 text-center text-caption text-text-muted">
                      +{loadingData.length - 20} more elements
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Time Series Charts */}
      {gridTimeSeries.length > 0 && (
        <div className="space-y-4">
          <h4 className="font-body font-medium text-body-sm text-text">Grid Time Series</h4>

          <TimeSeriesChart
            data={gridTimeSeries}
            metrics={['min_voltage', 'max_voltage', 'avg_voltage']}
            height={180}
            showLegend={true}
          />

          <TimeSeriesChart
            data={gridTimeSeries}
            metrics={['max_line_loading', 'max_trafo_loading']}
            height={180}
            showLegend={true}
          />
        </div>
      )}

      {/* Violations Summary */}
      {(voltageViolations.length > 0 || loadingViolations.length > 0) && (
        <div className="space-y-2">
          <h4 className="font-body font-medium text-body-sm text-text">Active Violations</h4>
          <div className="glass-card p-3 space-y-2">
            {voltageViolations.map((v, i) => (
              <div key={`v-${i}`} className="flex items-center justify-between p-2 bg-violation/10 rounded-lg border border-violation/20">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-violation" />
                  <span className="font-mono text-data text-sm">{v.bus}</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-violation font-mono">{v.value.toFixed(4)} p.u.</span>
                  <span className="text-text-muted">limit: {v.limit.toFixed(2)}</span>
                </div>
              </div>
            ))}
            {loadingViolations.map((v, i) => (
              <div key={`l-${i}`} className="flex items-center justify-between p-2 bg-violation/10 rounded-lg border border-violation/20">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-violation" />
                  <span className="font-mono text-data text-sm">{v.element}</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-violation font-mono">{v.value.toFixed(1)}%</span>
                  <span className="text-text-muted">limit: {v.limit.toFixed(0)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}