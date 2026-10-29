import { useTranslation } from 'react-i18next';
import { type LucideIcon, FileText } from 'lucide-react';

interface LayerSwitcherProps {
  currentLayer: 'run' | 'community' | 'asset';
  onLayerChange: (layer: 'run' | 'community' | 'asset') => void;
  disabled?: boolean;
  className?: string;
}

const layerConfig: Record<'run' | 'community' | 'asset', { icon: LucideIcon; labelKey: string; shortLabelKey: string }> = {
  run: { icon: FileText, labelKey: 'report.layer.run', shortLabelKey: 'report.layer.run' },
  community: { icon: FileText, labelKey: 'report.layer.community', shortLabelKey: 'report.layer.community' },
  asset: { icon: FileText, labelKey: 'report.layer.asset', shortLabelKey: 'report.layer.asset' },
};

export function LayerSwitcher({ currentLayer, onLayerChange, disabled = false, className = '' }: LayerSwitcherProps) {
  const { t } = useTranslation('report');

  return (
    <div className={`flex items-center gap-1 bg-surface/50 rounded-lg p-1 border border-border/30 ${className}`} role="tablist" aria-label={t('report.layer.run')}>
      {(['run', 'community', 'asset'] as const).map((layer) => {
        const { icon: Icon, labelKey, shortLabelKey } = layerConfig[layer];
        const isActive = currentLayer === layer;
        return (
          <button
            key={layer}
            role="tab"
            aria-selected={isActive}
            onClick={() => !disabled && onLayerChange(layer)}
            disabled={disabled}
            className={`
              flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all
              ${isActive
                ? 'bg-surface text-text shadow-sm'
                : 'text-text-muted hover:text-text hover:bg-surface/50'}
              ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
            `}
            aria-label={t(shortLabelKey)}
          >
            <Icon className="w-4 h-4" aria-hidden="true" />
            <span className="hidden sm:inline">{t(labelKey)}</span>
          </button>
        );
      })}
    </div>
  );
}