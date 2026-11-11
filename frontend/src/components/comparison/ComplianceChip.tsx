import { clsx } from 'clsx';

export interface ComplianceChipProps {
  status: 'compliant' | 'warning' | 'failed';
}

export function ComplianceChip({ status }: ComplianceChipProps) {
  const config: Record<string, { glyph: string; label: string; className: string }> = {
    compliant: { glyph: '✓', label: 'compliant', className: 'text-energy border-energy/30' },
    warning:   { glyph: '⚠', label: 'warning', className: 'text-sun border-sun/30' },
    failed:    { glyph: '✗', label: 'failed',  className: 'text-violation border-violation/30' },
  };

  const c = config[status];

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded text-caption font-medium border',
        c.className
      )}
      title={`${c.label.toUpperCase()}: ${status === 'compliant' ? 'All grid constraints satisfied' : status === 'warning' ? 'At or near a grid limit' : 'Run did not complete or breached a hard limit'}`}
    >
      <span className="text-caption">{c.glyph}</span>
      <span className="text-caption">{c.label}</span>
    </span>
  );
}
