import { clsx } from 'clsx';

export interface StrategyMapProps {
  buildings: Array<{
    building_id: string;
    building_type?: string;
    location?: { lat: number; lon: number };
  }>;
  violations?: Array<{
    element: string;
    elementType: string;
    value: number;
    limit: number;
    type: 'voltage' | 'loading';
  }>;
  className?: string;
}

export function StrategyMap({ buildings, violations, className }: StrategyMapProps) {
  const buildingList = buildings ?? [];
  const violationList = violations ?? [];

  const violationMap = new Map<string, { value: number; limit: number; type: string }>();
  violationList.forEach((v) => {
    violationMap.set(v.element, v);
  });

  const positions: Array<{ lat: number; lon: number }> = buildingList
    .map((b) => b.location)
    .filter((l): l is { lat: number; lon: number } => l !== undefined);

  const centerLat =
    positions.length > 0
      ? positions.reduce((s, l) => s + l.lat, 0) / positions.length
      : 34.05;
  const centerLon =
    positions.length > 0
      ? positions.reduce((s, l) => s + l.lon, 0) / positions.length
      : -118.24;

  const positionsList = positions.map((l) => [l.lat, l.lon]);

  const minLat = positionsList.length > 0 ? Math.min(...positionsList.map((p) => p[0])) : centerLat;
  const maxLat = positionsList.length > 0 ? Math.max(...positionsList.map((p) => p[0])) : centerLat;
  const minLon = positionsList.length > 0 ? Math.min(...positionsList.map((p) => p[1])) : centerLon;
  const maxLon = positionsList.length > 0 ? Math.max(...positionsList.map((p) => p[1])) : centerLon;

  const latSpan = maxLat - minLat || 1;
  const lonSpan = maxLon - minLon || 1;

  const normalizedPositions = buildingList.map((b) => {
    if (!b.location) return { ...b, x: 50, y: 50 };
    const x = ((b.location.lon - minLon) / lonSpan) * 100;
    const y = 100 - ((b.location.lat - minLat) / latSpan) * 100;
    return { ...b, x, y };
  });

  return (
    <div className={clsx('relative w-full h-full aspect-square bg-surface rounded-lg border border-border/30 overflow-hidden', className)}>
      <div className="absolute inset-0 bg-white/10" />

      <div className="absolute inset-0">
        {normalizedPositions.map((b) => {
          const v = violationMap.get(b.building_id);
          const hasViolation = !!v;
          const isCritical = v && v.type === 'voltage' && v.value > v.limit * 1.02;

          return (
            <div
              key={b.building_id}
              className="absolute flex items-center justify-center"
              style={{ left: `${b.x}%`, top: `${b.y}%` }}
            >
              <button
                type="button"
                className={clsx(
                  'flex h-6 w-6 items-center justify-center rounded border-2 border-white shadow-md text-xs font-bold',
                  isCritical
                    ? 'bg-violation text-white'
                    : hasViolation
                    ? 'bg-sun text-space'
                    : 'bg-energy text-space'
                )}
                title={`${b.building_id}${v ? ` (${v.type}: ${v.value.toFixed(2)} / ${v.limit})` : ''}`}
              >
                {hasViolation ? '!' : '●'}
              </button>
            </div>
          );
        })}
      </div>

      <div className="absolute bottom-2 left-2 right-2 p-2 bg-white/90 backdrop-blur rounded-lg border border-border/30 text-[10px] text-text-muted">
        <div className="flex flex-wrap gap-3">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-energy text-space" />
            <span>OK</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-sun text-space" />
            <span>Warning</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-violation text-white" />
            <span>Failed</span>
          </span>
        </div>
      </div>
    </div>
  );
}
