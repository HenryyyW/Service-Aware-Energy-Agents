import { useEffect, useRef, useState, useCallback } from 'react';
import { useSimulationStore } from '../../store/simulationStore';
import { clsx } from 'clsx';
import {
  AlertTriangle as AlertTriangleIcon,
  DollarSign,
  Zap,
  Sun,
  ChevronDown,
  TrendingUp,
  TrendingDown,
  Clock,
  Zap as ZapIcon,
  Battery,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '../ui/Button';

interface DispatchEntry {
  timestep: number;
  timestamp: string;
  assetId: string;
  actionType: string;
  valueKw: number;
  requestedKw?: number;
  limitedKw?: number;
  reason?: string;
  gridChange?: string;
  verification?: string;
}

interface WorkspaceTimelineProps {
  featureFlags?: {
    timelineRich: boolean;
  };
}

const ACTION_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  battery_charge: Battery,
  battery_discharge: ZapIcon,
  ev_charge: ZapIcon,
  flexible_load: Sun,
};

const ACTION_LABELS: Record<string, string> = {
  battery_charge: 'Battery Charge',
  battery_discharge: 'Battery Discharge',
  ev_charge: 'EV Charge',
  flexible_load: 'Flexible Load',
};

function groupDispatchesByTimestep(dispatches: DispatchEntry[]) {
  const groups = new Map<number, DispatchEntry[]>();
  for (const d of dispatches) {
    const arr = groups.get(d.timestep) || [];
    arr.push(d);
    groups.set(d.timestep, arr);
  }
  return Array.from(groups.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([timestep, entries]) => ({ timestep, entries }));
}

function extractDispatchesFromStepData(stepData: any): DispatchEntry[] {
  if (!stepData?.applied_actions) return [];
  
  const entries: DispatchEntry[] = stepData.applied_actions.map((action: any) => ({
    timestep: stepData.timestep,
    timestamp: stepData.timestamp,
    assetId: action.asset_id,
    actionType: action.action_type,
    valueKw: action.value_kw,
    requestedKw: action.requested_kw,
    limitedKw: action.limited_kw,
    reason: undefined,
    gridChange: undefined,
    verification: undefined,
  }));
  
  return entries;
}

