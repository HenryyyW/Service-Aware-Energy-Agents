import { ScatterplotLayer } from '@deck.gl/layers';
import { type BatteryAsset } from '../../../api/types';

interface BatteryLayerProps {
  batteries: BatteryAsset[];
  timestepData: Record<string, any>;
  selectedAssetId: string | null;
  onSelect: (assetId: string) => void;
}

export function createBatteryLayer({
  batteries,
  timestepData,
  selectedAssetId,
  onSelect,
}: BatteryLayerProps) {
  const data = batteries.map((battery) => {
    const batteryData = {
      ...(battery.building_id ? timestepData[battery.building_id] : {}),
      ...(timestepData[battery.asset_id] || {}),
    };
    const soc = batteryData.electrical_storage_soc !== undefined
      ? batteryData.electrical_storage_soc
      : battery.soc;
    const power = batteryData.battery_power_kw || 0;
    const isCharging = power > 0;
    const isDischarging = power < 0;

    return {
      ...battery,
      soc: soc || 0,
      power,
      isCharging,
      isDischarging,
      isSelected: battery.asset_id === selectedAssetId,
      coordinates: battery.location
        ? [battery.location.lon, battery.location.lat] as [number, number]
        : [0, 0],
    };
  }).filter(b => b.coordinates[0] !== 0 || b.coordinates[1] !== 0);

  const getFillColor = (d: any): [number, number, number, number] => {
    if (d.isSelected) return [245, 158, 11, 255];

    if (d.isCharging) {
      return [16, 185, 129, 220];
    } else if (d.isDischarging) {
      return [245, 158, 11, 220];
    }
    return [139, 92, 246, 180];
  };

  const getRadius = (d: any): number => {
    return 12 + (d.soc * 15);
  };

  const mainLayer = new ScatterplotLayer({
    id: 'batteries',
    data,
    getPosition: (d) => d.coordinates,
    getFillColor,
    getRadius,
    radiusMinPixels: 10,
    radiusMaxPixels: 50,
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

  const ringLayer = new ScatterplotLayer({
    id: 'battery-soc-ring',
    data,
    getPosition: (d) => d.coordinates,
    getRadius: (d) => 12 + (d.soc * 15) + 4,
    getFillColor: [0, 0, 0, 0],
    getLineColor: (d) => {
      if (d.isSelected) return [245, 158, 11, 255];
      return [139, 92, 246, 150];
    },
    getLineWidth: 2,
    lineWidthMinPixels: 2,
    stroked: true,
    filled: false,
    updateTriggers: {
      getRadius: [timestepData],
      getLineColor: [timestepData, selectedAssetId],
    },
  });

  return [mainLayer, ringLayer];
}