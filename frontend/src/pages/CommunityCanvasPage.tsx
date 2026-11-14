import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSimulationStore } from '../store/simulationStore';
import { useScenarioStore } from '../store/scenarioStore';
import { useCanvasStore } from '../store/canvasStore';
import { api, wsManager } from '../api/client';
import { CommunityCanvas } from '../components/canvas/CommunityCanvas';
import { ToastProvider } from '@/components/ui/Toast'
import { useToast } from '@/hooks';
import { Plus, RefreshCw } from '../utils/lucide';
import { devError } from '../utils/devLog';

function CommunityCanvasPageContent() {
  const { setRuns, setCurrentRun, setTrajectories, runs } = useSimulationStore();
  const setCurrentScenario = useScenarioStore((s) => s.setCurrentScenario);
  const { fetchNetworkGeometry, fetchAssetMetadata } = useCanvasStore();
  const { addToast } = useToast();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    // Load runs on mount. Canvas is run-sourced: every run renders via its
    // scenario_id configuration (api.getScenario) plus its own trajectories
    // (api.getTrajectories). Falls back to the empty state when there are no
    // runs at all.
    const loadRuns = async () => {
      setLoading(true);
      setError(null);
      try {
        const runsData = await api.getRuns();
        if (!active) return;
        setRuns(runsData);
        if (runsData.length > 0) {
          const run = runsData[0];
          setCurrentRun(run);
          // Scenario config + network geometry + asset metadata for this run,
          // all needed before the canvas can paint buildings.
          try {
            const scenario = await api.getScenario(run.scenario_id);
            if (active) setCurrentScenario(scenario);
          } catch (scenarioError) {
            if (active) {
              setError('Failed to load scenario configuration');
              devError('Failed to load scenario:', scenarioError);
            }
            return;
          }
          void (async () => {
            try {
              await fetchNetworkGeometry(run.scenario_id);
              await fetchAssetMetadata(run.scenario_id);
            } catch (geoError) {
              devError('Failed to load network geometry / asset metadata:', geoError);
            }
          })();
          // Trajectories for this run
          try {
            const trajectories = await api.getTrajectories(run.run_id);
            if (active) setTrajectories(trajectories);
          } catch (trajError) {
            if (active) {
              setError('Failed to load trajectory data');
              devError('Failed to load trajectories:', trajError);
            }
          }
        }
      } catch (error) {
        if (active) {
          setError('Could not connect to the backend API');
          devError('Failed to load runs:', error);
          addToast({
            type: 'error',
            title: 'Failed to load simulations',
            message: 'Could not connect to backend API',
          });
        }
      } finally {
        if (active) setLoading(false);
      }
    };

    loadRuns();

    // Set up WebSocket for real-time updates
    wsManager.on('simulation_update', () => {
      // Handled by useSimulationWebSocket hook
    });

    return () => {
      active = false;
      wsManager.disconnect();
    };
  }, [
    setRuns,
    setCurrentRun,
    setTrajectories,
    setCurrentScenario,
    fetchNetworkGeometry,
    fetchAssetMetadata,
    addToast,
  ]);

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-surface">
        <div className="flex flex-col items-center gap-2">
          <div className="animate-spin w-10 h-10 border-2 border-sun/30 border-t-sun rounded-full" />
          <p className="text-body text-text-muted">Loading simulation runs…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex flex-col items-center justify-center bg-surface text-center px-6">
        <p className="text-body text-text">{error}</p>
        <button
          type="button"
          className="btn btn-primary mt-3"
          onClick={() => { setLoading(true); setError(null); }}
          aria-label="Retry loading simulations"
        >
          <RefreshCw className="w-4 h-4 mr-2" /> Retry
        </button>
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center bg-surface text-center px-6">
        <p className="text-body text-text-muted">No community data</p>
        <p className="text-caption text-text-muted">
          No simulation runs found. Create a scenario to view its run on the canvas.
        </p>
        <button
          type="button"
          className="btn btn-primary mt-3"
          onClick={() => navigate('/scenarios/generate')}
          aria-label="Create scenario"
        >
          <Plus className="w-4 h-4 mr-2" /> Create scenario
        </button>
      </div>
    );
  }

  return <CommunityCanvas />;
}

export function CommunityCanvasPage() {
  return (
    <ToastProvider>
      <CommunityCanvasPageContent />
    </ToastProvider>
  );
}
