import { useRef, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import Map from 'react-map-gl/maplibre';
import Deck from '@deck.gl/react';
import { Layer } from '@deck.gl/core';
import { useCanvasStore } from '../../store/canvasStore';
import { useSimulationStore, useCurrentStepData } from '../../store/simulationStore';
import {
  createBuildingLayer,
  createPVLayer,
  createBatteryLayer,
  createEVLayer,
  createFeederLayer,
  createTransformerLayer,
  createViolationLayer,
  createVoltageHeatmapLayer,
  createLoadingHeatmapLayer,
  createFlowLayer
} from './MapLayers';
import { TimePlayer } from './TimePlayer';
import { Panel } from '../panels/Panel';
import { LayerTree } from '../panels/LayerTree';
import { AssetInspector } from '../panels/AssetInspector';
import { GridExplorer } from '../panels/GridExplorer';
import { TopBar } from '../panels/TopBar';
import type { Building, PVAsset, BatteryAsset, EVAsset, Feeder, Transformer, GridDiagnostics } from '../../api/types';

interface CommunityCanvasProps {}

export function CommunityCanvas({}: CommunityCanvasProps) {
  const navigate = useNavigate();
  const mapRef = useRef<HTMLDivElement>(null);
  const deckRef = useRef<typeof Deck>(null);

  const {
    viewport,
    setViewport,
    layers: layerVisibility,
    selectedAsset,
    selectAsset,
    mapStyle,
  } = useCanvasStore();

  const {
    trajectories,
    buildingIds,
    currentRun,
    timePlayer,
  } = useSimulationStore();

  const currentStepData = useCurrentStepData();

  const timestepData = useMemo(() => {
    if (!currentStepData) return {};
    const data: Record<string, any> = {};
    Object.entries(currentStepData.observations).forEach(([key, value]) => {
      data[key] = value;
      const match = key.match(/^(building_\d+)_(.+)$/);
      if (!match) return;
      data[match[1]] ??= {};
      data[match[1]][match[2]] = value;
    });
    currentStepData.applied_actions?.forEach(action => {
      const buildingId = action.asset_id.match(/^(building_\d+)/)?.[1];
      if (!buildingId) return;
      const field = action.action_type === 'ev_charge'
        ? 'ev_charge_kw'
        : action.action_type === 'flexible_load'
          ? 'flexible_load_kw'
          : 'battery_power_kw';
      data[buildingId] ??= {};
      data[buildingId][field] = (data[buildingId][field] || 0) + action.value_kw;
      data[action.asset_id] ??= {};
      data[action.asset_id][field] = action.value_kw;
    });
    return data;
  }, [currentStepData]);

  const buildingLocations = useMemo(() => new globalThis.Map(
    buildingIds.map((id, index) => {
      const column = index % 3;
      const row = Math.floor(index / 3);
      return [id, {
        lat: 40.0000 + (1 - row) * 0.00055,
        lon: -105.0000 + (column - 1) * 0.00065,
      }];
    })
  ), [buildingIds]);

  const buildings = useMemo((): Building[] => {
    if (!buildingIds.length || !currentStepData) return [];
    return buildingIds.flatMap((id) => {
      const location = buildingLocations.get(id);
      if (!location) return [];
      const halfSize = 0.00012;
      return [{
        building_id: id,
        name: id.replace('_', ' '),
        location,
        geometry: {
          type: 'Polygon' as const,
          coordinates: [[
            [location.lon - halfSize, location.lat - halfSize],
            [location.lon + halfSize, location.lat - halfSize],
            [location.lon + halfSize, location.lat + halfSize],
            [location.lon - halfSize, location.lat + halfSize],
            [location.lon - halfSize, location.lat - halfSize],
          ]],
        },
      }];
    });
  }, [buildingIds, buildingLocations, currentStepData]);

  const pvAssets = useMemo((): PVAsset[] => {
    return buildings.flatMap((building) => {
      const hasGeneration = trajectories.some((step) =>
        Number(step.observations[`${building.building_id}_solar_generation`] || 0) > 0
      );
      return hasGeneration ? [{
        asset_id: `${building.building_id}_pv`,
        building_id: building.building_id,
        orientation: 180,
        tilt: 30,
      }] : []
    });
  }, [buildings, trajectories]);

  const batteryAssets = useMemo((): BatteryAsset[] => {
    return buildings.flatMap((building) => {
      const hasBatteryActions = trajectories.some((step) =>
        step.applied_actions?.some((action) =>
          action.asset_id === `${building.building_id}_battery`
          && ['battery_charge', 'battery_discharge'].includes(action.action_type)
        )
      );
      return hasBatteryActions ? [{
        asset_id: `${building.building_id}_battery`,
        building_id: building.building_id,
        community: false,
        soc: 0,
        location: building.location,
      }] : []
    });
  }, [buildings, trajectories]);

  const evAssets = useMemo((): EVAsset[] => {
    const evIds = new Set(trajectories.flatMap((step) =>
      (step.applied_actions || [])
        .filter((action) => action.action_type === 'ev_charge')
        .map((action) => action.asset_id)
    ));
    return [...evIds].flatMap((assetId) => {
      const buildingId = assetId.match(/^(building_\d+)_/)?.[1];
      const location = buildingId ? buildingLocations.get(buildingId) : undefined;
      if (!buildingId || !location) return [];
      return [{
        asset_id: assetId,
        building_id: buildingId,
        hub: false,
        soc: 0,
        location,
      }];
    });
  }, [buildingLocations, trajectories]);

  const feeders = useMemo((): Feeder[] => {
    return [{
      feeder_id: 'feeder_1',
      name: 'Feeder 1',
      geometry: {
        type: 'LineString',
        coordinates: buildings.map((building) => [building.location!.lon, building.location!.lat]),
      },
      buses: [],
    }];
  }, [buildings]);

  const transformers = useMemo((): Transformer[] => {
    return [{
      transformer_id: 'trafo_1',
      name: 'Main Transformer',
      lat: 40.0000,
      lon: -105.0000,
      capacity_kva: 630,
      loading_pct: undefined,
    }];
  }, []);

  const gridDiagnostics = useMemo((): GridDiagnostics | undefined => {
    return currentStepData?.grid_diagnostics;
  }, [currentStepData]);

  const violations = useMemo(() => {
    if (!gridDiagnostics) return [];
    const viol: any[] = [];
    const voltageViolations = (gridDiagnostics.violations?.voltage || {}) as Record<string, { value: number; limit: number }>;
    const loadingViolations = (gridDiagnostics.violations?.loading || {}) as Record<string, { value: number; limit: number }>;
    Object.entries(voltageViolations).forEach(([bus, v]) => {
      viol.push({
        type: 'voltage',
        element: bus,
        elementType: 'bus',
        value: v.value,
        limit: v.limit,
        severity: v.value > v.limit * 1.02 ? 'critical' : 'warning',
        location: { lat: 40.0000, lon: -105.0000 },
        timestamp: currentStepData?.timestep || 0,
      });
    });
    Object.entries(loadingViolations).forEach(([el, v]) => {
      viol.push({
        type: 'loading',
        element: el,
        elementType: el.startsWith('line') ? 'line' : 'transformer',
        value: v.value,
        limit: v.limit,
        severity: v.value > v.limit * 1.02 ? 'critical' : 'warning',
        location: { lat: 37.7749, lon: -122.4194 },
        timestamp: currentStepData?.timestep || 0,
      });
    });
    return viol;
  }, [gridDiagnostics, currentStepData]);

  const energyFlows = useMemo(() => {
    if (!currentStepData) return [];
    const flows: any[] = [];

    buildings.forEach(b => {
      const pvGen = currentStepData.observations[`${b.building_id}_solar_generation`] || 0;
      const load = currentStepData.observations[`${b.building_id}_net_electricity_consumption`] || 0;

      if (pvGen > 0) {
        flows.push({
          from: { lat: b.location!.lat, lon: b.location!.lon, type: 'pv', id: `${b.building_id}_pv` },
          to: { lat: b.location!.lat, lon: b.location!.lon, type: 'building', id: b.building_id },
          power_kw: pvGen,
          type: 'generation',
        });
      }

      if (load > 0) {
        flows.push({
          from: { lat: b.location!.lat, lon: b.location!.lon, type: 'building', id: b.building_id },
          to: { lat: 40.0000, lon: -105.0000, type: 'grid', id: 'grid' },
          power_kw: load,
          type: 'consumption',
        });
      }
    });

    batteryAssets.forEach(bat => {
      const power = currentStepData.observations[`${bat.asset_id}_battery_power_kw`] || 0;
      if (Math.abs(power) > 1) {
        flows.push({
          from: { lat: bat.location!.lat, lon: bat.location!.lon, type: 'battery', id: bat.asset_id },
          to: { lat: 40.0000, lon: -105.0000, type: 'grid', id: 'grid' },
          power_kw: Math.abs(power),
          type: power > 0 ? 'storage_charge' : 'storage_discharge',
        });
      }
    });

    evAssets.forEach(ev => {
      const power = currentStepData.observations[`${ev.asset_id}_ev_charge_kw`] || 0;
      if (power > 1) {
        flows.push({
          from: { lat: 40.0000, lon: -105.0000, type: 'grid', id: 'grid' },
          to: { lat: ev.location!.lat, lon: ev.location!.lon, type: 'ev', id: ev.asset_id },
          power_kw: power,
          type: 'ev_charge',
        });
      }
    });

    return flows;
  }, [currentStepData, buildings, batteryAssets, evAssets]);

  const handleViewportChange = useCallback((newViewport: any) => {
    const nextViewport = newViewport.viewState || newViewport;
    setViewport({
      longitude: nextViewport.longitude,
      latitude: nextViewport.latitude,
      zoom: nextViewport.zoom,
      pitch: nextViewport.pitch,
      bearing: nextViewport.bearing,
    });
  }, [setViewport]);

  const mapStyleUrl = mapStyle === 'dark'
    ? 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'
    : mapStyle === 'light'
    ? 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'
    : 'mapbox://styles/mapbox/satellite-streets-v11';

  // Create deck.gl layers
  const deckLayers = useMemo((): (Layer | null)[] => {
    const layers: (Layer | null)[] = [];

    if (layerVisibility.buildings && buildings.length > 0) {
      layers.push(createBuildingLayer({
        buildings,
        timestepData,
        selectedBuildingId: selectedAsset?.type === 'building' ? selectedAsset.id : null,
        onSelect: (id: string) => selectAsset({ type: 'building', id, data: buildings.find(b => b.building_id === id) }),
      }));
    }

    if (layerVisibility.pv && pvAssets.length > 0) {
      layers.push(createPVLayer({
        buildings,
        pvAssets,
        timestepData,
        selectedAssetId: selectedAsset?.type === 'pv' ? selectedAsset.id : null,
        onSelect: (id: string) => selectAsset({ type: 'pv', id, data: pvAssets.find(a => a.asset_id === id) }),
      }));
    }

    if (layerVisibility.batteries && batteryAssets.length > 0) {
      const batteryLayers = createBatteryLayer({
        batteries: batteryAssets,
        timestepData,
        selectedAssetId: selectedAsset?.type === 'battery' ? selectedAsset.id : null,
        onSelect: (id: string) => selectAsset({ type: 'battery', id, data: batteryAssets.find(a => a.asset_id === id) }),
      });
      if (Array.isArray(batteryLayers)) {
        layers.push(...batteryLayers);
      } else if (batteryLayers) {
        layers.push(batteryLayers);
      }
    }

    if (layerVisibility.evs && evAssets.length > 0) {
      layers.push(createEVLayer({
        evs: evAssets,
        timestepData,
        selectedAssetId: selectedAsset?.type === 'ev' ? selectedAsset.id : null,
        onSelect: (id: string) => selectAsset({ type: 'ev', id, data: evAssets.find(a => a.asset_id === id) }),
      }));
    }

    if (layerVisibility.feeders && feeders.length > 0) {
      layers.push(createFeederLayer({
        feeders,
        timestepData,
        selectedFeederId: selectedAsset?.type === 'feeder' ? selectedAsset.id : null,
        onSelect: (id: string) => selectAsset({ type: 'feeder', id, data: feeders.find(f => f.feeder_id === id) }),
        showLoading: layerVisibility.loading_heatmap,
      }));
    }

    if (layerVisibility.transformers && transformers.length > 0) {
      const transformerLayers = createTransformerLayer({
        transformers,
        timestepData,
        selectedTransformerId: selectedAsset?.type === 'transformer' ? selectedAsset.id : null,
        onSelect: (id: string) => selectAsset({ type: 'transformer', id, data: transformers.find(t => t.transformer_id === id) }),
      });
      if (Array.isArray(transformerLayers)) {
        layers.push(...transformerLayers);
      } else if (transformerLayers) {
        layers.push(transformerLayers);
      }
    }

    if (layerVisibility.violations && violations.length > 0) {
      const violationLayers = createViolationLayer({
        violations,
        selectedViolationId: selectedAsset?.type === 'violation' ? selectedAsset.id : null,
        onSelect: (id: string) => selectAsset({ type: 'violation', id, data: violations.find(v => `${v.type}-${v.element}-${v.timestamp}` === id) }),
      });
      if (violationLayers && Array.isArray(violationLayers)) {
        layers.push(...violationLayers);
      } else if (violationLayers) {
        layers.push(violationLayers);
      }
    }

    if (layerVisibility.voltage_heatmap && gridDiagnostics) {
      const voltageLayer = createVoltageHeatmapLayer({
        buses: Object.entries(gridDiagnostics.voltage_profile).map(([bus, voltage], index) => {
          const location = buildings[index % Math.max(buildings.length, 1)]?.location || { lat: 40.0000, lon: -105.0000 };
          return {
            bus_id: bus,
            lat: location.lat,
            lon: location.lon,
            voltage_pu: voltage,
            violation: voltage < 0.95 || voltage > 1.05,
          };
        }),
        showHeatmap: true,
      });
      if (voltageLayer) layers.push(voltageLayer);
    }

    if (layerVisibility.loading_heatmap && gridDiagnostics) {
      const loadingLayer = createLoadingHeatmapLayer({
        elements: [
          ...Object.entries(gridDiagnostics.loading_profile.lines).map(([line, loading], index) => {
            const location = buildings[index % Math.max(buildings.length, 1)]?.location || { lat: 40.0000, lon: -105.0000 };
            return {
              element_id: line,
              lat: location.lat,
              lon: location.lon,
              loading_pct: loading * 100,
              type: 'line' as const,
            };
          }),
          ...Object.entries(gridDiagnostics.loading_profile.trafos).map(([trafo, loading], index) => {
            const location = buildings[index % Math.max(buildings.length, 1)]?.location || { lat: 40.0000, lon: -105.0000 };
            return {
              element_id: trafo,
              lat: location.lat,
              lon: location.lon,
              loading_pct: loading * 100,
              type: 'transformer' as const,
            };
          }),
        ],
        showHeatmap: true,
      });
      if (loadingLayer) layers.push(loadingLayer);
    }

    if (layerVisibility.flows && energyFlows.length > 0) {
      const flowLayers = createFlowLayer({
        flows: energyFlows,
        animationSpeed: timePlayer.playing ? timePlayer.speed : 0,
      });
      if (flowLayers && Array.isArray(flowLayers)) {
        layers.push(...flowLayers);
      } else if (flowLayers) {
        layers.push(flowLayers);
      }
    }

    return layers.filter(Boolean) as Layer[];
  }, [
    layerVisibility,
    buildings,
    pvAssets,
    batteryAssets,
    evAssets,
    feeders,
    transformers,
    violations,
    gridDiagnostics,
    energyFlows,
    timestepData,
    selectedAsset,
    selectAsset,
    timePlayer.playing,
    timePlayer.speed,
  ]);

  return (
    <div className="relative w-full h-full min-h-screen">
      <TopBar
        communityName={currentRun?.scenario_id || 'Virtual Community'}
        scenarioName={currentRun?.scenario_id}
        controllerType={currentRun?.controller_type}
        onScenarioChange={() => navigate('/scenarios')}
        onRunSimulation={() => navigate('/scenarios')}
      />

      <div className="absolute inset-0" ref={mapRef}>
        <Map
          viewState={{
            ...viewport,
            width: mapRef.current?.clientWidth || window.innerWidth,
            height: mapRef.current?.clientHeight || window.innerHeight,
            padding: { top: 0, bottom: 0, left: 0, right: 0 },
          }}
          onMove={(event) => handleViewportChange(event.viewState)}
          mapStyle={mapStyleUrl}
          attributionControl={false}
        />

        <Deck
          ref={deckRef as any}
          viewState={viewport}
          controller={false}
          layers={deckLayers}
        />
      </div>

      <Panel position="left" className="w-72 max-h-full overflow-hidden" defaultOpen={window.innerWidth >= 768}>
        <LayerTree
          layers={layerVisibility}
          onToggle={(layer) => useCanvasStore.getState().toggleLayer(layer)}
        />
      </Panel>

      <Panel position="right" className="w-80 max-h-full overflow-hidden" defaultOpen={window.innerWidth >= 768}>
        {selectedAsset && (
          <>
            {['building', 'pv', 'battery', 'ev', 'flexible_load'].includes(selectedAsset.type) && (
              <AssetInspector asset={selectedAsset} timestepData={timestepData} trajectories={trajectories} />
            )}
            {['feeder', 'transformer', 'bus'].includes(selectedAsset.type) && (
              <GridExplorer asset={selectedAsset} gridDiagnostics={gridDiagnostics} trajectories={trajectories} />
            )}
          </>
        )}
      </Panel>

      <TimePlayer />
    </div>
  );
}