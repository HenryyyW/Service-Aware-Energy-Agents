import { useScenarioStore } from '../store/scenarioStore';
import { useNavigate } from 'react-router-dom';
import { useSimulationStore } from '../store/simulationStore';
import { api } from '../api/client';
import { ScenarioEditor } from '../components/scenario/ScenarioEditor';
import { ParameterControls } from '../components/scenario/ParameterControls';
import { ScenarioComparison } from '../components/scenario/ScenarioComparison';
import { ToastProvider, useToast } from '../components/ui/Toast';
import { Tabs, TabList, Tab, TabPanel } from '../components/ui/Tabs';

function materializeScenario(source: any, editor: any, scenarioId: string) {
  const buildingCount = Math.max(1, Math.min(source.buildings.length, Math.trunc(editor.community?.buildings || source.buildings.length)));
  const buildings = source.buildings.slice(0, buildingCount).map((building: any) => structuredClone(building));
  const pvCount = Math.round(buildingCount * (editor.assets?.pv?.penetration ?? 0));
  const batteryCapacity = Math.max(0, editor.assets?.batteries?.community_capacity_kwh ?? 0);
  const batteryPower = Math.max(0, editor.assets?.batteries?.max_power_kw ?? 0);
  const sourceBatteryCapacity = buildings.reduce((sum: number, building: any) => sum + (building.battery?.capacity_kwh || 0), 0);
  const sourceBatteryPower = buildings.reduce((sum: number, building: any) => sum + (building.battery?.power_kw || 0), 0);
  const evTemplate = buildings.flatMap((building: any) => building.evs || [])[0];
  const evCount = Math.max(0, Math.min(500, Math.trunc(editor.assets?.evs?.number ?? 0)));
  const requestedEvPower = Math.max(...(editor.assets?.evs?.charging_power_kw || [11]));
  const flexibleBuildingCount = Math.round(buildingCount * (editor.assets?.flexible_loads?.share ?? 0));

  buildings.forEach((building: any, index: number) => {
    if (index >= pvCount) {
      building.pv = null;
    }
    if (batteryCapacity === 0 || batteryPower === 0) {
      building.battery = null;
    } else if (building.battery) {
      building.battery.capacity_kwh *= batteryCapacity / (sourceBatteryCapacity || batteryCapacity);
      building.battery.power_kw *= batteryPower / (sourceBatteryPower || batteryPower);
    }
    building.evs = [];
    if (index < flexibleBuildingCount && !building.flexible_loads?.length) {
      const flexibleTemplate = source.buildings.flatMap((item: any) => item.flexible_loads || [])[0];
      building.flexible_loads = flexibleTemplate ? [structuredClone(flexibleTemplate)] : [];
    } else if (index >= flexibleBuildingCount) {
      building.flexible_loads = [];
    }
  });

  if (evTemplate && buildings.length) {
    for (let index = 0; index < evCount; index += 1) {
      const ev = structuredClone(evTemplate);
      ev.target_soc = editor.assets.evs.departure_soc_requirement;
      ev.max_charge_kw = requestedEvPower;
      buildings[index % buildings.length].evs.push(ev);
    }
  }

  const durationDays = editor.community?.simulation_period === '1_day' ? 1 : 7;
  const start = new Date(`${buildings[0].simulation_start}T00:00:00`);
  const end = new Date(start);
  end.setDate(end.getDate() + durationDays);
  const isoDate = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  buildings.forEach((building: any) => {
    building.simulation_start = isoDate(start);
    building.simulation_end = isoDate(end);
  });

  return {
    ...source,
    scenario_id: scenarioId,
    name: editor.community?.name || source.name,
    buildings,
    community_import_limit_kw: editor.grid?.import_limit_kw ?? source.community_import_limit_kw,
    community_export_limit_kw: editor.grid?.export_limit_kw ?? source.community_export_limit_kw,
    random_seed: editor.random_seed ?? source.random_seed,
    timestep_minutes: source.timestep_minutes,
    pandapower: source.pandapower ? {
      ...source.pandapower,
      voltage_limits: {
        min: editor.grid?.voltage_limits_pu?.[0] ?? source.pandapower.voltage_limits.min,
        max: editor.grid?.voltage_limits_pu?.[1] ?? source.pandapower.voltage_limits.max,
      },
    } : source.pandapower,
  };
}

