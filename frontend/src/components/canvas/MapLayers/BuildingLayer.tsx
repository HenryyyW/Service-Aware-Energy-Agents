import { PolygonLayer } from '@deck.gl/layers';
import { type Building } from '../../../api/types';

interface BuildingLayerProps {
  buildings: Building[];
  timestepData: Record<string, any>;
  selectedBuildingId: string | null;
  onSelect: (buildingId: string) => void;
  getFillColor?: (building: Building, data: any) => [number, number, number, number];
  getElevation?: (building: Building, data: any) => number;
}

export function createBuildingLayer({
  buildings,
  timestepData,
  selectedBuildingId,
  onSelect,
  getFillColor,
  getElevation,
}: BuildingLayerProps) {
  const data = buildings.map((building) => {
    const buildingData = timestepData[building.building_id] || {};
    const load = buildingData.net_electricity_consumption || 0;
    const pvGen = buildingData.solar_generation || 0;
    const batterySoc = buildingData.electrical_storage_soc || 0;
    const netFlow = pvGen - load;

    return {
      ...building,
      load,
      pvGen,
      batterySoc,
      netFlow,
      isSelected: building.building_id === selectedBuildingId,
    };
  });

  const defaultGetFillColor = (d: any): [number, number, number, number] => {
    if (d.isSelected) return [245, 158, 11, 255];

    const netFlow = d.netFlow;
    if (netFlow > 10) {
      const intensity = Math.min(netFlow / 100, 1);
      return [
        Math.round(16 * (1 - intensity) + 245 * intensity),
        Math.round(185 * (1 - intensity) + 158 * intensity),
        Math.round(11 * (1 - intensity) + 11 * intensity),
        200
      ];
    } else if (netFlow < -10) {
      const intensity = Math.min(Math.abs(netFlow) / 100, 1);
      return [
        Math.round(16 * (1 - intensity) + 244 * intensity),
        Math.round(185 * (1 - intensity) + 63 * intensity),
        Math.round(11 * (1 - intensity) + 94 * intensity),
        200
      ];
    }
    return [27, 35, 54, 180];
  };

  const defaultGetElevation = (d: any): number => {
    return 4 + (d.batterySoc * 8) + Math.min(Math.abs(d.load) * 0.4, 4);
  };

  return new PolygonLayer({
    id: 'buildings',
    data,
    getPolygon: (d) => d.geometry?.coordinates?.[0] || [],
    getFillColor: getFillColor || defaultGetFillColor,
    getElevation: getElevation || defaultGetElevation,
    extruded: true,
    wireframe: false,
    getLineColor: [255, 255, 255, 50],
    getLineWidth: 1,
    lineWidthMinPixels: 1,
    pickable: true,
    onClick: (info: any) => {
      if (info.object) {
        onSelect(info.object.building_id);
      }
    },
    updateTriggers: {
      getFillColor: [timestepData, selectedBuildingId],
      getElevation: [timestepData],
    },
  });
}