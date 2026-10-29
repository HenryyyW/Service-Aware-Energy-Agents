import { useEffect, useState, useCallback } from 'react';
import { wsManager, type WebSocketConnectionState } from '../api/client';

/**
 * Hook to access WebSocket connection state from wsManager
 */
export function useWebSocketConnection(): WebSocketConnectionState {
  const [state, setState] = useState<WebSocketConnectionState>({
    isConnected: false,
    isReconnecting: false,
    lastMessageTime: null,
    stale: false,
    reconnectAttempts: 0,
  });

  useEffect(() => {
    const unsubscribe = wsManager.onConnectionStateChange(setState);
    // Immediately set current state
    setState(wsManager.getConnectionState());
    return unsubscribe;
  }, []);

  return state;
}

/**
 * Hook to connect to a specific simulation WebSocket
 */
export function useSimulationWebSocket(runId: string | null) {
  const [status, setStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');
  const [error, setError] = useState<Error | null>(null);

  const connect = useCallback(async () => {
    if (!runId) return;
    setStatus('connecting');
    setError(null);
    try {
      await wsManager.connect(runId);
      setStatus('connected');
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      setStatus('error');
    }
  }, [runId]);

  const disconnect = useCallback(() => {
    wsManager.disconnect();
    setStatus('disconnected');
  }, []);

  useEffect(() => {
    if (runId) {
      connect();
    } else {
      disconnect();
    }
    return () => disconnect();
  }, [runId, connect, disconnect]);

  return { status, error, connect, disconnect };
}

/**
 * Hook for simulation updates via WebSocket
 */
export function useSimulationUpdates(runId: string | null) {
  const [lastUpdate, setLastUpdate] = useState<{ timestep: number; data: any } | null>(null);

  useEffect(() => {
    if (!runId) return;

    const unsubscribeUpdate = wsManager.on('simulation_update', (payload) => {
      setLastUpdate({ timestep: payload.timestep, data: payload });
    });

    const unsubscribeComplete = wsManager.on('simulation_complete', (payload) => {
      setLastUpdate({ timestep: payload.timestep, data: payload });
    });

    const unsubscribeError = wsManager.on('simulation_error', (payload) => {
      console.error('Simulation error:', payload);
    });

    return () => {
      unsubscribeUpdate();
      unsubscribeComplete();
      unsubscribeError();
    };
  }, [runId]);

  return lastUpdate;
}

/**
 * Hook for agent updates via WebSocket
 */
export function useAgentUpdates() {
  const [lastUpdate, setLastUpdate] = useState<any>(null);

  useEffect(() => {
    const unsubscribe = wsManager.on('agent_update', (payload) => {
      setLastUpdate(payload);
    });

    return () => unsubscribe();
  }, []);

  return lastUpdate;
}