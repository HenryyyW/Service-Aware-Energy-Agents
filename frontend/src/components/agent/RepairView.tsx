import { useState } from 'react';
import { clsx } from 'clsx';
import { Wrench, FileCode, ChevronDown, ChevronRight, CheckCircle, Copy, Download, Play } from 'lucide-react';
import { Button } from '../ui/Button';
import { useAgentStore } from '../../store/agentStore';
import type { RepairPatch } from '../../api/types';

interface RepairViewProps {
  repairs?: RepairPatch[];
}

export function RepairView({ repairs }: RepairViewProps) {
  const { currentTask } = useAgentStore();
  const taskRepairs = repairs || currentTask?.repairs || [];
  const [expandedPatches, setExpandedPatches] = useState<Set<number>>(new Set());

  const togglePatch = (index: number) => {
    setExpandedPatches(prev => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  if (taskRepairs.length === 0) {
    return (
      <div className="glass-card p-8 text-center text-text-muted">
        <Wrench className="w-16 h-16 mx-auto mb-4 text-text-muted/30" />
        <p className="text-body">No repairs needed</p>
        <p className="text-caption mt-2">The repairer will propose patches if verification fails</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="glass-card p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Wrench className="w-6 h-6 text-sun" />
            <div>
              <h3 className="font-display font-semibold text-body text-text">Repair Patches</h3>
              <p className="text-caption text-text-muted">{taskRepairs.length} patch{taskRepairs.length !== 1 ? 'es' : ''} proposed</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="primary" size="sm">
              <Play className="w-4 h-4 mr-1" />
              Apply All
            </Button>
            <Button variant="ghost" size="icon" aria-label="Download all patches">
              <Download className="w-4 h-4" />
            </Button>
          </div>
        </div>

        <div className="grid gap-2 sm:grid-cols-3">
          <div className="text-center p-3 bg-surface/50 rounded-lg">
            <p className="font-mono text-data text-2xl text-sun">{taskRepairs.length}</p>
            <p className="text-caption text-text-muted">Total Patches</p>
          </div>
          <div className="text-center p-3 bg-surface/50 rounded-lg">
            <p className="font-mono text-data text-2xl text-energy">
              {taskRepairs.filter(r => r.description.includes('fix') || r.description.includes('Fix')).length}
            </p>
            <p className="text-caption text-text-muted">Fixes</p>
          </div>
          <div className="text-center p-3 bg-surface/50 rounded-lg">
            <p className="font-mono text-data text-2xl text-battery">
              {taskRepairs.filter(r => r.description.includes('config') || r.description.includes('Config')).length}
            </p>
            <p className="text-caption text-text-muted">Config Changes</p>
          </div>
        </div>
      </div>

      {/* Patch List */}
      <div className="space-y-3">
        {taskRepairs.map((patch, index) => (
          <div key={index} className="glass-card overflow-hidden">
            <button
              onClick={() => togglePatch(index)}
              className="w-full p-4 flex items-center justify-between hover:bg-white/5 transition-colors"
              aria-expanded={expandedPatches.has(index)}
            >
              <div className="flex items-center gap-3">
                <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-sun/10 flex items-center justify-center">
                  <FileCode className="w-5 h-5 text-sun" />
                </div>
                <div>
                  <p className="font-body font-medium text-body text-text">{patch.file}</p>
                  <p className="text-caption text-text-muted">{patch.description}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={clsx(
                  'badge px-2 py-1 text-caption',
                  patch.description.toLowerCase().includes('fix') ? 'badge-energy' : 'badge-sun'
                )}>
                  {patch.description.toLowerCase().includes('fix') ? 'FIX' : 'PATCH'}
                </span>
                {expandedPatches.has(index) ? (
                  <ChevronDown className="w-5 h-5 text-text-muted" />
                ) : (
                  <ChevronRight className="w-5 h-5 text-text-muted" />
                )}
              </div>
            </button>

            {expandedPatches.has(index) && (
              <div className="border-t border-border/30 p-4 bg-surface/30 animate-slide-down">
                <div className="flex items-center justify-between mb-3">
                  <span className="font-body font-medium text-body-sm text-text">Diff</span>
                  <div className="flex items-center gap-1">
                    <Button variant="ghost" size="icon" onClick={() => navigator.clipboard.writeText(patch.diff)} aria-label="Copy diff">
                      <Copy className="w-4 h-4" />
                    </Button>
                    <Button variant="ghost" size="icon" aria-label="Download patch">
                      <Download className="w-4 h-4" />
                    </Button>
                    <Button variant="primary" size="sm">
                      <CheckCircle className="w-4 h-4 mr-1" />
                      Apply
                    </Button>
                  </div>
                </div>
                <div className="font-mono text-body-sm text-text bg-space rounded-lg p-3 overflow-x-auto max-h-64 overflow-y-auto">
                  <pre>{patch.diff}</pre>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}