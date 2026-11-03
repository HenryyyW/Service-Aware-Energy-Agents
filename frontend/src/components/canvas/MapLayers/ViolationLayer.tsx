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

  // IEEE-style color scheme for power system violations
// Critical: Red (#dc2626), Warning: Amber (#f59e0b), Selected: Blue (#3b82f6)
const IEEE_COLORS = {
  critical: { fill: [220, 38, 38, 220], pulse: [220, 38, 38, 150], line: [220, 38, 38, 200] },
  warning: { fill: [245, 158, 11, 220], pulse: [245, 158, 11, 120], line: [245, 158, 11, 180] },
  selected: { fill: [59, 130, 246, 255], pulse: [59, 130, 246, 150], line: [59, 130, 246, 200] },
  normal: { fill: [34, 197, 94, 200] }, // Green for normal
};

const getFillColor = (d: any): [number, number, number, number] => {
  if (d.isSelected) return IEEE_COLORS.selected.fill as [number, number, number, number];

  if (d.severity === 'critical') return IEEE_COLORS.critical.fill as [number, number, number, number];
  return IEEE_COLORS.warning.fill as [number, number, number, number];
};

const getRadius = (d: any): number => {
  return d.severity === 'critical' ? 20 : 16;
};

const pulseLayerCritical = new ScatterplotLayer({
  id: 'violation-pulse-critical',
  data: data.filter(d => d.severity === 'critical'),
  getPosition: (d) => d.coordinates,
  getRadius: (d) => getRadius(d) + 10 + Math.sin(Date.now() / 200) * 5,
  getFillColor: IEEE_COLORS.critical.pulse as [number, number, number, number],
  getLineColor: IEEE_COLORS.critical.line as [number, number, number, number],
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
  getFillColor: IEEE_COLORS.warning.pulse as [number, number, number, number],
  getLineColor: IEEE_COLORS.warning.line as [number, number, number, number],
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
    // Normalize: 0.95 pu = 0 (blue), 1.00 pu = 0.33 (green), 1.05 pu = 0.66 (yellow), 1.10+ pu = 1 (red)
    // For violations < 0.95: 0.90 pu = -0.33 (dark blue), 0.85 pu = -0.66 (darker blue)
    voltageNormalized: Math.max(-1, Math.min(2, (bus.voltage_pu - 1.0) / 0.1 + 0.5)),
  }));

  return new ScatterplotLayer({
    id: 'voltage-heatmap',
    data,
    getPosition: (d) => d.coordinates,
    getFillColor: (d) => {
      const v = Math.max(0, Math.min(1, d.voltageNormalized));
      // IEEE voltage profile: Blue (<0.95) -> Green (0.95-1.05) -> Yellow (1.05-1.10) -> Red (>1.10)
      if (v < 0.33) {
        // Low voltage: Blue gradient
        const t = v / 0.33;
        return [
          Math.round(30 * t + 15 * (1 - t)),      // R: 15-30 (dark blue)
          Math.round(60 * t + 30 * (1 - t)),      // G: 30-60
          Math.round(200 * (1 - t) + 150 * t),    // B: 200-150
          180
        ];
      } else if (v < 0.5) {
        // Nominal low: Green-blue
        const t = (v - 0.33) / 0.17;
        return [
          Math.round(34 * (1 - t) + 34 * t),      // R: ~34
          Math.round(150 * t + 60 * (1 - t)),     // G: 60-150
          Math.round(100 * (1 - t) + 80 * t),     // B: 100-80
          180
        ];
      } else if (v < 0.66) {
        // Nominal: Green
        return [34, 197, 94, 180];
      } else if (v < 0.83) {
        // High voltage: Yellow
        const t = (v - 0.66) / 0.17;
        return [
          Math.round(234 * t + 34 * (1 - t)),     // R: 34-234
          Math.round(179 * t + 197 * (1 - t)),    // G: 197-179
          Math.round(94 * (1 - t)),               // B: 94-0
          180
        ];
      } else {
        // Violation: Red
        return [220, 38, 38, 200];
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
    // Normalize: 50% = 0.33 (green), 75% = 0.5 (yellow), 100% = 0.66 (orange), 125% = 0.83 (red), 150%+ = 1 (dark red)
    loadingNormalized: Math.max(0, Math.min(1, el.loading_pct / 150)),
  }));

  return new ScatterplotLayer({
    id: 'loading-heatmap',
    data,
    getPosition: (d) => d.coordinates,
    getFillColor: (d) => {
      const v = d.loadingNormalized;
      // IEEE loading profile: Green (<50%) -> Yellow (50-75%) -> Orange (75-100%) -> Red (100-125%) -> Dark Red (>125%)
      if (v < 0.33) {
        // Normal loading: Green
        return [34, 197, 94, 150];
      } else if (v < 0.5) {
        // Caution: Yellow
        const t = (v - 0.33) / 0.17;
        return [
          Math.round(234 * t + 34 * (1 - t)),
          Math.round(179 * t + 197 * (1 - t)),
          Math.round(94 * (1 - t)),
          180
        ];
      } else if (v < 0.66) {
        // Warning: Orange
        const t = (v - 0.5) / 0.16;
        return [
          249,
          Math.round(115 * (1 - t) + 79 * t),  // 115 -> 79
          22,
          200
        ];
      } else if (v < 0.83) {
        // Critical: Red
        return [220, 38, 38, 200];
      } else {
        // Severe: Dark Red
        return [153, 27, 27, 220];
      }
    },
    getRadius: 25,
    radiusMinPixels: 20,
    radiusMaxPixels: 80,
    pickable: false,
  });
}