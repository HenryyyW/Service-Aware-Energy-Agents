import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { MapViewport, LayerVisibility, SelectedAsset } from '../api/types';

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
    (set) => ({
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