export function WorkspaceTimeline({ featureFlags = { timelineRich: false } }: WorkspaceTimelineProps) {
  const { t } = useTranslation('workspace');
  const { trajectories } = useSimulationStore();
  const [dispatches, setDispatches] = useState<DispatchEntry[]>([]);
  const [selectedTimestep, setSelectedTimestep] = useState<number | null>(null);
  const [expandedTimesteps, setExpandedTimesteps] = useState<Set<number>>(new Set());
  const [batchedDispatches, setBatchedDispatches] = useState<DispatchEntry[]>([]);
  const batchRef = useRef<DispatchEntry[]>([]);
  const batchTimeoutRef = useRef<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Extract dispatches from trajectories
  useEffect(() => {
    if (!trajectories) {
      setDispatches([]);
      return;
    }
    
    const allDispatches: DispatchEntry[] = [];
    for (const stepData of trajectories) {
      allDispatches.push(...extractDispatchesFromStepData(stepData));
    }
    setDispatches(allDispatches);
  }, [trajectories]);

  // 250ms WS batching for incoming dispatch events
  useEffect(() => {
    if (batchTimeoutRef.current) {
      clearTimeout(batchTimeoutRef.current);
    }
    
    batchTimeoutRef.current = window.setTimeout(() => {
      if (batchRef.current.length > 0) {
        setBatchedDispatches(prev => [...prev, ...batchRef.current]);
        batchRef.current = [];
      }
    }, 250);
    
    return () => {
      if (batchTimeoutRef.current) {
        clearTimeout(batchTimeoutRef.current);
      }
    };
  }, []);

  // Keyboard navigation (j/k for timestep navigation)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!containerRef.current?.contains(document.activeElement)) return;
      
      if (e.key === 'j' || e.key === 'ArrowDown') {
        e.preventDefault();
        navigateTimestep(1);
      } else if (e.key === 'k' || e.key === 'ArrowUp') {
        e.preventDefault();
        navigateTimestep(-1);
      } else if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        toggleExpandSelected();
      }
    };
    
    containerRef.current?.addEventListener('keydown', handleKeyDown);
    return () => containerRef.current?.removeEventListener('keydown', handleKeyDown);
  }, []);

  const navigateTimestep = useCallback((direction: number) => {
    if (!trajectories || trajectories.length === 0) return;
    
    const timesteps = Array.from(new Set(dispatches.map(d => d.timestep))).sort((a, b) => a - b);
    if (timesteps.length === 0) return;
    
    const currentIdx = selectedTimestep !== null 
      ? timesteps.indexOf(selectedTimestep) 
      : direction > 0 ? -1 : timesteps.length;
    
    const nextIdx = Math.max(0, Math.min(timesteps.length - 1, currentIdx + direction));
    setSelectedTimestep(timesteps[nextIdx]);
  }, [dispatches, selectedTimestep]);

  const toggleExpandSelected = useCallback(() => {
    if (selectedTimestep !== null) {
      setExpandedTimesteps(current => {
        const next = new Set(current);
        if (next.has(selectedTimestep!)) next.delete(selectedTimestep!);
        else next.add(selectedTimestep!);
        return next;
      });
    }
  }, [selectedTimestep]);

  const groupedDispatches = groupDispatchesByTimestep(dispatches);
  const availableTimesteps = Array.from(new Set(dispatches.map(d => d.timestep))).sort((a, b) => a - b);

  return (
    <div ref={containerRef} className="flex-1 flex flex-col overflow-hidden" tabIndex={0}>
      {/* KPI Header Tiles */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 p-4 border-b border-border/30 bg-surface/30">
        <KpiTile
          icon={AlertTriangleIcon}
          label={t('kpi.violationsFixed')}
          value="0"
          trend="down"
          color="violation"
        />
        <KpiTile
          icon={DollarSign}
          label={t('kpi.costSavings')}
          value="$0"
          trend="up"
          color="energy"
        />
        <KpiTile
          icon={Zap}
          label={t('kpi.gridImportReduced')}
          value="0 kWh"
          trend="down"
          color="warning"
        />
        <KpiTile
          icon={Sun}
          label={t('kpi.pvUtilization')}
          value="0%"
          trend="up"
          color="sun"
        />
      </div>

      {/* Timeline Controls */}
      <div className="flex items-center justify-between p-3 border-b border-border/30 bg-surface/30">
        <div className="flex items-center gap-2">
          <span className="text-caption text-text-muted">{t('timeline.dispatches')}: {dispatches.length}</span>
          <span className="w-px h-4 bg-border/30 mx-2" />
          <span className="text-caption text-text-muted">
            {selectedTimestep !== null 
              ? `${t('common.timestep')}: ${selectedTimestep}` 
              : t('timeline.selectTimestep')}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigateTimestep(-1)}
            disabled={!selectedTimestep || selectedTimestep <= (availableTimesteps[0] || 0)}
            aria-label="Previous timestep (k)"
          >
            <ChevronDown className="w-4 h-4 rotate-180" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigateTimestep(1)}
            disabled={!selectedTimestep || selectedTimestep >= (availableTimesteps[availableTimesteps.length - 1] || 0)}
            aria-label="Next timestep (j)"
          >
            <ChevronDown className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Dispatch Timeline */}
      <div className="flex-1 overflow-auto" role="list" aria-label={t('timeline.dispatchTimeline')}>
        {groupedDispatches.length === 0 ? (
          <div className="flex items-center justify-center h-full text-text-muted">
            <div className="text-center">
              <Clock className="w-12 h-12 mx-auto mb-3 text-text-muted/30" />
              <p className="text-body">{t('empty.noDispatches')}</p>
              <p className="text-caption mt-1">{t('empty.waitingForRun')}</p>
            </div>
          </div>
        ) : (
          <div className="space-y-2 p-3">
            {groupedDispatches.map(({ timestep, entries }) => (
              <TimestepGroup
                key={timestep}
                timestep={timestep}
                entries={entries}
                isSelected={selectedTimestep === timestep}
                isExpanded={expandedTimesteps.has(timestep)}
                onSelect={() => setSelectedTimestep(timestep)}
                featureFlags={featureFlags}
              />
            ))}
          </div>
        )}
      </div>

      {/* Batched Updates Indicator */}
      {batchedDispatches.length > 0 && (
        <div className="p-2 bg-sun/10 border-t border-sun/30 text-text-muted text-caption flex items-center gap-2">
          <Clock className="w-4 h-4" />
          <span>{batchedDispatches.length} new dispatch(es) batched</span>
        </div>
      )}
    </div>
  );
}

interface KpiTileProps {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  trend: 'up' | 'down' | 'neutral';
  color: 'energy' | 'violation' | 'warning' | 'sun';
}

function KpiTile({ icon: Icon, label, value, trend, color }: KpiTileProps) {
  return (
    <div className="glass-card p-3">
      <div className="flex items-center justify-between mb-2">
        <Icon className={`w-5 h-5 ${color === 'energy' ? 'text-energy' : color === 'violation' ? 'text-violation' : color === 'warning' ? 'text-warning' : 'text-sun'}`} />
        <span className={clsx('font-mono text-caption', trend === 'up' ? 'text-energy' : trend === 'down' ? 'text-violation' : 'text-text-muted')}>
          {trend === 'up' ? <TrendingUp className="w-4 h-4" /> : trend === 'down' ? <TrendingDown className="w-4 h-4" /> : <span className="w-4 h-4">—</span>}
        </span>
      </div>
      <p className="font-body font-medium text-body-sm text-text">{label}</p>
      <p className="font-mono text-data text-2xl mt-1">{value}</p>
    </div>
  );
}

