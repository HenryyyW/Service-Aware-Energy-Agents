import { ScatterplotLayer } from '@deck.gl/layers';
import { type Building } from '../../../api/types';

interface LMPLayerProps {
  buildings: Building[];
  lmpPrices: Record<string, number>;
  timestepData: Record<string, any>;
  selectedBuildingId: string | null;
  onSelect: (buildingId: string) => void;
}

export function createLMPLayer({
  buildings,
  lmpPrices,
  timestepData,
  selectedBuildingId,
  onSelect,
}: LMPLayerProps) {
  if (!lmpPrices || Object.keys(lmpPrices).length === 0) return null;

  const prices = Object.values(lmpPrices);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const priceSpread = maxPrice - minPrice;

  const data = buildings.map((building) => {
    const lmp = lmpPrices[building.building_id] || 0;
    const buildingData = timestepData[building.building_id] || {};
    const load = buildingData.net_electricity_consumption || 0;
    const pvGen = buildingData.solar_generation || 0;
    const netFlow = pvGen - load;

    // Normalize price to 0-1 for color mapping
    const normalizedPrice = priceSpread > 0 ? (lmp - minPrice) / priceSpread : 0.5;

    return {
      ...building,
      lmp,
      load,
      pvGen,
      netFlow,
      normalizedPrice,
      isSelected: building.building_id === selectedBuildingId,
      minPrice,
      maxPrice,
      priceSpread,
    };
  });

  const getFillColor = (d: any): [number, number, number, number] => {
    if (d.isSelected) return [0, 192, 239, 255]; // --color-sun (IEEE blue)

    // IEEE-blue sequential ramp (low -> high price): #005d94 -> #00C0EF
    const t = d.normalizedPrice;
    return [
      0,                                     // R
      Math.round(93 * (1 - t) + 192 * t),    // G
      Math.round(148 * (1 - t) + 239 * t),   // B
      220,
    ];
  };

  const getRadius = (d: any): number => {
    // Base radius with slight variation based on price
    return 0.00008 + (d.normalizedPrice * 0.00004);
  };

  return new ScatterplotLayer({
    id: 'lmp-prices',
    data,
    getPosition: (d) => [d.location?.lon || 0, d.location?.lat || 0],
    getFillColor,
    getRadius,
    pickable: true,
    onClick: (info: any) => {
      if (info.object) {
        onSelect(info.object.building_id);
      }
    },
    updateTriggers: {
      getFillColor: [lmpPrices, selectedBuildingId],
      getRadius: [lmpPrices],
    },
  });
}

// Legend helper for LMP layer
export function getLMPColorScale(minPrice: number, maxPrice: number, steps = 5): Array<{ price: number; color: string; label: string }> {
  const scale = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const price = minPrice + (maxPrice - minPrice) * t;
    // IEEE-blue sequential ramp: #005d94 -> #00C0EF
    const r = 0;
    const g = Math.round(93 * (1 - t) + 192 * t);
    const b = Math.round(148 * (1 - t) + 239 * t);
    scale.push({
      price,
      color: `rgb(${r}, ${g}, ${b})`,
      label: `$${price.toFixed(3)}/kWh`,
    });
  }
  return scale;
}