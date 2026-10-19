import { useEffect } from 'react';
import { useSimulationStore } from '../store/simulationStore';
import { api, wsManager } from '../api/client';
import { CommunityCanvas } from '../components/canvas/CommunityCanvas';
import { ToastProvider, useToast } from '../components/ui/Toast';

function CommunityCanvasPageContent() {
  const { setRuns, setCurrentRun, setTrajectories } = useSimulationStore();
  const { addToast } = useToast();

  useEffect(() => {
    // Load runs on mount
    const loadRuns = async () => {
      try {
        const runsData = await api.getRuns();
        setRuns(runsData);
        if (runsData.length > 0) {
          setCurrentRun(runsData[0]);
          // Load trajectories for the first run
          const trajectories = await api.getTrajectories(runsData[0].run_id);
          setTrajectories(trajectories);
        }
      } catch (error) {
        console.error('Failed to load runs:', error);
        addToast({
          type: 'error',
          title: 'Failed to load simulations',
          message: 'Could not connect to backend API',
        });
      }
    };

    loadRuns();

    // Set up WebSocket for real-time updates
    wsManager.on('simulation_update', () => {
      // Handled by useSimulationWebSocket hook
    });

    return () => {
      wsManager.disconnect();
    };
  }, [setRuns, setCurrentRun, setTrajectories, addToast]);

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