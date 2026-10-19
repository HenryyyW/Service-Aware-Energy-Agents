import { ScatterplotLayer } from '@deck.gl/layers';
import { type EVAsset } from '../../../api/types';

interface EVLayerProps {
  evs: EVAsset[];
  timestepData: Record<string, any>;
  selectedAssetId: string | null;
  onSelect: (assetId: string) => void;
}

export function createEVLayer({
  evs,
  timestepData,
  selectedAssetId,
  onSelect,
}: EVLayerProps) {
  const data = evs.map((ev) => {
    const evData = {
      ...(ev.building_id ? timestepData[ev.building_id] : {}),
      ...(timestepData[ev.asset_id] || {}),
    };
    const soc = evData.connected_electric_vehicle_at_charger_soc !== undefined
      ? evData.connected_electric_vehicle_at_charger_soc
      : ev.soc;
    const chargingPower = evData.ev_charge_kw || 0;
    const isCharging = chargingPower > 0;
    const departureRisk = ev.departure_time && ev.target_soc && soc < ev.target_soc;

    return {
      ...ev,
      soc: soc || 0,
      chargingPower,
      isCharging,
      departureRisk,
      isSelected: ev.asset_id === selectedAssetId,
      coordinates: ev.location
        ? [ev.location.lon, ev.location.lat] as [number, number]
        : [0, 0],
    };
  }).filter(ev => ev.coordinates[0] !== 0 || ev.coordinates[1] !== 0);

  const getFillColor = (d: any): [number, number, number, number] => {
    if (d.isSelected) return [245, 158, 11, 255];

    if (d.departureRisk) {
      return [239, 68, 68, 220];
    }

    if (d.isCharging) {
      return [6, 182, 212, 220];
    }

    return [6, 182, 212, 120];
  };

  const getRadius = (d: any): number => {
    return 10 + (d.soc * 15);
  };

  return new ScatterplotLayer({
    id: 'evs',
    data,
    getPosition: (d) => d.coordinates,
    getFillColor,
    getRadius,
    radiusMinPixels: 8,
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