import { useState } from 'react';

export type AsyncStatus = 'idle' | 'loading' | 'success' | 'error' | 'empty';

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