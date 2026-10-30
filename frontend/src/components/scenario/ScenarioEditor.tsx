import { useState } from 'react';
import { ChevronDown, ChevronRight, Save, Download, Upload, X, Plus, Trash2, RotateCcw, Play } from 'lucide-react';
import { Button } from '../ui/Button';
import { Input, Select, Textarea } from '../ui/Input';
import { Slider } from '../ui/Slider';
import { Modal } from '../ui/Modal';
import { useScenarioStore } from '../../store/scenarioStore';
import type { ScenarioConfig } from '../../api/types';

interface ScenarioEditorProps {
  onSave?: (scenario: ScenarioConfig) => void;
  onRun?: (scenario: ScenarioConfig) => void;
  readOnly?: boolean;
}

const objectiveOptions = [
  'minimize_cost',
  'minimize_peak',
  'maximize_renewable_self_consumption',
  'preserve_ev_service',
  'preserve_comfort',
  'minimize_emissions',
  'maximize_fairness',
];

const gridModelOptions = [
  'simbench_lv_grid_1',
  'simbench_lv_grid_2',
  'ieee_13_node',
  'ieee_34_node',
  'ieee_123_node',
];

export function ScenarioEditor({ onSave, onRun, readOnly = false }: ScenarioEditorProps) {
  const {
    currentScenario,
    updateScenarioField,
    scenarios,
    addScenario,
    deleteScenario,
    setCurrentScenario,
  } = useScenarioStore();

  const [expandedSections, setExpandedSections] = useState<string[]>(['community', 'assets', 'grid', 'control', 'pricing']);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [yamlText, setYamlText] = useState('');

  const toggleSection = (section: string) => {
    setExpandedSections(prev => prev.includes(section)
      ? prev.filter(s => s !== section)
      : [...prev, section]
    );
  };

  const handleSave = () => {
    if (saveName.trim() && currentScenario) {
      const newScenario = { ...currentScenario, community: { ...currentScenario.community, name: saveName } };
      addScenario(newScenario);
      onSave?.(newScenario);
      setShowSaveDialog(false);
      setSaveName('');
    }
  };

  const handleRun = () => {
    onRun?.(currentScenario!);
  };

  const handleExportYaml = () => {
    const yaml = jsYamlDump(currentScenario);
    setYamlText(yaml);
    // Trigger download
    const blob = new Blob([yaml], { type: 'application/x-yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentScenario?.community.name || 'scenario'}.yaml`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleImportYaml = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        try {
          const yaml = event.target?.result as string;
          const parsed = jsYamlLoad(yaml);
          setCurrentScenario(parsed);
        } catch (error) {
          console.error('Failed to parse YAML:', error);
        }
      };
      reader.readAsText(file);
    }
  };

  if (!currentScenario) return null;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="font-display font-semibold text-heading-2 text-text">Scenario Editor</h2>
          <span className="badge badge-sun">{currentScenario.community.name}</span>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={handleExportYaml} aria-label="Export YAML">
            <Download className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="icon" aria-label="Import YAML">
            <Upload className="w-4 h-4" />
            <input
              type="file"
              accept=".yaml,.yml"
              onChange={handleImportYaml}
              className="hidden"
              id="yaml-import"
            />
            <label htmlFor="yaml-import" className="cursor-pointer" />
          </Button>
          {!readOnly && (
            <Button variant="secondary" onClick={() => setShowSaveDialog(true)}>
              <Save className="w-4 h-4 mr-2" />
              Save As
            </Button>
          )}
          <Button variant="primary" onClick={handleRun} disabled={readOnly}>
            <Play className="w-4 h-4 mr-2" />
            Run Simulation
          </Button>
        </div>
      </div>

      {/* Scenario Form */}
      <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); handleSave(); }}>
        {/* Community Section */}
        <ScenarioSection
          title="Community"
          icon="🏘️"
          expanded={expandedSections.includes('community')}
          onToggle={() => toggleSection('community')}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input
              label="Community Name"
              value={currentScenario.community.name}
              onChange={(e) => updateScenarioField('community.name', e.target.value)}
              placeholder="Eco-District A"
            />
            <Input
              label="Number of Buildings"
              type="number"
              value={currentScenario.community.buildings}
              onChange={(e) => updateScenarioField('community.buildings', parseInt(e.target.value) || 0)}
              min={1}
              max={5}
            />
            <Select
              label="Simulation Period"
              value={currentScenario.community.simulation_period}
              onChange={(e) => updateScenarioField('community.simulation_period', e.target.value)}
              options={[
                { value: '1_day', label: '1 Day (24 hourly steps)' },
                { value: '7_days', label: '1 Week (168 hourly steps)' },
              ]}
            />
            <Input
              label="Timestep (minutes)"
              type="number"
              value={60}
              disabled
            />
          </div>
        </ScenarioSection>

        {/* Assets Section */}
        <ScenarioSection
          title="Assets"
          icon="⚡"
          expanded={expandedSections.includes('assets')}
          onToggle={() => toggleSection('assets')}
        >
          <div className="space-y-4">
            {/* PV */}
            <div className="glass-card p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-xl">☀️</span>
                  <h4 className="font-body font-medium text-body text-text">Rooftop PV</h4>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Slider
                  label="PV Penetration"
                  min={0}
                  max={1}
                  step={0.05}
                  value={currentScenario.assets.pv.penetration}
                  onChange={(v) => updateScenarioField('assets.pv.penetration', v)}
                  valueFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                />
                <Select
                  label="Orientation"
                  value={currentScenario.assets.pv.orientation}
                  onChange={(e) => updateScenarioField('assets.pv.orientation', e.target.value)}
                  options={[
                    { value: 'rooftop', label: 'Rooftop' },
                    { value: 'ground', label: 'Ground-mounted' },
                    { value: 'mixed', label: 'Mixed' },
                  ]}
                />
              </div>
            </div>

            {/* Batteries */}
            <div className="glass-card p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-xl">🔋</span>
                  <h4 className="font-body font-medium text-body text-text">Batteries</h4>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Input
                  label="Community Capacity (kWh)"
                  type="number"
                  value={currentScenario.assets.batteries.community_capacity_kwh}
                  onChange={(e) => updateScenarioField('assets.batteries.community_capacity_kwh', parseInt(e.target.value) || 0)}
                  min={0}
                  max={5000}
                />
                <Input
                  label="Max Power (kW)"
                  type="number"
                  value={currentScenario.assets.batteries.max_power_kw}
                  onChange={(e) => updateScenarioField('assets.batteries.max_power_kw', parseInt(e.target.value) || 0)}
                  min={0}
                  max={2000}
                />
              </div>
            </div>

            {/* EVs */}
            <div className="glass-card p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-xl">🚗</span>
                  <h4 className="font-body font-medium text-body text-text">EV Fleet</h4>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Input
                  label="Number of EVs"
                  type="number"
                  value={currentScenario.assets.evs.number}
                  onChange={(e) => updateScenarioField('assets.evs.number', parseInt(e.target.value) || 0)}
                  min={0}
                  max={500}
                />
                <Input
                  label="Departure SOC Requirement"
                  type="number"
                  step="0.05"
                  value={currentScenario.assets.evs.departure_soc_requirement}
                  onChange={(e) => updateScenarioField('assets.evs.departure_soc_requirement', parseFloat(e.target.value) || 0)}
                  min={0}
                  max={1}
                />
                <div className="md:col-span-3">
                  <label className="block text-caption text-text-muted mb-1.5">Charging Power Options (kW)</label>
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
                          <X className="w-3 h-3" />
                        </Button>
                      </span>
                    ))}
                    <Button variant="ghost" size="sm" onClick={(e) => {
                      e.preventDefault();
                      const newPower = prompt('Enter charging power (kW):');
                      if (newPower) {
                        updateScenarioField('assets.evs.charging_power_kw', [...currentScenario.assets.evs.charging_power_kw, parseInt(newPower)]);
                      }
                    }}>
                      <Plus className="w-4 h-4 mr-1" />
                      Add Power Level
                    </Button>
                  </div>
                </div>
              </div>
            </div>

            {/* Flexible Loads */}
            <div className="glass-card p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-xl">⚙️</span>
                  <h4 className="font-body font-medium text-body text-text">Flexible Loads</h4>
                </div>
              </div>
              <Slider
                label="Flexible Load Share"
                min={0}
                max={1}
                step={0.05}
                value={currentScenario.assets.flexible_loads.share}
                onChange={(v) => updateScenarioField('assets.flexible_loads.share', v)}
                valueFormatter={(v) => `${(v * 100).toFixed(0)}%`}
              />
            </div>
          </div>
        </ScenarioSection>

        {/* Grid Section */}
        <ScenarioSection
          title="Grid"
          icon="🔌"
          expanded={expandedSections.includes('grid')}
          onToggle={() => toggleSection('grid')}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Select
              label="Grid Model"
              value={currentScenario.grid.model}
              onChange={(e) => updateScenarioField('grid.model', e.target.value)}
              options={gridModelOptions.map(v => ({ value: v, label: v }))}
            />
            <Input
              label="Transformer Capacity (kVA)"
              type="number"
              value={currentScenario.grid.transformer_capacity_kva}
              onChange={(e) => updateScenarioField('grid.transformer_capacity_kva', parseInt(e.target.value) || 0)}
              min={100}
              max={5000}
            />
            <div className="md:col-span-2">
              <label className="block text-caption text-text-muted mb-1.5">Voltage Limits (p.u.)</label>
              <div className="flex gap-4">
                <Input
                  label="Min"
                  type="number"
                  step="0.01"
                  value={currentScenario.grid.voltage_limits_pu[0]}
                  onChange={(e) => updateScenarioField('grid.voltage_limits_pu', [parseFloat(e.target.value) || 0.95, currentScenario.grid.voltage_limits_pu[1]])}
                  min={0.9}
                  max={1.0}
                  className="w-32"
                />
                <Input
                  label="Max"
                  type="number"
                  step="0.01"
                  value={currentScenario.grid.voltage_limits_pu[1]}
                  onChange={(e) => updateScenarioField('grid.voltage_limits_pu', [currentScenario.grid.voltage_limits_pu[0], parseFloat(e.target.value) || 1.05])}
                  min={1.0}
                  max={1.1}
                  className="w-32"
                />
              </div>
            </div>
            <Input
              label="Import Limit (kW)"
              type="number"
              value={currentScenario.grid.import_limit_kw}
              onChange={(e) => updateScenarioField('grid.import_limit_kw', parseInt(e.target.value) || 0)}
              min={0}
              max={5000}
            />
            <Input
              label="Export Limit (kW)"
              type="number"
              value={currentScenario.grid.export_limit_kw}
              onChange={(e) => updateScenarioField('grid.export_limit_kw', parseInt(e.target.value) || 0)}
              min={0}
              max={5000}
            />
          </div>
        </ScenarioSection>

        {/* Control Section */}
        <ScenarioSection
          title="Control Strategy"
          icon="🎯"
          expanded={expandedSections.includes('control')}
          onToggle={() => toggleSection('control')}
        >
          <div className="space-y-4">
            <Select
              label="Control Strategy"
              value={currentScenario.control.strategy}
              onChange={(e) => updateScenarioField('control.strategy', e.target.value)}
              options={[
                { value: 'rule_based', label: 'Rule-Based' },
                { value: 'multi_agent', label: 'Multi-Agent Heuristic' },
                { value: 'centralized', label: 'Centralized Heuristic' },
              ]}
            />
            <div>
              <label className="block text-caption text-text-muted mb-1.5">Objectives</label>
              <div className="flex flex-wrap gap-2">
                {objectiveOptions.map(obj => (
                  <label key={obj} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={currentScenario.control.objective.includes(obj)}
                      onChange={(e) => {
                        const newObjectives = e.target.checked
                          ? [...currentScenario.control.objective, obj]
                          : currentScenario.control.objective.filter(o => o !== obj);
                        updateScenarioField('control.objective', newObjectives);
                      }}
                      className="w-4 h-4 rounded border-border bg-space text-sun focus:ring-sun"
                    />
                    <span className="text-body-sm text-text">{obj.replace(/_/g, ' ')}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        </ScenarioSection>

        {/* Pricing Regime Section (Phase 2) */}
        <ScenarioSection
          title="Pricing Regime"
          icon="💰"
          expanded={expandedSections.includes('pricing')}
          onToggle={() => toggleSection('pricing')}
        >
          <div className="space-y-4">
            <div className="glass-card p-4">
              <h4 className="font-body font-medium text-body text-text mb-3">Pricing Regime Selector</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Select
                  label="Pricing Regime"
                  value={currentScenario.energy_sharing?.enabled && currentScenario.energy_sharing.market_type === 'lmp' && currentScenario.energy_sharing.dynamic_pricing?.enabled ? 'lmp' :
                        currentScenario.energy_sharing?.enabled && currentScenario.energy_sharing.market_type === 'uniform_price' ? 'pool_tou' :
                        'tou_solo'}
                  onChange={(e) => {
                    const regime = e.target.value;
                    if (regime === 'lmp') {
                      updateScenarioField('energy_sharing', {
                        enabled: true,
                        market_type: 'lmp',
                        settlement_interval: '1h',
                        dynamic_pricing: {
                          enabled: true,
                          pricing_type: 'lmp',
                          lmp_update_interval_minutes: 60,
                          congestion_cost_method: 'dc_approx',
                          loss_factor: 1.0,
                          price_cap_per_kwh: 1.0,
                          fallback_to_tariff: true,
                        },
                      });
                    } else if (regime === 'pool_tou') {
                      updateScenarioField('energy_sharing', {
                        enabled: true,
                        market_type: 'uniform_price',
                        settlement_interval: '1h',
                        dynamic_pricing: undefined,
                      });
                    } else {
                      updateScenarioField('energy_sharing', {
                        enabled: false,
                        market_type: 'uniform_price',
                        settlement_interval: '1h',
                        dynamic_pricing: undefined,
                      });
                    }
                  }}
                  options={[
                    { value: 'tou_solo', label: 'TOU Solo (no sharing, static TOU)' },
                    { value: 'pool_tou', label: 'Pool TOU (community pool, uniform price)' },
                    { value: 'lmp', label: 'LMP (community pool, locational marginal pricing)' },
                  ]}
                />
                <Select
                  label="Cost Basis"
                  value={currentScenario.energy_sharing?.dynamic_pricing?.enabled ? 'lmp' : 'tariff'}
                  onChange={(e) => {
                    const basis = e.target.value;
                    if (basis === 'lmp') {
                      updateScenarioField('energy_sharing', {
                        ...currentScenario.energy_sharing,
                        dynamic_pricing: {
                          ...currentScenario.energy_sharing?.dynamic_pricing,
                          enabled: true,
                          pricing_type: 'lmp',
                        },
                      });
                    } else {
                      updateScenarioField('energy_sharing', {
                        ...currentScenario.energy_sharing,
                        dynamic_pricing: {
                          ...currentScenario.energy_sharing?.dynamic_pricing,
                          enabled: false,
                        },
                      });
                    }
                  }}
                  options={[
                    { value: 'tariff', label: 'Tariff (static rates)' },
                    { value: 'lmp', label: 'LMP (locational marginal pricing)' },
                  ]}
                />
              </div>
              <div className="mt-3 p-3 bg-surface/50 rounded-lg text-caption text-text-muted">
                <p><strong>Regime Definitions:</strong></p>
                <ul className="list-disc list-inside mt-1 space-y-1">
                  <li><strong>tou_solo:</strong> No community pool, static TOU tariff per building</li>
                  <li><strong>pool_tou:</strong> Community pool enabled, uniform price clearing (Phase 1)</li>
                  <li><strong>lmp:</strong> Community pool with locational marginal pricing, dynamic per-building prices</li>
                </ul>
              </div>
            </div>

            {currentScenario.energy_sharing?.enabled && currentScenario.energy_sharing.market_type === 'lmp' && (
              <div className="glass-card p-4">
                <h4 className="font-body font-medium text-body text-text mb-3">LMP Dynamic Pricing Configuration</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Input
                    label="Price Cap ($/kWh)"
                    type="number"
                    step="0.01"
                    value={currentScenario.energy_sharing.dynamic_pricing?.price_cap_per_kwh ?? 1.0}
                    onChange={(e) => updateScenarioField('energy_sharing.dynamic_pricing.price_cap_per_kwh', parseFloat(e.target.value) || 0)}
                    min={0}
                    max={5}
                  />
                  <Input
                    label="LMP Update Interval (min)"
                    type="number"
                    value={currentScenario.energy_sharing.dynamic_pricing?.lmp_update_interval_minutes ?? 60}
                    onChange={(e) => updateScenarioField('energy_sharing.dynamic_pricing.lmp_update_interval_minutes', parseInt(e.target.value) || 60)}
                    min={15}
                    max={1440}
                  />
                  <Input
                    label="Congestion Cost Method"
                    value={currentScenario.energy_sharing.dynamic_pricing?.congestion_cost_method ?? 'dc_approx'}
                    onChange={(e) => updateScenarioField('energy_sharing.dynamic_pricing.congestion_cost_method', e.target.value)}
                    placeholder="dc_approx"
                  />
                  <Input
                    label="Loss Factor"
                    type="number"
                    step="0.01"
                    value={currentScenario.energy_sharing.dynamic_pricing?.loss_factor ?? 1.0}
                    onChange={(e) => updateScenarioField('energy_sharing.dynamic_pricing.loss_factor', parseFloat(e.target.value) || 1.0)}
                    min={0.5}
                    max={2.0}
                  />
                  <Select
                    label="Fallback to Tariff on OPF Failure"
                    value={String(currentScenario.energy_sharing.dynamic_pricing?.fallback_to_tariff ?? true)}
                    onChange={(e) => updateScenarioField('energy_sharing.dynamic_pricing.fallback_to_tariff', e.target.value === 'true')}
                    options={[
                      { value: 'true', label: 'Yes (safe fallback)' },
                      { value: 'false', label: 'No (fail hard)' },
                    ]}
                  />
                </div>
              </div>
            )}
          </div>
        </ScenarioSection>

        {/* YAML View */}
        <ScenarioSection
          title="Raw YAML"
          icon="📄"
          expanded={expandedSections.includes('yaml')}
          onToggle={() => toggleSection('yaml')}
        >
          <Textarea
            value={yamlText || jsYamlDump(currentScenario)}
            onChange={(e) => setYamlText(e.target.value)}
            rows={20}
            placeholder="YAML representation of the scenario..."
            className="font-mono text-body-sm"
          />
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setYamlText(jsYamlDump(currentScenario))}>
              <RotateCcw className="w-4 h-4 mr-1" />
              Reset from Form
            </Button>
            <Button variant="ghost" onClick={() => {
              try {
                const parsed = jsYamlLoad(yamlText);
                setCurrentScenario(parsed);
              } catch (error) {
                console.error('Invalid YAML:', error);
              }
            }}>
              Apply YAML
            </Button>
          </div>
        </ScenarioSection>
      </form>

      {/* Saved Scenarios List */}
      {scenarios.length > 0 && (
        <div className="space-y-2">
          <h3 className="font-body font-medium text-body-sm text-text">Saved Scenarios</h3>
          <div className="space-y-2">
            {scenarios.map((scenario) => (
              <div key={scenario.community.name} className="glass-card p-3 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-xl">📋</span>
                  <div>
                    <p className="font-body font-medium text-body text-text">{scenario.community.name}</p>
                    <p className="text-caption text-text-muted">
                      {scenario.community.buildings} buildings · {scenario.assets.evs.number} EVs · {scenario.grid.model}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <Button variant="ghost" size="icon" onClick={() => setCurrentScenario(scenario)} aria-label="Load scenario">
                    <RotateCcw className="w-4 h-4" />
                  </Button>
                  <Button variant="ghost" size="icon" onClick={() => deleteScenario(scenario.community.name)} aria-label="Delete scenario">
                    <Trash2 className="w-4 h-4 text-violation" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Save Dialog */}
      <Modal
        isOpen={showSaveDialog}
        onClose={() => setShowSaveDialog(false)}
        title="Save Scenario"
        size="sm"
      >
        <div className="space-y-4">
          <Input
            label="Scenario Name"
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
            placeholder="Enter a name for this scenario"
            autoFocus
          />
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setShowSaveDialog(false)}>Cancel</Button>
            <Button variant="primary" onClick={handleSave} disabled={!saveName.trim()}>Save</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

import { isFeatureEnabled } from '../../config/featureFlags';

// YAML serializer/parser - gated behind feature flag
function jsYamlDump(obj: any): string {
  if (isFeatureEnabled('yamlExport')) {
    // In production, use js-yaml: import { dump } from 'js-yaml'; return dump(obj);
    return JSON.stringify(obj, null, 2);
  }
  return JSON.stringify(obj, null, 2);
}

function jsYamlLoad(str: string): any {
  if (isFeatureEnabled('yamlExport')) {
    // In production, use js-yaml: import { load } from 'js-yaml'; return load(str);
    return JSON.parse(str);
  }
  return JSON.parse(str);
}

function ScenarioSection({ title, icon, expanded, onToggle, children }: {
  title: string;
  icon: string;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="glass-card overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 p-3 hover:bg-white/5 transition-colors"
        aria-expanded={expanded}
      >
        <span className="text-xl">{icon}</span>
        <h3 className="font-display font-medium text-body text-text flex-1">{title}</h3>
        {expanded ? <ChevronDown className="w-5 h-5 text-text-muted" /> : <ChevronRight className="w-5 h-5 text-text-muted" />}
      </button>
      {expanded && (
        <div className="border-t border-border/30 p-4 animate-slide-down">
          {children}
        </div>
      )}
    </div>
  );
}