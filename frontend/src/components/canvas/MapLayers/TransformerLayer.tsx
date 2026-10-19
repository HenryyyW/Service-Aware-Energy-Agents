import { ScatterplotLayer } from '@deck.gl/layers';
import { type Transformer } from '../../../api/types';

interface TransformerLayerProps {
  transformers: Transformer[];
  timestepData: Record<string, any>;
  selectedTransformerId: string | null;
  onSelect: (transformerId: string) => void;
}

export function createTransformerLayer({
  transformers,
  timestepData,
  selectedTransformerId,
  onSelect,
}: TransformerLayerProps) {
  const data = transformers.map((transformer) => {
    const transformerData = timestepData[transformer.transformer_id] || {};
    const loading = transformerData.loading_pct !== undefined
      ? transformerData.loading_pct
      : transformer.loading_pct || 0;
    const isOverloaded = loading > 100;

    return {
      ...transformer,
      loading,
      isOverloaded,
      isSelected: transformer.transformer_id === selectedTransformerId,
      coordinates: [transformer.lon, transformer.lat] as [number, number],
    };
  });

  const getFillColor = (d: any): [number, number, number, number] => {
    if (d.isSelected) return [245, 158, 11, 255];

    if (d.isOverloaded) return [239, 68, 68, 220];
    if (d.loading > 80) return [245, 158, 11, 200];
    if (d.loading > 60) return [234, 179, 8, 180];
    return [234, 179, 8, 180];
  };

  const getRadius = (d: any): number => {
    return 15 + (d.loading / 100) * 15;
  };

  const ringLayer = new ScatterplotLayer({
    id: 'transformer-loading-ring',
    data,
    getPosition: (d) => d.coordinates,
    getRadius: (d) => 15 + (d.loading / 100) * 15 + 6,
    getFillColor: [0, 0, 0, 0],
    getLineColor: getFillColor,
    getLineWidth: 3,
    lineWidthMinPixels: 3,
    stroked: true,
    filled: false,
    updateTriggers: {
      getRadius: [timestepData],
      getLineColor: [timestepData, selectedTransformerId],
    },
  });

  const mainLayer = new ScatterplotLayer({
    id: 'transformers',
    data,
    getPosition: (d) => d.coordinates,
    getFillColor,
    getRadius,
    radiusMinPixels: 12,
    radiusMaxPixels: 40,
    pickable: true,
    onClick: (info: any) => {
      if (info.object) {
        onSelect(info.object.transformer_id);
      }
    },
    updateTriggers: {
      getFillColor: [timestepData, selectedTransformerId],
      getRadius: [timestepData],
    },
  });

  return [ringLayer, mainLayer];
}