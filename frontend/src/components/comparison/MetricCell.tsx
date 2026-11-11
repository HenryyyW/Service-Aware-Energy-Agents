import { clsx } from 'clsx';
import { ExternalLink } from '../../utils/lucide';

export interface MetricCellProps {
  label: string;
  value?: number | string;
  unit: string;
  limit?: number | string;      // comparison limit (e.g. import_limit_kw)
  linkHref?: string;            // "open record" URL
  linkLabel?: string;           // link text
  format?: (v: number) => string;
}

export function MetricCell({
  label,
  value,
  unit,
  limit,
  linkHref,
  linkLabel,
  format = (v: number) => v.toLocaleString(),
}: MetricCellProps) {
  const hasValue = value !== undefined && value !== null;
  const displayValue = hasValue
    ? (typeof value === 'number' ? format(value) : String(value))
    : '—';
  const isExceedingLimit =
    limit !== undefined &&
    hasValue &&
    typeof value === 'number' &&
    typeof limit === 'number' &&
    value > limit;
  const valueClass = clsx('font-mono text-data', isExceedingLimit ? 'text-violation' : 'text-text');

  return (
    <div className="flex flex-col gap-1">
      <label className="text-caption text-text-muted">{label}</label>
      <div className="flex items-baseline gap-1">
        {linkHref && linkLabel ? (
          <a
            href={linkHref}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 underline underline-offset-4 hover:no-underline"
          >
            <span className={valueClass}>{displayValue}</span>
            <span className="text-caption text-text-muted">{unit}</span>
            <ExternalLink className="w-3 h-3 text-text-muted" aria-label={`Open record: ${linkLabel}`} />
          </a>
        ) : (
          <>
            <span className={valueClass}>{displayValue}</span>
            <span className="text-caption text-text-muted">{unit}</span>
          </>
        )}
      </div>
      {limit !== undefined && hasValue && typeof value === 'number' && typeof limit === 'number' ? (
        <p className="text-[10px] text-text-muted">
          {`limit: ${format(limit)} ${unit}`}
        </p>
      ) : null}
    </div>
  );
}
