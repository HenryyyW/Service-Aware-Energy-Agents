import { Sun, Battery, Car, Zap, Wind, Settings, RotateCcw, Play, Minus, Plus } from 'lucide-react';
import { Button } from '../ui/Button';
import { Slider } from '../ui/Slider';
import { Select } from '../ui/Input';
import { useScenarioStore } from '../../store/scenarioStore';

interface ParameterControlsProps {
  onRun?: () => void;
  running?: boolean;
}

export function ParameterControls({ onRun, running = false }: ParameterControlsProps) {
  const { currentScenario, updateScenarioField } = useScenarioStore();

  if (!currentScenario) return null;

  const handleQuickRun = () => {
    onRun?.();
  };

  const handleReset = () => {
    // Reset to defaults
    updateScenarioField('assets.pv.penetration', 0.4);
    updateScenarioField('assets.batteries.community_capacity_kwh', 800);
    updateScenarioField('assets.batteries.max_power_kw', 250);
    updateScenarioField('assets.evs.number', 35);
    updateScenarioField('assets.evs.departure_soc_requirement', 0.8);
    updateScenarioField('assets.flexible_loads.share', 0.15);
    updateScenarioField('grid.import_limit_kw', 500);
    updateScenarioField('grid.export_limit_kw', 200);
    updateScenarioField('control.strategy', 'agent_policy');
  };

  return (
    <div className="space-y-4">
      {/* Quick Actions */}
      <div className="flex items-center gap-2">
        <Button
          variant="primary"
          size="lg"
          onClick={handleQuickRun}
          disabled={running}
          className="flex-1"
        >
          {running ? (
            <>
              <div className="animate-spin w-5 h-5 mr-2 border-2 border-white/30 border-t-white rounded-full" />
              Running...
            </>
          ) : (
            <>
              <Play className="w-5 h-5 mr-2" />
              Run Simulation
            </>
          )}
        </Button>
        <Button variant="ghost" size="icon" onClick={handleReset} aria-label="Reset to defaults">
          <RotateCcw className="w-5 h-5" />
        </Button>
      </div>

      {/* PV Controls */}
      <div className="glass-card p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Sun className="w-5 h-5 text-sun" />
            <h4 className="font-body font-medium text-body text-text">PV Generation</h4>
          </div>
        </div>
        <Slider
          label="PV Penetration"
          min={0}
          max={1.5}
          step={0.05}
          value={currentScenario.assets.pv.penetration}
          onChange={(v) => updateScenarioField('assets.pv.penetration', v)}
          valueFormatter={(v) => `${(v * 100).toFixed(0)}%`}
        />
        <div className="flex items-center gap-4 mt-3 pt-3 border-t border-border/30">
          <Select
            label="Orientation"
            value={currentScenario.assets.pv.orientation}
            onChange={(e) => updateScenarioField('assets.pv.orientation', e.target.value)}
            options={[
              { value: 'rooftop', label: 'Rooftop' },
              { value: 'ground', label: 'Ground' },
              { value: 'mixed', label: 'Mixed' },
            ]}
            className="flex-1"
          />
        </div>
      </div>

      {/* Battery Controls */}
      <div className="glass-card p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Battery className="w-5 h-5 text-battery" />
            <h4 className="font-body font-medium text-body text-text">Storage</h4>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Slider
            label="Capacity (kWh)"
            min={0}
            max={5000}
            step={50}
            value={currentScenario.assets.batteries.community_capacity_kwh}
            onChange={(v) => updateScenarioField('assets.batteries.community_capacity_kwh', v)}
            valueFormatter={(v) => `${v.toLocaleString()} kWh`}
          />
          <Slider
            label="Max Power (kW)"
            min={0}
            max={2000}
            step={25}
            value={currentScenario.assets.batteries.max_power_kw}
            onChange={(v) => updateScenarioField('assets.batteries.max_power_kw', v)}
            valueFormatter={(v) => `${v.toLocaleString()} kW`}
          />
        </div>
      </div>

      {/* EV Controls */}
      <div className="glass-card p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Car className="w-5 h-5 text-ev" />
            <h4 className="font-body font-medium text-body text-text">EV Fleet</h4>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Slider
            label="Number of EVs"
            min={0}
            max={200}
            step={1}
            value={currentScenario.assets.evs.number}
            onChange={(v) => updateScenarioField('assets.evs.number', v)}
          />
          <Slider
            label="Target SOC"
            min={0.5}
            max={1.0}
            step={0.05}
            value={currentScenario.assets.evs.departure_soc_requirement}
            onChange={(v) => updateScenarioField('assets.evs.departure_soc_requirement', v)}
            valueFormatter={(v) => `${(v * 100).toFixed(0)}%`}
          />
        </div>
        <div className="mt-3 pt-3 border-t border-border/30">
          <label className="block text-caption text-text-muted mb-2">Charging Power Levels</label>
          <div className="flex flex-wrap gap-2">
            {currentScenario.assets.evs.charging_power_kw.map((power, i) => (
              <span key={i} className="badge badge-ev">
                {power} kW
                <Button variant="ghost" size="icon" className="p-0.5 ml-1" onClick={(e) => {
                  e.preventDefault();
                  const newPowers = [...currentScenario.assets.evs.charging_power_kw];
                  newPowers.splice(i, 1);
                  updateScenarioField('assets.evs.charging_power_kw', newPowers);
                }}>
                  <Minus className="w-3 h-3" />
                </Button>
              </span>
            ))}
            <Button variant="ghost" size="sm" onClick={(e) => {
              e.preventDefault();
              const newPower = prompt('Add charging power (kW):');
              if (newPower && !isNaN(parseInt(newPower))) {
                updateScenarioField('assets.evs.charging_power_kw', [...currentScenario.assets.evs.charging_power_kw, parseInt(newPower)]);
              }
            }}>
              <Plus className="w-4 h-4 mr-1" />
              Add
            </Button>
          </div>
        </div>
      </div>

      {/* Flexible Load Controls */}
      <div className="glass-card p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-load" />
            <h4 className="font-body font-medium text-body text-text">Flexible Loads</h4>
          </div>
        </div>
        <Slider
          label="Flexible Load Share"
          min={0}
          max={0.5}
          step={0.05}
          value={currentScenario.assets.flexible_loads.share}
          onChange={(v) => updateScenarioField('assets.flexible_loads.share', v)}
          valueFormatter={(v) => `${(v * 100).toFixed(0)}%`}
        />
      </div>

      {/* Grid Controls */}
      <div className="glass-card p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-grid" />
            <h4 className="font-body font-medium text-body text-text">Grid Limits</h4>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Slider
            label="Import Limit (kW)"
            min={0}
            max={2000}
            step={50}
            value={currentScenario.grid.import_limit_kw}
            onChange={(v) => updateScenarioField('grid.import_limit_kw', v)}
            valueFormatter={(v) => `${v.toLocaleString()} kW`}
          />
          <Slider
            label="Export Limit (kW)"
            min={0}
            max={1000}
            step={50}
            value={currentScenario.grid.export_limit_kw}
            onChange={(v) => updateScenarioField('grid.export_limit_kw', v)}
            valueFormatter={(v) => `${v.toLocaleString()} kW`}
          />
        </div>
      </div>

      {/* Control Strategy */}
      <div className="glass-card p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-energy" />
            <h4 className="font-body font-medium text-body text-text">Control Strategy</h4>
          </div>
        </div>
        <Select
          label="Strategy"
          value={currentScenario.control.strategy}
          onChange={(e) => updateScenarioField('control.strategy', e.target.value)}
          options={[
            { value: 'rule_based', label: 'Rule-Based' },
            { value: 'multi_agent', label: 'Multi-Agent Heuristic' },
            { value: 'centralized', label: 'Centralized' },
          ]}
        />
      </div>

      {/* Tariff */}
      <div className="glass-card p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Wind className="w-5 h-5 text-comfort" />
            <h4 className="font-body font-medium text-body text-text">Tariff</h4>
          </div>
        </div>
        <Select
          label="Tariff Profile"
          value={currentScenario.control.objective.includes('minimize_cost') ? 'TOU' : 'Flat'}
          onChange={() => {
            // Would update tariff in scenario
          }}
          options={[
            { value: 'Flat', label: 'Flat Rate' },
            { value: 'TOU', label: 'Time of Use' },
            { value: 'Real-time', label: 'Real-time Pricing' },
            { value: 'Dynamic', label: 'Dynamic' },
          ]}
        />
      </div>
    </div>
  );
}