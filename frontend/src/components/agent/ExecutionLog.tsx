import { clsx } from 'clsx';
import { Terminal, AlertCircle, ChevronDown, Download, Trash2 } from 'lucide-react';
import { Button } from '../ui/Button';
import { Select } from '../ui/Input';
import { useState, useEffect, useRef } from 'react';
import { useAgentStore } from '../../store/agentStore';

interface ExecutionLogProps {
  logs?: string[];
  autoScroll?: boolean;
}

export function ExecutionLog({ logs, autoScroll = true }: ExecutionLogProps) {
  const { currentTask } = useAgentStore();
  const taskLogs = logs || currentTask?.execution_log || [];
  const [filter, setFilter] = useState<'all' | 'stdout' | 'stderr' | 'error'>('all');
  const logContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [taskLogs, autoScroll]);

  const filteredLogs = taskLogs.filter(log => {
    if (filter === 'all') return true;
    if (filter === 'error') return log.includes('ERROR') || log.includes('Error') || log.includes('Traceback');
    if (filter === 'stdout') return log.startsWith('>') || log.startsWith('STDOUT:');
    if (filter === 'stderr') return log.startsWith('STDERR:');
    return true;
  });

  if (taskLogs.length === 0) {
    return (
      <div className="glass-card p-8 text-center text-text-muted">
        <Terminal className="w-16 h-16 mx-auto mb-4 text-text-muted/30" />
        <p className="text-body">No execution logs yet</p>
        <p className="text-caption mt-2">Logs will appear when the executor runs the simulation</p>
      </div>
    );
  }

  return (
    <div className="glass-card flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-border/30">
        <div className="flex items-center gap-2">
          <Terminal className="w-5 h-5 text-energy" />
          <span className="font-body font-medium text-body-sm text-text">Execution Log</span>
          <span className="text-caption text-text-muted">{taskLogs.length} entries</span>
        </div>
        <div className="flex items-center gap-2">
          <Select
            value={filter}
            onChange={(e) => setFilter(e.target.value as any)}
            options={[
              { value: 'all', label: 'All' },
              { value: 'stdout', label: 'Stdout' },
              { value: 'stderr', label: 'Stderr' },
              { value: 'error', label: 'Errors' },
            ]}
            className="w-auto min-w-[100px]"
          />
          <Button variant="ghost" size="icon" aria-label="Download logs">
            <Download className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="icon" aria-label="Clear logs">
            <Trash2 className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Log Content */}
      <div
        ref={logContainerRef}
        className="flex-1 overflow-auto p-3 font-mono text-body-sm leading-relaxed bg-space"
      >
        {filteredLogs.map((log, index) => (
          <div
            key={index}
            className={clsx(
              'py-0.5 px-2 border-l-2 transition-colors',
              log.includes('ERROR') || log.includes('Error') || log.includes('Traceback')
                ? 'border-violation bg-violation/5'
                : log.startsWith('>') || log.startsWith('STDOUT:')
                ? 'border-energy bg-energy/5'
                : log.startsWith('STDERR:')
                ? 'border-violation bg-violation/5'
                : 'border-text-muted/30'
            )}
          >
            <span className="text-text-muted mr-2">[{index}]</span>
            <span className={clsx(
              log.includes('ERROR') || log.includes('Error') || log.includes('Traceback') ? 'text-violation' :
              log.startsWith('>') || log.startsWith('STDOUT:') ? 'text-energy' :
              log.startsWith('STDERR:') ? 'text-violation' :
              'text-text'
            )}>
              {escapeHtml(log)}
            </span>
          </div>
        ))}
      </div>

      {/* Status Bar */}
      <div className="flex items-center justify-between px-3 py-2 border-t border-border/30 bg-surface/50">
        <div className="flex items-center gap-4 text-caption text-text-muted">
          <span>{filteredLogs.length} / {taskLogs.length} lines</span>
          {taskLogs.some(l => l.includes('ERROR') || l.includes('Error')) && (
            <span className="flex items-center gap-1 text-violation">
              <AlertCircle className="w-3 h-3" />
              Errors detected
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" aria-label="Toggle auto-scroll">
            <ChevronDown className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&')
    .replace(/</g, '<')
    .replace(/>/g, '>')
    .replace(/"/g, '"')
    .replace(/'/g, '&#039;');
}