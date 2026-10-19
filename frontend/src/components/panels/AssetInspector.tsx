import { useMemo } from 'react';
import { clsx } from 'clsx';
import { Sun, Zap, Battery, Car, TrendingUp, TrendingDown, Activity, Settings, Download } from 'lucide-react';
import { Button } from '../ui/Button';
import { TimeSeriesChart } from './TimeSeriesChart';
import type { SelectedAsset, TimeStepData } from '../../api/types';

interface AssetInspectorProps {
  asset: SelectedAsset;
  timestepData: Record<string, any>;
  trajectories: TimeStepData[];
}

const assetIcons = {
  building: '🏢',
  pv: '☀️',
  battery: '🔋',
  ev: '🚗',
  flexible_load: '⚙️',
};

// Format functions defined outside component
const formatPercent = (v: number) => `${(v * 100).toFixed(0)}%`;
const formatPercent1 = (v: number) => `${(v * 100).toFixed(1)}%`;
const formatPower = (v: number) => v > 0 ? `+${v.toFixed(1)}` : v.toFixed(1);

const metricDefinitions: Record<string, any[]> = {
  building: [
    { key: 'net_electricity_consumption', label: 'Net Load', unit: 'kW', icon: Zap, color: 'text-load' },
    { key: 'solar_generation', label: 'PV Generation', unit: 'kW', icon: Sun, color: 'text-sun' },
    { key: 'electrical_storage_soc', label: 'Battery SOC', unit: '%', icon: Battery, color: 'text-battery', format: formatPercent },
    { key: 'indoor_temperature', label: 'Indoor Temp', unit: '°C', icon: Activity, color: 'text-comfort' },
    { key: 'cooling_demand', label: 'Cooling Demand', unit: 'kW', icon: TrendingDown, color: 'text-comfort' },
    { key: 'heating_demand', label: 'Heating Demand', unit: 'kW', icon: TrendingUp, color: 'text-load' },
  ],
  pv: [
    { key: 'solar_generation', label: 'Generation', unit: 'kW', icon: Sun, color: 'text-sun' },
    { key: 'capacity_factor', label: 'Capacity Factor', unit: '%', icon: Activity, color: 'text-sun', format: formatPercent1 },
  ],
  battery: [
    { key: 'electrical_storage_soc', label: 'State of Charge', unit: '%', icon: Battery, color: 'text-battery', format: formatPercent },
    { key: 'battery_power_kw', label: 'Power', unit: 'kW', icon: Zap, color: 'text-energy', format: formatPower },
    { key: 'available_capacity_kwh', label: 'Available Capacity', unit: 'kWh', icon: Battery, color: 'text-battery' },
  ],
  ev: [
    { key: 'connected_electric_vehicle_at_charger_soc', label: 'State of Charge', unit: '%', icon: Battery, color: 'text-battery', format: formatPercent },
    { key: 'ev_charge_kw', label: 'Charging Power', unit: 'kW', icon: Zap, color: 'text-ev' },
    { key: 'departure_time', label: 'Departure', unit: 'step', icon: Car, color: 'text-ev' },
    { key: 'target_soc', label: 'Target SOC', unit: '%', icon: TrendingUp, color: 'text-ev', format: formatPercent },
  ],
  flexible_load: [
    { key: 'flexible_load_kw', label: 'Power', unit: 'kW', icon: Zap, color: 'text-load' },
    { key: 'deadline', label: 'Deadline', unit: 'step', icon: Activity, color: 'text-comfort' },
    { key: 'status', label: 'Status', unit: '', icon: Settings, color: 'text-comfort' },
  ],
};

