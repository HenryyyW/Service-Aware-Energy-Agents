import { useState } from 'react';
import { clsx } from 'clsx';
import { Eye, EyeOff, ChevronRight, ChevronDown, Sun, Zap, Battery, Car, LineChart, Cpu, AlertTriangle, ArrowUpDown, Thermometer, DollarSign } from 'lucide-react';
import type { LayerVisibility } from '../../api/types';

interface LayerTreeProps {
  layers: LayerVisibility;
  onToggle: (layer: keyof LayerVisibility) => void;
}

const layerGroups = [
  {
    label: 'Assets',
    icon: Cpu,
    layers: [
      { key: 'buildings', label: 'Buildings', icon: Cpu },
      { key: 'pv', label: 'Rooftop PV', icon: Sun },
      { key: 'batteries', label: 'Batteries', icon: Battery },
      { key: 'evs', label: 'EV Chargers', icon: Car },
      { key: 'flexible_loads', label: 'Flexible Loads', icon: Thermometer },
    ] as const,
  },
  {
    label: 'Grid',
    icon: Zap,
    layers: [
      { key: 'feeders', label: 'Feeders', icon: LineChart },
      { key: 'transformers', label: 'Transformers', icon: Cpu },
    ] as const,
  },
  {
    label: 'Analysis',
    icon: AlertTriangle,
    layers: [
      { key: 'violations', label: 'Violations', icon: AlertTriangle },
      { key: 'flows', label: 'Energy Flows', icon: ArrowUpDown },
      { key: 'voltage_heatmap', label: 'Voltage Heatmap', icon: Sun },
      { key: 'loading_heatmap', label: 'Loading Heatmap', icon: Battery },
      { key: 'lmp_prices', label: 'LMP Prices', icon: DollarSign },
    ] as const,
  },
];

export function LayerTree({ layers, onToggle }: LayerTreeProps) {
  const [expandedGroups, setExpandedGroups] = useState<string[]>(['Assets', 'Grid', 'Analysis']);

  const toggleGroup = (label: string) => {
    setExpandedGroups(prev => prev.includes(label)
      ? prev.filter(g => g !== label)
      : [...prev, label]
    );
  };

  return (
    <div className="space-y-4">
      {layerGroups.map((group) => {
        const isExpanded = expandedGroups.includes(group.label);
        const visibleCount = group.layers.filter(l => layers[l.key]).length;
        const totalCount = group.layers.length;

        return (
          <div key={group.label} className="space-y-1">
            <button
              onClick={() => toggleGroup(group.label)}
              className="flex items-center gap-2 w-full px-2 py-1.5 rounded-lg text-body-sm text-text-muted hover:text-text hover:bg-white/5 transition-colors"
              aria-expanded={isExpanded}
            >
              <group.icon className="w-4 h-4 flex-shrink-0" />
              <span className="font-medium flex-1 text-left">{group.label}</span>
              <span className="text-caption text-text-muted/50 px-2 py-0.5 rounded bg-surface">
                {visibleCount}/{totalCount}
              </span>
              {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            </button>

            {isExpanded && (
              <div className="space-y-1 ml-6 mt-1 border-l border-border/30 pl-2">
                {group.layers.map((layer) => {
                  const isVisible = layers[layer.key];
                  return (
                    <button
                      key={layer.key}
                      onClick={() => onToggle(layer.key)}
                      className={clsx(
                        'layer-item w-full justify-start',
                        isVisible ? 'layer-item-active' : ''
                      )}
                      aria-pressed={isVisible}
                    >
                      {isVisible ? <Eye className="w-4 h-4 flex-shrink-0" aria-hidden="true" /> : <EyeOff className="w-4 h-4 flex-shrink-0" aria-hidden="true" />}
                      <layer.icon className="w-4 h-4 flex-shrink-0 text-text-muted" />
                      <span className="flex-1 text-left">{layer.label}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}