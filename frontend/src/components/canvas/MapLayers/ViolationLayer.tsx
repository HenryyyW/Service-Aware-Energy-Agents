import { ScatterplotLayer } from '@deck.gl/layers';

interface Violation {
  type: 'voltage' | 'loading';
  element: string;
  elementType: 'bus' | 'line' | 'transformer';
  value: number;
  limit: number;
  severity: 'warning' | 'critical';
  location: { lat: number; lon: number };
  timestamp: number;
}

interface ViolationLayerProps {
  violations: Violation[];
  selectedViolationId: string | null;
  onSelect: (violationId: string) => void;
}

export function createViolationLayer({
  violations,
  selectedViolationId,
  onSelect,
}: ViolationLayerProps) {
  if (violations.length === 0) return null;

  const data = violations.map((v, _index) => ({
    ...v,
    id: `${v.type}-${v.element}-${v.timestamp}`,
    isSelected: `${v.type}-${v.element}-${v.timestamp}` === selectedViolationId,
    coordinates: [v.location.lon, v.location.lat] as [number, number],
  }));

  const getFillColor = (d: any): [number, number, number, number] => {
    if (d.isSelected) return [245, 158, 11, 255];

    if (d.severity === 'critical') return [239, 68, 68, 220];
    return [245, 158, 11, 200];
  };

  const getRadius = (d: any): number => {
    return d.severity === 'critical' ? 20 : 16;
  };

  const pulseLayerCritical = new ScatterplotLayer({
    id: 'violation-pulse-critical',
    data: data.filter(d => d.severity === 'critical'),
    getPosition: (d) => d.coordinates,
    getRadius: (d) => getRadius(d) + 10 + Math.sin(Date.now() / 200) * 5,
    getFillColor: [239, 68, 68, 0],
    getLineColor: [239, 68, 68, 150],
    getLineWidth: 2,
    lineWidthMinPixels: 2,
    stroked: true,
    filled: false,
    updateTriggers: {
      getRadius: [Date.now()],
    },
  });

  const pulseLayerWarning = new ScatterplotLayer({
    id: 'violation-pulse-warning',
    data: data.filter(d => d.severity === 'warning'),
    getPosition: (d) => d.coordinates,
    getRadius: (d) => getRadius(d) + 8 + Math.sin(Date.now() / 300) * 4,
    getFillColor: [245, 158, 11, 0],
    getLineColor: [245, 158, 11, 120],
    getLineWidth: 2,
    lineWidthMinPixels: 2,
    stroked: true,
    filled: false,
    updateTriggers: {
      getRadius: [Date.now()],
    },
  });

  const mainLayer = new ScatterplotLayer({
    id: 'violations',
    data,
    getPosition: (d) => d.coordinates,
    getFillColor,
    getRadius,
    radiusMinPixels: 12,
    radiusMaxPixels: 50,
    pickable: true,
    onClick: (info: any) => {
      if (info.object) {
        onSelect(info.object.id);
      }
    },
    updateTriggers: {
      getFillColor: [selectedViolationId],
      getRadius: [selectedViolationId],
    },
  });

  return [pulseLayerCritical, pulseLayerWarning, mainLayer];
}

interface VoltageHeatmapProps {
  buses: Array<{
    bus_id: string;
    lat: number;
    lon: number;
    voltage_pu: number;
    violation?: boolean;
  }>;
  showHeatmap: boolean;
}

export function createVoltageHeatmapLayer({ buses, showHeatmap }: VoltageHeatmapProps) {
  if (!showHeatmap || buses.length === 0) return null;

  const data = buses.map(bus => ({
    ...bus,
    coordinates: [bus.lon, bus.lat] as [number, number],
    voltageNormalized: Math.max(0, Math.min(1, (bus.voltage_pu - 0.95) / 0.1)),
  }));

  return new ScatterplotLayer({
    id: 'voltage-heatmap',
    data,
    getPosition: (d) => d.coordinates,
    getFillColor: (d) => {
      const v = d.voltageNormalized;
      if (v < 0.5) {
        const t = v * 2;
        return [
          Math.round(59 * t),
          Math.round(130 * t + 246 * (1 - t)),
          Math.round(246 * (1 - t) + 246 * t),
          150
        ];
      } else {
        const t = (v - 0.5) * 2;
        return [
          Math.round(246 * (1 - t) + 239 * t),
          Math.round(246 * (1 - t) + 68 * t),
          Math.round(246 * (1 - t) + 68 * t),
          150
        ];
      }
    },
    getRadius: 20,
    radiusMinPixels: 15,
    radiusMaxPixels: 60,
    pickable: false,
  });
}

interface LoadingHeatmapProps {
  elements: Array<{
    element_id: string;
    lat: number;
    lon: number;
    loading_pct: number;
    type: 'line' | 'transformer';
  }>;
  showHeatmap: boolean;
}

export function createLoadingHeatmapLayer({ elements, showHeatmap }: LoadingHeatmapProps) {
  if (!showHeatmap || elements.length === 0) return null;

  const data = elements.map(el => ({
    ...el,
    coordinates: [el.lon, el.lat] as [number, number],
    loadingNormalized: Math.max(0, Math.min(1, el.loading_pct / 150)),
  }));

  return new ScatterplotLayer({
    id: 'loading-heatmap',
    data,
    getPosition: (d) => d.coordinates,
    getFillColor: (d) => {
      const v = d.loadingNormalized;
      if (v < 0.33) return [16, 185, 129, 150];
      else if (v < 0.66) return [234, 179, 8, 150];
      else if (v < 1.0) return [249, 115, 22, 150];
      return [239, 68, 68, 180];
    },
    getRadius: 25,
    radiusMinPixels: 20,
    radiusMaxPixels: 80,
    pickable: false,
  });
}