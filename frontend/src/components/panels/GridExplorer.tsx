import { useMemo } from 'react';
import { clsx } from 'clsx';
import { Zap, AlertTriangle, CheckCircle, TrendingUp, TrendingDown } from 'lucide-react';
import { TimeSeriesChart } from './TimeSeriesChart';
import type { SelectedAsset, GridDiagnostics, TimeStepData } from '../../api/types';

interface GridExplorerProps {
  asset: SelectedAsset;
  gridDiagnostics: GridDiagnostics | undefined;
  trajectories: TimeStepData[];
}

export function GridExplorer({ asset, gridDiagnostics, trajectories }: GridExplorerProps) {
  const { type, id } = asset;

  const voltageViolationIds = useMemo(() => {
    if (!gridDiagnostics) return new Set<string>();
    const voltageViolationSource = gridDiagnostics.violations?.voltage || [];
    const voltageViolations = Array.isArray(voltageViolationSource)
      ? voltageViolationSource
      : Object.entries(voltageViolationSource).map(([bus, violation]) => ({ bus, ...violation }));
    return new Set(voltageViolations.map((violation) => violation.bus));
  }, [gridDiagnostics]);

  const loadingViolationIds = useMemo(() => {
    if (!gridDiagnostics) return new Set<string>();
    const loadingViolationSource = gridDiagnostics.violations?.loading || [];
    const loadingViolations = Array.isArray(loadingViolationSource)
      ? loadingViolationSource
      : Object.entries(loadingViolationSource).map(([element, violation]) => ({ element, ...violation }));
    return new Set(loadingViolations.map((violation) => violation.element));
  }, [gridDiagnostics]);

  // Voltage data for selected element
  const voltageData = useMemo(() => {
    if (!gridDiagnostics) return [];
    if (type === 'bus' && gridDiagnostics.voltage_profile[id] !== undefined) {
      return [{
        bus: id,
        voltage_pu: gridDiagnostics.voltage_profile[id],
        violation: voltageViolationIds.has(id),
      }];
    }
    return Object.entries(gridDiagnostics.voltage_profile || {}).map(([bus, voltage]) => ({
      bus,
      voltage_pu: voltage,
      violation: voltageViolationIds.has(bus),
    }));
  }, [gridDiagnostics, type, id, voltageViolationIds]);

  // Loading data for selected element
  const loadingData = useMemo(() => {
    if (!gridDiagnostics) return [];
    if (type === 'feeder' || type === 'transformer') {
      const loading = type === 'feeder'
        ? gridDiagnostics.loading_profile?.lines[id]
        : gridDiagnostics.loading_profile?.trafos[id];
      if (loading !== undefined) {
        return [{
          element: id,
          loading_pct: loading * 100,
          violation: loadingViolationIds.has(id),
          type: type === 'feeder' ? 'line' as const : 'transformer' as const,
        }];
      }
    }
    return [
      ...Object.entries(gridDiagnostics.loading_profile?.lines || {}).map(([line, loading]) => ({
        element: line,
        loading_pct: loading * 100,
        violation: loadingViolationIds.has(line),
        type: 'line' as const,
      })),
      ...Object.entries(gridDiagnostics.loading_profile?.trafos || {}).map(([trafo, loading]) => ({
        element: trafo,
        loading_pct: loading * 100,
        violation: loadingViolationIds.has(trafo),
        type: 'transformer' as const,
      })),
    ];
  }, [gridDiagnostics, type, id, loadingViolationIds]);

  // Time series for grid metrics
  const gridTimeSeries = useMemo(() => {
    if (!gridDiagnostics) return [];
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
  }, [trajectories, gridDiagnostics]);

  if (!gridDiagnostics) {
    return (
      <div className="glass-card p-4 text-center text-text-muted">
        <Zap className="w-12 h-12 mx-auto mb-3 text-text-muted/30" />
        <p className="text-body-sm">No grid diagnostics available</p>
        <p className="text-caption text-text-muted/50 mt-1">Run a simulation with grid coupling to see voltage and loading data</p>
      </div>
    );
  }

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
        <h3 className="font-body font-semibold text-body text-text">Grid Diagnostics</h3>
        <span className="badge badge-info">Real-time</span>
      </div>

      {/* Voltage Profile */}
      <div className="glass-card">
        <div className="p-4 border-b border-border/30 flex items-center justify-between">
          <h4 className="font-body font-medium text-body-sm text-text">Bus Voltages</h4>
          <span className="badge badge-secondary">{voltageData.length} buses</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border/30">
                <th className="text-left p-3 font-body font-medium text-body-sm text-text-muted">Bus</th>
                <th className="text-left p-3 font-body font-medium text-body-sm text-text-muted">Voltage (pu)</th>
                <th className="text-left p-3 font-body font-medium text-body-sm text-text-muted">Status</th>
              </tr>
            </thead>
            <tbody>
              {voltageData.map((item, idx) => {
                const status = getVoltageStatus(item.voltage_pu);
                return (
                  <tr key={idx} className="border-b border-border/20 hover:bg-surface/30">
                    <td className="p-3 font-mono text-body-sm text-text">{item.bus}</td>
                    <td className="p-3 font-mono text-body-sm text-text">{item.voltage_pu.toFixed(3)}</td>
                    <td className="p-3">
                      <span className={clsx('badge', status.color)}>
                        <status.icon className="w-3 h-3 mr-1" />
                        {status.label}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Line & Transformer Loadings */}
      <div className="glass-card">
        <div className="p-4 border-b border-border/30 flex items-center justify-between">
          <h4 className="font-body font-medium text-body-sm text-text">Line & Transformer Loadings</h4>
          <span className="badge badge-secondary">{loadingData.length} elements</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border/30">
                <th className="text-left p-3 font-body font-medium text-body-sm text-text-muted">Element</th>
                <th className="text-left p-3 font-body font-medium text-body-sm text-text-muted">Loading</th>
                <th className="text-left p-3 font-body font-medium text-body-sm text-text-muted">Status</th>
              </tr>
            </thead>
            <tbody>
              {loadingData.map((item, idx) => {
                const status = getLoadingStatus(item.loading_pct);
                const isTransformer = item.type === 'transformer';
                return (
                  <tr key={idx} className="border-b border-border/20 hover:bg-surface/30">
                    <td className="p-3 font-body text-body-sm text-text">
                      {isTransformer ? '⚡ ' : '🔗 '}{item.element}
                    </td>
                    <td className="p-3">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-2 bg-border rounded overflow-hidden">
                          <div
                            className={clsx('h-full rounded', status.color.replace('text-', 'bg-'))}
                            style={{ width: `${Math.min(item.loading_pct, 100)}%` }}
                          />
                        </div>
                        <span className="font-mono text-body-sm text-text w-16 text-right">{item.loading_pct.toFixed(1)}%</span>
                      </div>
                    </td>
                    <td className="p-3">
                      <span className={clsx('badge', status.color)}>
                        <status.icon className="w-3 h-3 mr-1" />
                        {status.label}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Violations Summary */}
      {voltageViolationIds.size > 0 || loadingViolationIds.size > 0 ? (
        <div className="glass-card border-violation/30">
          <div className="p-4 border-b border-border/30 flex items-center justify-between">
            <h4 className="font-body font-medium text-body-sm text-text">Active Violations</h4>
            <span className="badge badge-violation">{voltageViolationIds.size + loadingViolationIds.size} Total</span>
          </div>
          <div className="p-4 space-y-2">
            {Array.from(voltageViolationIds).map((bus, idx) => (
              <div key={idx} className="flex items-center gap-3 p-2 bg-violation/10 rounded">
                <AlertTriangle className="w-5 h-5 text-violation" />
                <span className="font-body text-body-sm text-text">Voltage violation at Bus {bus}</span>
              </div>
            ))}
            {Array.from(loadingViolationIds).map((element, idx) => (
              <div key={idx} className="flex items-center gap-3 p-2 bg-violation/10 rounded">
                <AlertTriangle className="w-5 h-5 text-violation" />
                <span className="font-body text-body-sm text-text">Loading violation: {element}</span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="glass-card">
          <div className="p-4 text-center text-text-muted">
            <CheckCircle className="w-12 h-12 mx-auto mb-3 text-energy" />
            <p className="text-body">No active violations</p>
            <p className="text-caption text-text-muted/50 mt-1">All grid parameters within normal limits</p>
          </div>
        </div>
      )}

      {/* Time Series Charts */}
      <div className="glass-card">
        <div className="p-4 border-b border-border/30 flex items-center justify-between">
          <h4 className="font-body font-medium text-body-sm text-text">Grid Metrics Over Time</h4>
        </div>
        <div className="p-4">
          <TimeSeriesChart
            data={gridTimeSeries}
            xAxisKey="timestep"
            metrics={['min_voltage', 'max_voltage', 'avg_voltage']}
            height={200}
          />
          <TimeSeriesChart
            data={gridTimeSeries}
            xAxisKey="timestep"
            metrics={['max_line_loading', 'max_trafo_loading']}
            height={200}
          />
        </div>
      </div>
    </div>
  );
}