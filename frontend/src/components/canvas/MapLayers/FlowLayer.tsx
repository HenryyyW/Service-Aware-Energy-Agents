import { PathLayer, ScatterplotLayer } from '@deck.gl/layers';

interface EnergyFlow {
  from: { lat: number; lon: number; type: string; id: string };
  to: { lat: number; lon: number; type: string; id: string };
  power_kw: number;
  type: 'generation' | 'consumption' | 'storage_charge' | 'storage_discharge' | 'grid_import' | 'grid_export' | 'ev_charge' | 'v2g' | 'sharing';
}

interface FlowLayerProps {
  flows: EnergyFlow[];
  animationSpeed?: number;
  showParticles?: boolean;
}

export function createFlowLayer({ flows, animationSpeed = 1, showParticles = true }: FlowLayerProps) {
  if (flows.length === 0) return null;

  const particleData = flows.flatMap((flow, flowIndex) => {
    const particleCount = Math.max(3, Math.min(15, Math.abs(flow.power_kw) / 20));
    const particles = [];

    for (let i = 0; i < particleCount; i++) {
      const phase = (i / particleCount + (Date.now() / 2000) * animationSpeed) % 1;
      particles.push({
        flowIndex,
        flow,
        phase,
        coordinates: [
          flow.from.lon + (flow.to.lon - flow.from.lon) * phase,
          flow.from.lat + (flow.to.lat - flow.from.lat) * phase,
        ] as [number, number],
      });
    }
    return particles;
  });

  const getFlowColor = (flow: EnergyFlow): [number, number, number, number] => {
    switch (flow.type) {
      case 'generation':
        return [245, 158, 11, 200];
      case 'consumption':
        return [244, 63, 94, 200];
      case 'storage_charge':
        return [16, 185, 129, 200];
      case 'storage_discharge':
        return [245, 158, 11, 200];
      case 'grid_import':
        return [234, 179, 8, 200];
      case 'grid_export':
        return [16, 185, 129, 200];
      case 'ev_charge':
        return [6, 182, 212, 200];
      case 'v2g':
        return [6, 182, 212, 200];
      case 'sharing':
        return [139, 92, 246, 200];
      default:
        return [150, 150, 150, 150];
    }
  };

  const getParticleColor = (d: any): [number, number, number, number] => {
    const color = getFlowColor(d.flow);
    const alpha = d.phase < 0.1 ? d.phase * 10 : d.phase > 0.9 ? (1 - d.phase) * 10 : 1;
    return [color[0], color[1], color[2], Math.round(color[3] * alpha)];
  };

  const getParticleRadius = (d: any): number => {
    const baseSize = Math.max(4, Math.min(12, Math.abs(d.flow.power_kw) / 30));
    return baseSize * (0.8 + 0.2 * Math.sin(d.phase * Math.PI * 2));
  };

  const lineData = flows.map(flow => ({
    ...flow,
    path: [
      [flow.from.lon, flow.from.lat],
      [flow.to.lon, flow.to.lat],
    ] as [number, number][],
    color: getFlowColor(flow),
    width: Math.max(2, Math.min(8, Math.abs(flow.power_kw) / 50)),
  }));

  const lineLayer = new PathLayer({
    id: 'flow-lines',
    data: lineData,
    getPath: (d) => d.path,
    getColor: (d) => d.color,
    getWidth: (d) => d.width,
    widthMinPixels: 1,
    widthMaxPixels: 10,
    pickable: false,
  });

  if (!showParticles || particleData.length === 0) {
    return lineLayer;
  }

  const particleLayer = new ScatterplotLayer({
    id: 'flow-particles',
    data: particleData,
    getPosition: (d) => d.coordinates,
    getFillColor: getParticleColor,
    getRadius: getParticleRadius,
    radiusMinPixels: 3,
    radiusMaxPixels: 15,
    pickable: false,
    updateTriggers: {
      getFillColor: [Date.now()],
      getRadius: [Date.now()],
      getPosition: [Date.now()],
    },
  });

  return [lineLayer, particleLayer];
}