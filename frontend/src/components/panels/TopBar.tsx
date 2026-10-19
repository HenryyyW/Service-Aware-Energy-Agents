import { MapPin, Settings, Play, Download, Upload, GitBranch, Sun, Info, Zap, Battery } from 'lucide-react';
import { Button } from '../ui/Button';
import { Select } from '../ui/Input';
import { useCanvasStore } from '../../store/canvasStore';
import { useSimulationStore } from '../../store/simulationStore';
import { api } from '../../api/client';

interface TopBarProps {
  communityName: string;
  scenarioName?: string;
  controllerType?: string;
  onScenarioChange: () => void;
  onRunSimulation: () => void;
}

export function TopBar({
  communityName,
  scenarioName,
  controllerType,
  onScenarioChange,
  onRunSimulation,
}: TopBarProps) {
  const { mapStyle, setMapStyle } = useCanvasStore();
  const { runs, currentRun, setCurrentRun, setTrajectories } = useSimulationStore();
  const selfConsumption = currentRun?.energy_metrics?.pv_self_consumption;
  const pvGeneration = currentRun?.energy_metrics?.pv_generation_kwh;
  const selfConsumptionRate = pvGeneration && pvGeneration > 0 && selfConsumption !== undefined
    ? (selfConsumption / pvGeneration) * 100
    : undefined;
  const evCompletionRate = currentRun?.service_metrics?.ev_completion_rate;

  const handleRunChange = async (runId: string) => {
    const run = runs.find((candidate) => candidate.run_id === runId);
    if (!run) return;
    setCurrentRun(run);
    try {
      setTrajectories(await api.getTrajectories(run.run_id));
    } catch (error) {
      console.error('Failed to load selected run:', error);
    }
  };

  const handleMapStyleChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setMapStyle(event.target.value as 'dark' | 'light' | 'satellite');
  };

  return (
    <header className="fixed top-0 left-0 right-0 z-40 bg-space/90 backdrop-blur-panel border-b border-border">
      <div className="max-w-full mx-auto px-4 h-14 flex items-center justify-between">
        {/* Left: Community Identity */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <MapPin className="w-5 h-5 text-sun" />
            <div>
              <h1 className="font-display font-semibold text-body text-text">{communityName}</h1>
              <p className="text-caption text-text-muted">{scenarioName || 'No scenario loaded'}</p>
            </div>
          </div>

          {controllerType && (
            <span className="badge badge-sun hidden sm:inline-flex">
              {controllerType.replace('_', ' ')}
            </span>
          )}

          <div className="hidden md:flex items-center gap-1 border-l border-border/30 pl-4 ml-2">
            <Button variant="ghost" size="icon" aria-label="Scenario studio" onClick={onScenarioChange}>
              <GitBranch className="w-4 h-4" />
            </Button>
            <Button variant="ghost" size="icon" aria-label="Run simulation" onClick={onRunSimulation}>
              <Play className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Center: Quick Stats */}
        <div className="hidden xl:flex items-center gap-6">
          {currentRun && (
            <>
              <div className="flex items-center gap-2">
                <Sun className="w-4 h-4 text-sun" />
                <span className="text-body-sm text-text">
                  <span className="font-mono text-data text-sun">
                    {selfConsumptionRate !== undefined ? `${selfConsumptionRate.toFixed(1)}%` : '—'}
                  </span>
                  <span className="text-text-muted"> Self-consumption</span>
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-energy" aria-hidden="true" />
                <span className="text-body-sm text-text">
                  <span className="font-mono text-data text-energy">
                    {currentRun.energy_metrics?.peak_demand_kw ? currentRun.energy_metrics.peak_demand_kw.toFixed(0) : '—'} kW
                  </span>
                  <span className="text-text-muted"> Peak</span>
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Battery className="w-4 h-4 text-battery" aria-hidden="true" />
                <span className="text-body-sm text-text">
                  <span className="font-mono text-data text-battery">
                    {evCompletionRate !== undefined ? `${(evCompletionRate * 100).toFixed(0)}%` : '—'}
                  </span>
                  <span className="text-text-muted"> EV Ready</span>
                </span>
              </div>
            </>
          )}
        </div>

        {/* Right: Controls */}
        <div className="flex items-center gap-2">
          {/* Map Style Selector */}
          <div className="hidden sm:flex items-center gap-2">
            <span className="text-caption text-text-muted">Map:</span>
            <Select
              value={mapStyle}
              onChange={handleMapStyleChange}
              options={[
                { value: 'dark', label: 'Dark' },
                { value: 'light', label: 'Light' },
                { value: 'satellite', label: 'Satellite' },
              ]}
              className="w-auto min-w-[120px]"
            />
          </div>

          {/* Scenario Selector */}
          <div className="hidden lg:flex items-center gap-2">
            <span className="text-caption text-text-muted">Run:</span>
            <Select
              value={currentRun?.run_id || ''}
              onChange={(e) => { void handleRunChange(e.target.value); }}
              options={runs.map(r => ({ value: r.run_id, label: `${r.run_id} (${r.controller_type})` }))}
              className="w-auto min-w-[150px] max-w-[190px]"
              placeholder="Select run..."
            />
          </div>

          {/* Actions */}
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" aria-label="Download report">
              <Download className="w-4 h-4" />
            </Button>
            <Button variant="ghost" size="icon" aria-label="Upload scenario">
              <Upload className="w-4 h-4" />
            </Button>
            <Button variant="ghost" size="icon" aria-label="Settings">
              <Settings className="w-4 h-4" />
            </Button>
            <Button variant="ghost" size="icon" aria-label="Help">
              <Info className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>
    </header>
  );
}