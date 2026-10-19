import { ScatterplotLayer } from '@deck.gl/layers';
import { type Building, type PVAsset } from '../../../api/types';

interface PVLayerProps {
  buildings: Building[];
  pvAssets: PVAsset[];
  timestepData: Record<string, any>;
  selectedAssetId: string | null;
  onSelect: (assetId: string) => void;
}

export function createPVLayer({
  buildings,
  pvAssets,
  timestepData,
  selectedAssetId,
  onSelect,
}: PVLayerProps) {
  const data = pvAssets.map((pv) => {
    const building = buildings.find(b => b.building_id === pv.building_id);
    const buildingData = timestepData[pv.building_id] || {};
    const generation = buildingData.solar_generation || 0;
    const outputRatio = generation > 0 ? 1 : 0;

    if (!building?.location) return null;

    return {
      ...pv,
      building,
      generation,
      outputRatio,
      isSelected: pv.asset_id === selectedAssetId,
      coordinates: [building.location.lon, building.location.lat] as [number, number],
    };
  }).filter(Boolean);

  const getFillColor = (d: any): [number, number, number, number] => {
    if (d.isSelected) return [245, 158, 11, 255];

    const ratio = d.outputRatio;
    if (ratio > 0.1) {
      const intensity = Math.min(ratio, 1);
      return [
        Math.round(245 * intensity),
        Math.round(158 * intensity),
        Math.round(11 * intensity),
        Math.round(150 + 105 * intensity)
      ];
    }
    return [100, 80, 20, 100];
  };

  const getRadius = (d: any): number => {
    return Math.max(8, Math.min(24, 8 + d.generation * 1.5));
  };

  return new ScatterplotLayer({
    id: 'pv-assets',
    data,
    getPosition: (d) => d.coordinates,
    getFillColor,
    getRadius,
    radiusMinPixels: 6,
    radiusMaxPixels: 40,
    pickable: true,
    onClick: (info: any) => {
      if (info.object) {
        onSelect(info.object.asset_id);
      }
    },
    updateTriggers: {
      getFillColor: [timestepData, selectedAssetId],
      getRadius: [timestepData],
    },
  });
}