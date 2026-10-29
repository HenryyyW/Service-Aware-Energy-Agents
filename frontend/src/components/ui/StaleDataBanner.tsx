import { useEffect, useState } from 'react';
import { clsx } from 'clsx';
import { WifiOff, RotateCcw, X } from 'lucide-react';
import { useWebSocketConnection } from '../../hooks/useWebSocket';
import { Button } from './Button';

/**
 * Stale data banner component that shows when WebSocket data is stale or reconnecting
 */
export function StaleDataBanner({ 
  className = '',
  onDismiss,
}: { 
  className?: string;
  onDismiss?: () => void;
}) {
  const connectionState = useWebSocketConnection();
  const [dismissed, setDismissed] = useState(false);
  const [showDetails, setShowDetails] = useState(false);

  // Auto-hide when connection is healthy
  useEffect(() => {
    if (!connectionState.stale && !connectionState.isReconnecting) {
      setDismissed(false);
    }
  }, [connectionState.stale, connectionState.isReconnecting]);

  if (dismissed) return null;
  
  const isStale = connectionState.stale;
  const isReconnecting = connectionState.isReconnecting;
  
  if (!isStale && !isReconnecting) return null;

  const handleDismiss = () => {
    setDismissed(true);
    onDismiss?.();
  };

  const handleReconnect = () => {
    // Trigger a reconnect attempt
    window.location.reload(); // Simple approach - full reload to reset WS
  };

  return (
    <div 
      className={clsx(
        'fixed top-0 left-0 right-0 z-50 px-4 py-2 animate-slide-down',
        isStale ? 'bg-warning/10 border-b border-warning/30' : 'bg-info/10 border-b border-info/30',
        className
      )}
      role="alert"
      aria-live="polite"
    >
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          {connectionState.isReconnecting ? (
            <>
              <div className="w-5 h-5 border-2 border-info border-t-transparent rounded-full animate-spin" />
              <span className="font-body text-body-sm text-text">
                Reconnecting... (attempt {connectionState.reconnectAttempts}/{5})
              </span>
            </>
          ) : (
            <>
              <span className="w-5 h-5 flex items-center justify-center">
                <WifiOff className="w-5 h-5 text-warning" />
              </span>
              <span className="font-body text-body-sm text-text">
                Live data stale — last update {connectionState.lastMessageTime 
                  ? `${Math.round((Date.now() - connectionState.lastMessageTime) / 1000)}s ago` 
                  : 'unknown'}
              </span>
            </>
          )}
        </div>
        
        <div className="flex items-center gap-2 flex-shrink-0">
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={handleReconnect}
            className="flex items-center gap-1"
          >
            <RotateCcw className="w-4 h-4" />
            Reconnect
          </Button>
          
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={handleDismiss}
            aria-label="Dismiss"
          >
            <X className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {showDetails && (
        <div className="max-w-7xl mx-auto px-4 pb-2 text-caption text-text-muted/70 border-t border-white/10">
          <details className="flex items-center gap-2">
            <summary className="cursor-pointer flex items-center gap-1">
              <RotateCcw className="w-3 h-3" />
              Connection Details
            </summary>
            <div className="ml-4 space-y-1 font-mono text-xs">
              <div>Connected: {connectionState.isConnected ? 'Yes' : 'No'}</div>
              <div>Reconnecting: {connectionState.isReconnecting ? 'Yes' : 'No'}</div>
              <div>Reconnect Attempts: {connectionState.reconnectAttempts}</div>
              <div>Last Message: {connectionState.lastMessageTime 
                ? new Date(connectionState.lastMessageTime).toLocaleTimeString() 
                : 'Never'}</div>
              <div>Stale Threshold: 5s</div>
            </div>
          </details>
        </div>
      )}
    </div>
  );
}

/**
 * Hook to access WebSocket connection state
 */
export function useWebSocketConnection() {
  // This would be implemented to connect to the wsManager
  // For now, return a mock state
  const [state, setState] = useState({
    isConnected: false,
    isReconnecting: false,
    lastMessageTime: null,
    stale: false,
    reconnectAttempts: 0,
  });

  // In a real implementation, this would subscribe to wsManager.onConnectionStateChange
  useEffect(() => {
    // Subscribe to wsManager connection state changes
    // const unsubscribe = wsManager.onConnectionStateChange(setState);
    // return unsubscribe;
  }, []);

  return state;
}

/**
 * Component that shows stale data indicator inline (for use in panels/cards)
 */
export function InlineStaleIndicator({ 
  lastUpdate, 
  threshold = 5000,
  className = ''
}: { 
  lastUpdate: number | null;
  threshold?: number;
  className?: string;
}) {
  const isStale = lastUpdate && (Date.now() - lastUpdate) > threshold;
  
  if (!isStale) return null;

  const secondsAgo = Math.round((Date.now() - (lastUpdate || 0)) / 1000);
  
  return (
    <span className={clsx('inline-flex items-center gap-1 text-caption text-warning/80', className)}>
      <span className="w-2 h-2 rounded-full bg-warning animate-pulse" />
      <span>Stale ({secondsAgo}s ago)</span>
    </span>
  );
}

/**
 * Connection status indicator for headers/toolbars
 */
export function ConnectionStatusIndicator({ className = '' }: { className?: string }) {
  const connectionState = useWebSocketConnection();

  if (connectionState.isReconnecting) {
    return (
      <span className={clsx('inline-flex items-center gap-1.5 text-caption text-info', className)}>
        <span className="w-3 h-3 border-2 border-info border-t-transparent rounded-full animate-spin" />
        <span>Reconnecting...</span>
      </span>
    );
  }

  if (!connectionState.isConnected) {
    return (
      <span className={clsx('inline-flex items-center gap-1.5 text-caption text-violation', className)}>
        <span className="w-2 h-2 rounded-full bg-violation" />
        <span>Disconnected</span>
      </span>
    );
  }

  if (connectionState.stale) {
    return (
      <span className={clsx('inline-flex items-center gap-1.5 text-caption text-warning', className)}>
        <span className="w-2 h-2 rounded-full bg-warning animate-pulse" />
        <span>Stale</span>
      </span>
    );
  }

  return (
    <span className={clsx('inline-flex items-center gap-1.5 text-caption text-energy', className)}>
      <span className="w-2 h-2 rounded-full bg-energy animate-pulse" />
      <span>Live</span>
    </span>
  );
}