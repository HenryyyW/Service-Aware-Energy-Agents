import { PathLayer } from '@deck.gl/layers';
import { type Feeder } from '../../../api/types';

interface FeederLayerProps {
  feeders: Feeder[];
  timestepData: Record<string, any>;
  selectedFeederId: string | null;
  onSelect: (feederId: string) => void;
  showLoading?: boolean;
}

export function createFeederLayer({
  feeders,
  timestepData,
  selectedFeederId,
  onSelect,
  showLoading = false,
}: FeederLayerProps) {
  const data = feeders.map((feeder) => {
    const feederData = timestepData[feeder.feeder_id] || {};
    const loading = feederData.loading_pct || 0;
    const powerFlow = feederData.power_flow_kw || 0;
    const isOverloaded = loading > 100;

    return {
      ...feeder,
      loading,
      powerFlow,
      isOverloaded,
      isSelected: feeder.feeder_id === selectedFeederId,
      path: feeder.geometry?.coordinates || [],
    };
  });

  const getColor = (d: any): [number, number, number, number] => {
    if (d.isSelected) return [0, 192, 239, 255];

    if (showLoading) {
      if (d.isOverloaded) return [239, 68, 68, 220];
      if (d.loading > 80) return [0, 192, 239, 200];
      if (d.loading > 60) return [74, 201, 227, 180];
      return [16, 185, 129, 180];
    }

    if (d.powerFlow > 10) {
      return [16, 185, 129, 200];
    } else if (d.powerFlow < -10) {
      return [74, 201, 227, 200];
    }
    return [74, 201, 227, 150];
  };

  const getWidth = (d: any): number => {
    const baseWidth = 3;
    if (showLoading) {
      return baseWidth + (d.loading / 100) * 8;
    }
    return baseWidth + Math.min(Math.abs(d.powerFlow) / 100, 1) * 5;
  };

  return new PathLayer({
    id: 'feeders',
    data,
    getPath: (d) => d.path,
    getColor,
    getWidth,
    widthMinPixels: 2,
    widthMaxPixels: 20,
    pickable: true,
    onClick: (info: any) => {
      if (info.object) {
        onSelect(info.object.feeder_id);
      }
    },
    updateTriggers: {
      getColor: [timestepData, selectedFeederId, showLoading],
      getWidth: [timestepData, showLoading],
    },
  });
}