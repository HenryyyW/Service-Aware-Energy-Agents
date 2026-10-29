/**
 * Reusable async state components for consistent loading, empty, error, and success states
 * across all views (CommunityCanvas, ScenarioStudio, Report, Comparison, AgentWorkspace)
 */
import { useState, useEffect } from 'react';
import { clsx } from 'clsx';
import { Loader2, AlertCircle, CheckCircle, XCircle, RefreshCw, Search, Plus } from 'lucide-react';
import { Button } from './Button';

export type AsyncStatus = 'idle' | 'loading' | 'success' | 'error' | 'empty';

export interface AsyncStateConfig {
  status: AsyncStatus;
  error?: Error | string;
  retry?: () => void;
  emptyMessage?: string;
  emptyAction?: { label: string; onClick: () => void };
  loadingMessage?: string;
}

/**
 * Skeleton loader for content areas
 */
export function Skeleton({ className = '', rows = 3 }: { className?: string; rows?: number }) {
  return (
    <div className={clsx('space-y-3', className)}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-4 bg-surface/50 rounded animate-pulse" style={{ width: `${70 + Math.random() * 30}%` }} />
      ))}
    </div>
  );
}

/**
 * Skeleton for card grids
 */
export function CardSkeleton({ className = '', count = 4 }: { className?: string; count?: number }) {
  return (
    <div className={clsx('grid gap-4 sm:grid-cols-2 lg:grid-cols-4', className)}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="glass-card p-4 animate-pulse space-y-3">
          <div className="h-5 bg-surface/50 rounded w-3/4" />
          <div className="h-4 bg-surface/50 rounded w-1/2" />
          <div className="h-4 bg-surface/50 rounded w-2/3" />
        </div>
      ))}
    </div>
  );
}

/**
 * Table skeleton
 */
export function TableSkeleton({ className = '', rows = 5, cols = 4 }: { className?: string; rows?: number; cols?: number }) {
  return (
    <div className={clsx('overflow-x-auto', className)}>
      <table className="w-full">
        <thead>
          <tr>
            {Array.from({ length: cols }).map((_, i) => (
              <th key={i} className="text-left p-3 bg-surface/50 animate-pulse">
                <div className="h-4 bg-surface/30 rounded w-3/4" />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, row) => (
            <tr key={row}>
              {Array.from({ length: cols }).map((_, col) => (
                <td key={col} className="p-3 animate-pulse">
                  <div className="h-4 bg-surface/50 rounded w-3/4" />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Empty state component
 */
export function EmptyState({ 
  icon: Icon, 
  title, 
  description, 
  action,
  className = ''
}: { 
  icon: React.ReactNode; 
  title: string; 
  description: string; 
  action?: { label: string; onClick: () => void };
  className?: string;
}) {
  return (
    <div className={clsx('flex flex-col items-center justify-center p-8 text-center text-text-muted', className)}>
      <div className="w-16 h-16 mx-auto mb-4 text-text-muted/30 flex items-center justify-center">
        {Icon}
      </div>
      <h3 className="font-body font-medium text-body text-text mb-2">{title}</h3>
      <p className="text-caption text-text-muted/70 max-w-sm mb-6">{description}</p>
      {action && (
        <Button variant="primary" size="sm" onClick={action.onClick}>
          <Plus className="w-4 h-4 mr-1" />
          {action.label}
        </Button>
      )}
    </div>
  );
}

/**
 * Error state component
 */
export function ErrorState({ 
  error, 
  onRetry,
  className = ''
}: { 
  error: Error | string; 
  onRetry?: () => void;
  className?: string;
}) {
  const message = typeof error === 'string' ? error : error.message;
  
  return (
    <div className={clsx('flex flex-col items-center justify-center p-8 text-center', className)}>
      <AlertCircle className="w-16 h-16 mx-auto mb-4 text-violation" />
      <h3 className="font-body font-medium text-body text-text mb-2">Something went wrong</h3>
      <p className="text-caption text-text-muted/70 max-w-sm mb-6">{message}</p>
      {onRetry && (
        <Button variant="primary" size="sm" onClick={onRetry}>
          <RefreshCw className="w-4 h-4 mr-1" />
          Try Again
        </Button>
      )}
    </div>
  );
}

/**
 * Success state component
 */
export function SuccessState({ 
  title, 
  description,
  onContinue,
  className = ''
}: { 
  title: string; 
  description?: string;
  onContinue?: () => void;
  className?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center">
      <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-energy/10 flex items-center justify-center">
        <CheckCircle className="w-8 h-8 text-energy" />
      </div>
      <h3 className="font-body font-medium text-body text-text mb-2">{title}</h3>
      {description && <p className="text-caption text-text-muted/70 max-w-sm mb-6">{description}</p>}
      {onContinue && (
        <Button variant="primary" size="sm" onClick={onContinue}>
          Continue
        </Button>
      )}
    </div>
  );
}

/**
 * Main async state wrapper component
 */
export function AsyncWrapper({ 
  children, 
  status, 
  error, 
  onRetry,
  emptyConfig,
  loadingMessage = 'Loading...',
  className = ''
}: { 
  children: React.ReactNode;
  status: AsyncStatus;
  error?: Error | string;
  onRetry?: () => void;
  emptyConfig?: { icon: React.ReactNode; title: string; description: string; action?: { label: string; onClick: () => void } };
  loadingMessage?: string;
  className?: string;
}) {
  if (status === 'loading') {
    return (
      <div className={clsx('flex flex-col items-center justify-center p-8', className)}>
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-8 h-8 text-sun animate-spin" />
          <span className="text-caption text-text-muted">{loadingMessage}</span>
        </div>
      </div>
    );
  }

  if (status === 'error') {
    return <ErrorState error={error} onRetry={onRetry} />;
  }

  if (status === 'empty') {
    return emptyConfig ? (
      <EmptyState 
        icon={emptyConfig.icon} 
        title={emptyConfig.title} 
        description={emptyConfig.description}
        action={emptyConfig.action}
      />
    ) : (
      <EmptyState 
        icon={<Search className="w-8 h-8" />}
        title="No data available" 
        description="No items found matching your criteria"
      />
    );
  }

  return <div className={className}>{children}</div>;
}

/**
 * Hook for managing async state
 */
export function useAsyncState<T>() {
  const [status, setStatus] = useState<AsyncStatus>('idle');
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);

  const execute = async (asyncFn: () => Promise<T>) => {
    setStatus('loading');
    setError(null);
    try {
      const result = await asyncFn();
      setData(result);
      setStatus(result === null || (Array.isArray(result) && result.length === 0) ? 'empty' : 'success');
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      setError(error);
      setStatus('error');
      throw error;
    }
  };

  const reset = () => {
    setStatus('idle');
    setData(null);
    setError(null);
  };

  return { status, data, error, execute, reset, setStatus };
}

export function useAsyncArray<T>() {
  const [status, setStatus] = useState<AsyncStatus>('idle');
  const [data, setData] = useState<T[]>([]);
  const [error, setError] = useState<Error | null>(null);

  const execute = async (asyncFn: () => Promise<T[]>) => {
    setStatus('loading');
    setError(null);
    try {
      const result = await asyncFn();
      setData(result);
      setStatus(result.length === 0 ? 'empty' : 'success');
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      setError(error);
      setStatus('error');
      throw error;
    }
  };

  const reset = () => {
    setStatus('idle');
    setData([]);
    setError(null);
  };

  return { status, data, error, execute, reset, setStatus, setData };
}