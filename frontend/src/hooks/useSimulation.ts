import { useEffect, useRef, useCallback } from 'react';
import { wsManager } from '../api/client';
import { useSimulationStore } from '../store/simulationStore';
import { useAgentStore } from '../store/agentStore';
import type { TimeStepData, WebSocketMessage } from '../api/types';

export function useSimulationWebSocket(runId: string | null) {
  const setTrajectories = useSimulationStore((state) => state.setTrajectories);
  const setTimePlayer = useSimulationStore((state) => state.setTimePlayer);
  const updateRun = useSimulationStore((state) => state.updateRun);
  const { currentRun } = useSimulationStore();
  const { updateTaskStatus, updateTaskField } = useAgentStore();

  const reconnectTimeoutRef = useRef<number | null>(null);

  const handleMessage = useCallback((message: WebSocketMessage) => {
    switch (message.type) {
      case 'simulation_update':
        // Update trajectories with new timestep
        const payload = message.payload as TimeStepData;
        setTrajectories((prev: TimeStepData[]) => {
          const existing = prev.find((t: TimeStepData) => t.timestep === payload.timestep);
          if (existing) {
            return prev.map((t: TimeStepData) => t.timestep === payload.timestep ? payload : t);
          }
          return [...prev, payload].sort((a: TimeStepData, b: TimeStepData) => a.timestep - b.timestep);
        });
        break;

      case 'simulation_complete':
        if (currentRun) {
          updateRun(currentRun.run_id, {
            status: 'completed',
            end_time: new Date().toISOString(),
            energy_metrics: message.payload.energy_metrics,
            service_metrics: message.payload.service_metrics,
            grid_metrics: message.payload.grid_metrics,
          });
        }
        setTimePlayer({ playing: false });
        break;

      case 'simulation_error':
        if (currentRun) {
          updateRun(currentRun.run_id, { status: 'failed' });
        }
        setTimePlayer({ playing: false });
        break;

      case 'agent_update':
        updateTaskStatus(message.payload.status);
        if (message.payload.plan) updateTaskField('plan', message.payload.plan);
        if (message.payload.code) updateTaskField('code', message.payload.code);
        if (message.payload.execution_log) updateTaskField('execution_log', message.payload.execution_log);
        if (message.payload.verification) updateTaskField('verification', message.payload.verification);
        if (message.payload.repairs) updateTaskField('repairs', message.payload.repairs);
        if (message.payload.report) updateTaskField('report', message.payload.report);
        break;

      case 'agent_complete':
        updateTaskStatus('completed');
        break;
    }
  }, [setTrajectories, setTimePlayer, updateRun, currentRun, updateTaskStatus, updateTaskField]);

  useEffect(() => {
    if (!runId) return;

    const connect = async () => {
      try {
        await wsManager.connect(runId);

        // Subscribe to messages
        const unsubscribers = [
          wsManager.on('simulation_update', (payload) => handleMessage({ type: 'simulation_update', payload })),
          wsManager.on('simulation_complete', (payload) => handleMessage({ type: 'simulation_complete', payload })),
          wsManager.on('simulation_error', (payload) => handleMessage({ type: 'simulation_error', payload })),
          wsManager.on('agent_update', (payload) => handleMessage({ type: 'agent_update', payload })),
          wsManager.on('agent_complete', (payload) => handleMessage({ type: 'agent_complete', payload })),
        ];

        return () => {
          unsubscribers.forEach(unsub => unsub());
        };
      } catch (error) {
        console.error('Failed to connect WebSocket:', error);
      }
    };

    connect();

    return () => {
      wsManager.disconnect();
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [runId, handleMessage]);
}

export function useTimePlayer() {
  const { timePlayer, play, pause, stepForward, stepBackward, setSpeed, reset, setCurrentTimestep } = useSimulationStore();

  const togglePlay = useCallback(() => {
    if (timePlayer.playing) {
      pause();
    } else {
      play();
    }
  }, [timePlayer.playing, play, pause]);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

    switch (e.key) {
      case ' ':
        e.preventDefault();
        togglePlay();
        break;
      case 'ArrowRight':
        e.preventDefault();
        stepForward();
        break;
      case 'ArrowLeft':
        e.preventDefault();
        stepBackward();
        break;
      case 'Home':
        e.preventDefault();
        reset();
        break;
      case 'End':
        e.preventDefault();
        setCurrentTimestep(timePlayer.maxTimestep);
        break;
    }
  }, [togglePlay, stepForward, stepBackward, reset, setCurrentTimestep, timePlayer.maxTimestep]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return {
    ...timePlayer,
    play,
    pause,
    togglePlay,
    stepForward,
    stepBackward,
    setSpeed,
    reset,
    setCurrentTimestep,
  };
}

export function useSimulationPolling(runId: string | null, enabled: boolean = true) {
  useEffect(() => {
    if (!runId || !enabled) return;

    const pollInterval = setInterval(async () => {
      try {
        // In a real implementation, this would fetch from the API
        // For now, we'll rely on WebSocket
      } catch (error) {
        console.error('Polling error:', error);
      }
    }, 5000);

    return () => clearInterval(pollInterval);
  }, [runId, enabled]);
}