interface TimestepGroupProps {
  timestep: number;
  entries: DispatchEntry[];
  isSelected: boolean;
  isExpanded: boolean;
  onSelect: () => void;
  featureFlags: { timelineRich: boolean };
}

function TimestepGroup({ timestep, entries, isSelected, isExpanded, onSelect, featureFlags }: TimestepGroupProps) {
  const { t } = useTranslation('workspace');
  const totalValue = entries.reduce((sum, e) => sum + e.valueKw, 0);
  const actionTypes = [...new Set(entries.map(e => e.actionType))];

  return (
    <div className={clsx(
      'rounded-lg border transition-all',
      isSelected ? 'border-sun/30 bg-sun/5' : 'border-border hover:border-sun/10'
    )}>
      <button
        onClick={onSelect}
        className="w-full flex items-center justify-between p-3 text-left"
        aria-expanded={isExpanded}
      >
        <div className="flex items-center gap-3">
          <span className={clsx('font-mono text-data w-16', isSelected ? 'text-sun' : 'text-text')}>
            {t('common.timestep')} {timestep}
          </span>
          <span className="text-caption text-text-muted">
            {entries.length} {t('timeline.actions')}
          </span>
          <span className={clsx('badge px-2 py-0.5 text-caption', actionTypes.length > 1 ? 'badge-sun' : 'badge-energy')}>
            {actionTypes.map(t => ACTION_LABELS[t] || t).join(', ')}
          </span>
          <span className="font-mono text-data text-sun ml-auto">
            {totalValue.toFixed(1)} kW
          </span>
          <ChevronDown className={clsx('w-4 h-4 text-text-muted transition-transform', isExpanded && 'rotate-180')} />
        </div>
      </button>

      {isExpanded && (
        <div className="border-t border-border/30 bg-surface/30 animate-slide-down">
          <div className="p-3 space-y-2">
            {entries.map((entry, idx) => (
              <DispatchEntryCard key={idx} entry={entry} featureFlags={featureFlags} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

interface DispatchEntryCardProps {
  entry: DispatchEntry;
  featureFlags: { timelineRich: boolean };
}

function DispatchEntryCard({ entry, featureFlags }: DispatchEntryCardProps) {
  const { t } = useTranslation('workspace');
  const Icon = ACTION_ICONS[entry.actionType] || ZapIcon;
  const isLimited = entry.limitedKw !== undefined && entry.limitedKw < (entry.requestedKw || entry.valueKw);

  return (
    <div className="glass-card p-3 rounded-lg border border-border/30">
      <div className="flex items-start gap-3">
        <div className={clsx('flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center', entry.actionType.includes('battery') ? 'bg-energy/10 text-energy' : 'bg-sun/10 text-sun')}>
          <Icon className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-data text-body-sm">{entry.assetId}</span>
            <span className={clsx('badge px-2 py-0.5 text-caption', entry.actionType.includes('battery') ? 'badge-energy' : 'badge-sun')}>
              {ACTION_LABELS[entry.actionType] || entry.actionType}
            </span>
            {isLimited && (
              <span className="badge badge-warning px-2 py-0.5 text-caption">
                {t('timeline.limited')}
              </span>
            )}
          </div>
          <div className="grid grid-cols-2 gap-2 text-caption">
            <div>
              <span className="text-text-muted">{t('timeline.value')}:</span>
              <span className="font-mono text-data ml-1">{entry.valueKw.toFixed(1)} kW</span>
            </div>
            {entry.requestedKw !== undefined && (
              <div>
                <span className="text-text-muted">{t('timeline.requested')}:</span>
                <span className="font-mono text-data ml-1">{entry.requestedKw.toFixed(1)} kW</span>
              </div>
            )}
            {entry.limitedKw !== undefined && (
              <div>
                <span className="text-text-muted">{t('timeline.limitedValue')}:</span>
                <span className="font-mono text-warning ml-1">{entry.limitedKw.toFixed(1)} kW</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Forward-compatible rich fields (hidden behind feature flag) */}
      {featureFlags.timelineRich && (
        <div className="mt-3 pt-3 border-t border-border/30 space-y-2 text-caption text-text-muted">
          {entry.reason && (
            <div className="flex gap-2">
              <span className="font-medium text-text">{t('timeline.reason')}:</span>
              <span>{entry.reason}</span>
            </div>
          )}
          {entry.gridChange && (
            <div className="flex gap-2">
              <span className="font-medium text-text">{t('timeline.gridChange')}:</span>
              <span>{entry.gridChange}</span>
            </div>
          )}
          {entry.verification && (
            <div className="flex gap-2">
              <span className="font-medium text-text">{t('timeline.verification')}:</span>
              <span>{entry.verification}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}