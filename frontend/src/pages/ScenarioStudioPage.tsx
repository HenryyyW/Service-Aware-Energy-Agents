import { useScenarioStore } from '../store/scenarioStore';
import { api } from '../api/client';
import { ScenarioEditor } from '../components/scenario/ScenarioEditor';
import { ParameterControls } from '../components/scenario/ParameterControls';
import { ScenarioComparison } from '../components/scenario/ScenarioComparison';
import { ToastProvider, useToast } from '../components/ui/Toast';
import { Tabs, TabList, Tab, TabPanel } from '../components/ui/Tabs';

function ScenarioStudioPageContent() {
  const { scenarios } = useScenarioStore();
  const { addToast } = useToast();

  const handleRunSimulation = async (scenario: any) => {
    try {
      addToast({ type: 'info', title: 'Starting simulation...', duration: 3000 });
      const run = await api.runSimulation(scenario.community.name, 'agent_policy');
      addToast({ type: 'success', title: 'Simulation started', message: `Run ID: ${run.run_id}` });
      // Would connect to WebSocket for real-time updates
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
              onSave={(scenario) => console.log('Saved:', scenario)}
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