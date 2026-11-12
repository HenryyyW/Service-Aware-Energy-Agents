import { useEffect, useState } from 'react';
import { useSimulationStore } from '../store/simulationStore';
import { api, wsManager } from '../api/client';
import { CommunityCanvas } from '../components/canvas/CommunityCanvas';
import { ToastProvider } from '@/components/ui/Toast'
import { useToast } from '@/hooks';
import { RefreshCw } from '../utils/lucide';
import { devError } from '../utils/devLog';

function CommunityCanvasPageContent() {
  const { setRuns, setCurrentRun, setTrajectories } = useSimulationStore();
  const { addToast } = useToast();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    // Load runs on mount
    const loadRuns = async () => {
      setLoading(true);
      setError(null);
      try {
        const runsData = await api.getRuns();
        if (!active) return;
        setRuns(runsData);
        if (runsData.length > 0) {
          setCurrentRun(runsData[0]);
          // Load trajectories for the first run
          try {
            const trajectories = await api.getTrajectories(runsData[0].run_id);
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
  }, [setRuns, setCurrentRun, setTrajectories, addToast]);

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

  return (
    <CommunityCanvas />
  );
}

export function CommunityCanvasPage() {
  return (
    <ToastProvider>
      <CommunityCanvasPageContent />
    </ToastProvider>
  );
}