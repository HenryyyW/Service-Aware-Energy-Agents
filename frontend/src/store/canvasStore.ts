import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { MapViewport, LayerVisibility, SelectedAsset, NetworkGeometry } from '../api/types';
import { api } from '../api/client';
import { WebMercatorViewport } from '@deck.gl/core';
import { useScenarioStore } from './scenarioStore';

interface CanvasState {
  // Map viewport
  viewport: MapViewport;
  setViewport: (viewport: Partial<MapViewport>) => void;
  resetViewport: () => void;

  // Layer visibility
  layers: LayerVisibility;
  toggleLayer: (layer: keyof LayerVisibility) => void;
  setLayer: (layer: keyof LayerVisibility, visible: boolean) => void;
  setLayers: (layers: Partial<LayerVisibility>) => void;

  // Selection
  selectedAsset: SelectedAsset | null;
  selectAsset: (asset: SelectedAsset | null) => void;

  // Map style
  mapStyle: 'dark' | 'light' | 'satellite';
  setMapStyle: (style: 'dark' | 'light' | 'satellite') => void;

  // Community bounds (for fitting map to community)
  communityBounds: [[number, number], [number, number]] | null;
  setCommunityBounds: (bounds: [[number, number], [number, number]] | null) => void;

  // Network geometry (real pandapower network data)
  networkGeometry: NetworkGeometry | null;
  setNetworkGeometry: (geometry: NetworkGeometry | null) => void;
  fetchNetworkGeometry: () => Promise<void>;
  fitToNetworkBounds: () => void;
}

const DEFAULT_VIEWPORT: MapViewport = {
  longitude: -105.0000,
  latitude: 40.0000,
  zoom: 16,
  pitch: 48,
  bearing: 0,
};

const DEFAULT_LAYERS: LayerVisibility = {
  buildings: true,
  pv: true,
  batteries: true,
  evs: true,
  flexible_loads: true,
  feeders: true,
  transformers: true,
  violations: true,
  flows: true,
  voltage_heatmap: false,
  loading_heatmap: false,
};

export const useCanvasStore = create<CanvasState>()(
  persist(
    (set, get) => ({
      viewport: DEFAULT_VIEWPORT,
      setViewport: (viewport) => set((state) => ({ viewport: { ...state.viewport, ...viewport } })),
      resetViewport: () => set({ viewport: DEFAULT_VIEWPORT }),

      layers: DEFAULT_LAYERS,
      toggleLayer: (layer) => set((state) => ({ layers: { ...state.layers, [layer]: !state.layers[layer] } })),
      setLayer: (layer, visible) => set((state) => ({ layers: { ...state.layers, [layer]: visible } })),
      setLayers: (layers) => set((state) => ({ layers: { ...state.layers, ...layers } })),

      selectedAsset: null,
      selectAsset: (asset) => set({ selectedAsset: asset }),

      mapStyle: 'dark',
      setMapStyle: (style) => set({ mapStyle: style }),

      communityBounds: null,
      setCommunityBounds: (bounds) => set({ communityBounds: bounds }),

      networkGeometry: null,
      setNetworkGeometry: (geometry) => set({ networkGeometry: geometry }),
      fetchNetworkGeometry: async () => {
        try {
          // Get current scenario from scenario store
          const currentScenario = useScenarioStore.getState().currentScenario;
          const scenarioId = currentScenario?.scenario_id || currentScenario?.community?.name;
          const geometry = await api.getNetworkGeometry(scenarioId);
          set({ networkGeometry: geometry });
        } catch (error) {
          console.error('Failed to fetch network geometry:', error);
        }
      },
      fitToNetworkBounds: () => {
        const { networkGeometry, setViewport } = get();
        const bounds = networkGeometry?.bounds;
        if (!bounds || bounds.min_lon === undefined || bounds.max_lon === undefined
          || bounds.min_lat === undefined || bounds.max_lat === undefined) return;

        const fitted = new WebMercatorViewport({
          width: window.innerWidth,
          height: window.innerHeight,
        }).fitBounds([
          [bounds.min_lon, bounds.min_lat],
          [bounds.max_lon, bounds.max_lat],
        ], {
          padding: { left: Math.min(460, window.innerWidth * 0.3), right: Math.min(480, window.innerWidth * 0.3), top: 120, bottom: 220 },
          maxZoom: 18,
        });

        setViewport({
          longitude: fitted.longitude,
          latitude: fitted.latitude,
          zoom: fitted.zoom,
          pitch: 0,
          bearing: 0,
        });
      },
    }),
    {
      name: 'canvas-store',
      partialize: (state) => ({
        mapStyle: state.mapStyle,
        layers: state.layers,
      }),
    }
  )
);