function ScenarioStudioPageContent() {
  const { scenarios } = useScenarioStore();
  const { addToast } = useToast();
  const navigate = useNavigate();
  const { addRun, setCurrentRun, setTrajectories, updateRun } = useSimulationStore();

  const persistEditorScenario = async (scenario: any, scenarioId: string) => {
    const source = await api.getScenario(scenario.scenario_id || 'scenario_a');
    const effectiveScenario = materializeScenario(source, scenario, scenarioId);
    return api.createScenario(effectiveScenario);
  };

  const handleSaveScenario = async (scenario: any) => {
    try {
      const scenarioId = `studio_${Date.now()}`;
      await persistEditorScenario(scenario, scenarioId);
      addToast({ type: 'success', title: 'Scenario saved', message: scenarioId });
    } catch (error) {
      console.error('Failed to save scenario:', error);
      addToast({ type: 'error', title: 'Failed to save scenario' });
    }
  };

  const handleRunSimulation = async (scenario: any) => {
    try {
      addToast({ type: 'info', title: 'Starting simulation...', duration: 3000 });
      const scenarioId = `studio_${Date.now()}`;
      const effectiveScenario = await persistEditorScenario(scenario, scenarioId);
      const controllerType = scenario.control?.strategy || 'rule_based';
      // Calculate maxSteps based on actual timestep_minutes
      const timestepMinutes = scenario.timestep_minutes || effectiveScenario.timestep_minutes || 60;
      const durationDays = scenario.community?.simulation_period === '1_day' ? 1 : 7;
      const maxSteps = Math.floor((durationDays * 24 * 60) / timestepMinutes);
      const run = await api.runSimulation(scenarioId, controllerType, {
        random_seed: effectiveScenario.random_seed,
        max_steps: maxSteps,
      });
      addRun(run);
      setCurrentRun(run);
      addToast({
        type: 'success',
        title: 'Simulation queued',
        message: `Run ${run.run_id}. Timestep: ${timestepMinutes} min, ${maxSteps} steps.`,
      });
      navigate('/');

      void (async () => {
        try {
          let current = run;
          for (let attempt = 0; attempt < 1800 && ['pending', 'running'].includes(current.status); attempt += 1) {
            await new Promise((resolve) => window.setTimeout(resolve, 2000));
            current = await api.getRun(run.run_id);
            updateRun(run.run_id, current);
          }
          if (current.status === 'completed') {
            const trajectories = await api.getTrajectories(run.run_id);
            setCurrentRun(current);
            setTrajectories(trajectories);
          }
        } catch (pollError) {
          console.error('Failed to refresh simulation run:', pollError);
        }
      })();
    } catch (error) {
      console.error('Failed to run simulation:', error);
      addToast({ type: 'error', title: 'Failed to start simulation', duration: 5000 });
    }
  };

  const handleQuickRun = () => {
    const { currentScenario } = useScenarioStore.getState();
    if (currentScenario) {
      handleRunSimulation(currentScenario);
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-border/30 bg-surface/50">
        <div className="flex items-center justify-between mb-4">
          <h1 className="font-display font-semibold text-heading-1 text-text">Scenario Studio</h1>
          <div className="flex items-center gap-2">
            {scenarios.length > 0 && (
              <span className="badge badge-sun">{scenarios.length} saved</span>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="editor">
        <TabList>
          <Tab value="editor">Scenario Editor</Tab>
          <Tab value="parameters">Quick Parameters</Tab>
          <Tab value="comparison">Comparison</Tab>
        </TabList>

        <TabPanel value="editor">
          <div className="p-4 h-[calc(100%-60px)] overflow-auto">
            <ScenarioEditor
              onSave={handleSaveScenario}
              onRun={handleRunSimulation}
            />
          </div>
        </TabPanel>

        <TabPanel value="parameters">
          <div className="p-4 h-[calc(100%-60px)] overflow-auto">
            <ParameterControls onRun={handleQuickRun} />
          </div>
        </TabPanel>

        <TabPanel value="comparison">
          <div className="p-4 h-[calc(100%-60px)] overflow-auto">
            <ScenarioComparison />
          </div>
        </TabPanel>
      </Tabs>
    </div>
  );
}

export function ScenarioStudioPage() {
  return (
    <ToastProvider>
      <ScenarioStudioPageContent />
    </ToastProvider>
  );
}