// Helper component for current actions to avoid JSX parsing issues
function CurrentActionsDisplay({ actions }: { actions: Record<string, number> }) {
  const entries = Object.entries(actions);
  if (entries.length === 0) return null;

  return (
    <div className="space-y-2">
      <h4 className="font-body font-medium text-body-sm text-text">Current Actions</h4>
      <div className="grid grid-cols-2 gap-2">
        {entries.map(([actionType, value]) => {
          const isPositive = value > 0;
          const isNegative = value < 0;
          const valueColor = isPositive ? 'text-energy' : isNegative ? 'text-load' : 'text-text';
          const prefix = isPositive ? '+' : '';
          const displayValue = prefix + value.toFixed(1) + ' kW';
          return (
            <div key={actionType} className="glass-card p-3">
              <div className="flex items-center justify-between">
                <span className="text-caption text-text-muted capitalize">{actionType.replace('_', ' ')}</span>
                <span className={clsx('metric-value font-mono', valueColor)}>
                  {displayValue}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function AssetInspector({ asset, timestepData, trajectories }: AssetInspectorProps) {
  const { type, id, data } = asset;
  const icon = assetIcons[type as keyof typeof assetIcons] || '📦';

  // Get current timestep data for this asset
  const currentData = useMemo(() => {
    const prefix = `${id}_`;
    const result: Record<string, number> = {};
    Object.entries(timestepData).forEach(([key, value]) => {
      if (key.startsWith(prefix)) {
        result[key.slice(prefix.length)] = typeof value === 'number' ? value : 0;
      }
    });
    return result;
  }, [timestepData, id]);

  // Get time series for this asset
  const timeSeries = useMemo(() => {
    return trajectories.map(step => {
      const prefix = `${id}_`;
      const point: Record<string, number> = { timestep: step.timestep };
      Object.entries(step.observations).forEach(([key, value]) => {
        if (key.startsWith(prefix)) {
          point[key.slice(prefix.length)] = typeof value === 'number' ? value : 0;
        }
      });
      step.applied_actions?.forEach(action => {
        if (action.asset_id === id) {
          point[`action_${action.action_type}`] = action.value_kw;
        }
      });
      return point;
    });
  }, [trajectories, id]);

  const metrics = metricDefinitions[type] || [];

  if (metrics.length === 0) {
    return (
      <div className="glass-card p-4 text-center text-text-muted">
        <span className="text-4xl mb-2 block">{icon}</span>
        <p>No metrics available for {type}</p>
      </div>
    );
  }

  // Current actions at latest timestep
  const currentActions = useMemo(() => {
    const actions: Record<string, number> = {};
    const maxTimestep = trajectories.length > 0 ? Math.max(...trajectories.map(t => t.timestep)) : 0;
    const currentStep = trajectories.find(t => t.timestep === maxTimestep);
    currentStep?.applied_actions?.forEach(action => {
      if (action.asset_id === id) {
        actions[action.action_type] = action.value_kw;
      }
    });
    return actions;
  }, [trajectories, timestepData, id]);

  return (
    <div className="space-y-4">
      {/* Asset Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-3xl">{icon}</span>
          <div>
            <h3 className="font-display font-semibold text-body text-text">{data?.name || id}</h3>
            <p className="text-caption text-text-muted capitalize">{type.replace('_', ' ')}</p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" aria-label="Download data">
            <Download className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="icon" aria-label="Settings">
            <Settings className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Current Metrics */}
      <div className="grid grid-cols-2 gap-3">
        {metrics.map((metric) => {
          const value = currentData[metric.key];
          const displayValue = value !== undefined
            ? (metric.format ? metric.format(value) : typeof value === 'number' ? value.toFixed(1) : value)
            : '—';

          return (
            <div key={metric.key} className="glass-card p-3">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <metric.icon className={clsx('w-4 h-4', metric.color)} />
                  <span className="metric-label">{metric.label}</span>
                </div>
              </div>
              <div className="flex items-baseline justify-between">
                <span className={clsx('metric-value font-mono text-data', metric.color)}>
                  {displayValue}
                </span>
                <span className="text-caption text-text-muted">{metric.unit}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Time Series Chart */}
      {timeSeries.length > 0 && metrics.length > 0 && (
        <div className="space-y-2">
          <h4 className="font-body font-medium text-body-sm text-text">Time Series</h4>
          <TimeSeriesChart
            data={timeSeries}
            metrics={metrics.map(m => m.key)}
            height={200}
            showLegend={true}
          />
        </div>
      )}

      {/* Current Actions */}
      <CurrentActionsDisplay actions={currentActions} />
    </div>
  );
}