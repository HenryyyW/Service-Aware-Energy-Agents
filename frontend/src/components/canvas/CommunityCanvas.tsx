import { useRef, useMemo, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import MapGL, { Marker } from 'react-map-gl/maplibre';
import { Building2 } from 'lucide-react';
import Deck from '@deck.gl/react';
import { Layer } from '@deck.gl/core';
import { useCanvasStore } from '../../store/canvasStore';
import { useSimulationStore, useCurrentStepData } from '../../store/simulationStore';
import { useScenarioStore } from '../../store/scenarioStore';
import { api } from '../../api/client';
import { toDisplayNetworkGeometry } from '../../api/networkGeometry';
import { WebMercatorViewport } from '@deck.gl/core';
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
  createFlowLayer,
  createLMPLayer
} from './MapLayers';
import { TimePlayer } from './TimePlayer';
import { Panel } from '../panels/Panel';
import { LayerTree } from '../panels/LayerTree';
import { AssetInspector } from '../panels/AssetInspector';
import { GridExplorer } from '../panels/GridExplorer';
import { TopBar } from '../panels/TopBar';
import type { Building, PVAsset, BatteryAsset, EVAsset, Feeder, Transformer, GridDiagnostics, NetworkBus, PVAssetMetadata, BatteryAssetMetadata, EVAssetMetadata } from '../../api/types';

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
    networkGeometry: sourceNetworkGeometry,
    fetchNetworkGeometry,
    fetchAssetMetadata,
    assetMetadata,
  } = useCanvasStore();

  const {
    trajectories,
    buildingIds,
    currentRun,
    timePlayer,
  } = useSimulationStore();

  const { currentScenario, setCurrentScenario } = useScenarioStore();

  const communityAnchor = useMemo(() => {
    const locations = currentScenario?.buildings
      ?.map((building: any) => building.location)
      .filter((location: any) => Number.isFinite(location?.lat) && Number.isFinite(location?.lon));
    if (!locations?.length) return { latitude: 40, longitude: -105 };
    return {
      latitude: locations.reduce((sum: number, location: any) => sum + location.lat, 0) / locations.length,
      longitude: locations.reduce((sum: number, location: any) => sum + location.lon, 0) / locations.length,
    };
  }, [currentScenario]);

  const networkGeometry = useMemo(
    () => toDisplayNetworkGeometry(sourceNetworkGeometry, communityAnchor),
    [sourceNetworkGeometry, communityAnchor],
  );

  const currentStepData = useCurrentStepData();

  // Fetch network geometry on mount
  useEffect(() => {
    if (currentRun?.scenario_id) {
      fetchNetworkGeometry(currentRun.scenario_id);
    }
  }, [fetchNetworkGeometry, currentRun?.scenario_id]);

  // Fetch asset metadata when scenario changes
  useEffect(() => {
    if (currentRun?.scenario_id) {
      fetchAssetMetadata(currentRun.scenario_id);
    }
  }, [fetchAssetMetadata, currentRun?.scenario_id]);

  useEffect(() => {
    if (!currentRun?.scenario_id) return;
    let active = true;
    api.getScenario(currentRun.scenario_id).then((scenario) => {
      if (active) setCurrentScenario(scenario);
    }).catch((error) => {
      if (active) {
        setCurrentScenario(null);
        console.error('Failed to load network bus mappings:', error);
      }
    });
    return () => { active = false; };
  }, [currentRun?.scenario_id, setCurrentScenario]);

  useEffect(() => {
    const bounds = networkGeometry?.bounds;
    if (!bounds) return;
    const fitted = new WebMercatorViewport({ width: window.innerWidth, height: window.innerHeight }).fitBounds([
      [bounds.min_lon, bounds.min_lat],
      [bounds.max_lon, bounds.max_lat],
    ], {
      padding: { left: Math.min(300, window.innerWidth * 0.28), right: Math.min(340, window.innerWidth * 0.31), top: 110, bottom: 190 },
      maxZoom: 18,
    });
    setViewport({ longitude: fitted.longitude, latitude: fitted.latitude, zoom: fitted.zoom, pitch: 0, bearing: 0 });
  }, [networkGeometry, setViewport]);

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

  // Extract LMP prices from current step data (Phase 2)
  // Backend returns LMP prices in observations as {building_id}_electricity_pricing
  const lmpPrices = useMemo((): Record<string, number> => {
    if (!currentStepData?.observations) return {};
    const prices: Record<string, number> = {};
    Object.entries(currentStepData.observations).forEach(([key, value]) => {
      const match = key.match(/^(building_\d+)_electricity_pricing$/);
      if (match && typeof value === 'number') {
        prices[match[1]] = value;
      }
    });
    return prices;
  }, [currentStepData]);

  // Map building IDs to their corresponding bus indices from the scenario config
  const buildingBusMapping = useMemo(() => {
    if (!currentScenario?.pandapower?.bus_mappings) return new Map<string, number>();
    const mapping = new Map<string, number>();
    currentScenario.pandapower.bus_mappings.forEach((m: any) => {
      mapping.set(m.building_id, m.bus_idx);
    });
    return mapping;
  }, [currentScenario]);

  // Get building locations from real network geometry
  const buildingLocations = useMemo(() => {
    const locations = new Map<string, { lat: number; lon: number }>();
    buildingIds.forEach((id) => {
      const busIdx = buildingBusMapping.get(id);
      if (busIdx === undefined || !networkGeometry) return;
      
      // Find the bus by bus_idx in the network geometry
      const busEntry = Object.values(networkGeometry.buses).find((bus: NetworkBus) => bus.bus_idx === busIdx);
      if (busEntry) {
        locations.set(id, { lat: busEntry.lat, lon: busEntry.lon });
      }
    });
    return locations;
  }, [buildingIds, buildingBusMapping, networkGeometry]);

  const buildings = useMemo((): Building[] => {
    if (!buildingIds.length || !currentStepData) return [];
    return buildingIds.flatMap((id) => {
      const location = buildingLocations.get(id);
      if (!location) return [];
      // Scale the building size based on the coordinate system
      // The network geometry coordinates are in a different scale (0-22 range)
      const halfSize = 0.00003;
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

  // Use asset metadata from API for PV assets
  const pvAssets = useMemo((): PVAsset[] => {
    if (!assetMetadata?.pv) return [];
    return assetMetadata.pv.map((pv: PVAssetMetadata) => ({
      asset_id: pv.asset_id,
      building_id: pv.building_id,
      orientation: pv.orientation,
      tilt: pv.tilt,
      location: pv.location,
    }));
  }, [assetMetadata]);

  // Use asset metadata from API for battery assets
  const batteryAssets = useMemo((): BatteryAsset[] => {
    if (!assetMetadata?.batteries) return [];
    return assetMetadata.batteries.map((battery: BatteryAssetMetadata) => ({
      asset_id: battery.asset_id,
      building_id: battery.building_id,
      community: false,
      soc: 0,
      location: battery.location,
    }));
  }, [assetMetadata]);

  // Use asset metadata from API for EV assets
  const evAssets = useMemo((): EVAsset[] => {
    if (!assetMetadata?.evs) return [];
    return assetMetadata.evs.map((ev: EVAssetMetadata) => ({
      asset_id: ev.asset_id,
      building_id: ev.building_id,
      hub: false,
      soc: 0,
      location: ev.location,
    }));
  }, [assetMetadata]);

  // Create feeders from real network line geometries
  const feeders = useMemo((): Feeder[] => {
    if (!networkGeometry) return [];
    
    return networkGeometry.lines.map((line) => {
      const fromBus = networkGeometry.buses[line.from_bus];
      const toBus = networkGeometry.buses[line.to_bus];
      return {
        feeder_id: `line_${line.line_id}`,
        name: line.name,
        geometry: {
          type: 'LineString' as const,
          coordinates: line.coordinates,
        },
        buses: [
          fromBus ? { bus_id: fromBus.name, name: fromBus.name, lat: fromBus.lat, lon: fromBus.lon } : { bus_id: line.from_bus, name: line.from_bus, lat: 0, lon: 0 },
          toBus ? { bus_id: toBus.name, name: toBus.name, lat: toBus.lat, lon: toBus.lon } : { bus_id: line.to_bus, name: line.to_bus, lat: 0, lon: 0 },
        ],
      };
    });
  }, [networkGeometry]);

  // Create transformers from real network transformer data
  const transformers = useMemo((): Transformer[] => {
    if (!networkGeometry) return [];
    
    return networkGeometry.transformers.map((trafo) => ({
      transformer_id: `trafo_${trafo.transformer_id}`,
      name: trafo.name,
      lat: trafo.lat,
      lon: trafo.lon,
      capacity_kva: trafo.capacity_mva * 1000,
      loading_pct: undefined,
    }));
  }, [networkGeometry]);

  const gridDiagnostics = useMemo((): GridDiagnostics | undefined => {
    return currentStepData?.grid_diagnostics;
  }, [currentStepData]);

  const violations = useMemo(() => {
    if (!gridDiagnostics || !networkGeometry) return [];
    const viol: any[] = [];
    const voltageViolations = (gridDiagnostics.violations?.voltage || {}) as Record<string, { value: number; limit: number }>;
    const loadingViolations = (gridDiagnostics.violations?.loading || {}) as Record<string, { value: number; limit: number }>;
    
    Object.entries(voltageViolations).forEach(([bus, v]) => {
      // Find the bus location from network geometry
      const busEntry = Object.values(networkGeometry.buses).find((b: NetworkBus) => b.name === bus);
      const location = busEntry ? { lat: busEntry.lat, lon: busEntry.lon } : { lat: 0, lon: 0 };
      
      viol.push({
        type: 'voltage',
        element: bus,
        elementType: 'bus',
        value: v.value,
        limit: v.limit,
        severity: v.value > v.limit * 1.02 ? 'critical' : 'warning',
        location,
        timestamp: currentStepData?.timestep || 0,
      });
    });
    Object.entries(loadingViolations).forEach(([el, v]) => {
      // Try to find location for lines and transformers
      let location = { lat: 0, lon: 0 };
      const lineEntry = networkGeometry.lines.find((l) => l.name === el);
      const trafoEntry = networkGeometry.transformers.find((t) => t.name === el);
      
      if (lineEntry && lineEntry.coordinates.length > 0) {
        // Use midpoint of line
        const midIdx = Math.floor(lineEntry.coordinates.length / 2);
        location = { lat: lineEntry.coordinates[midIdx][1], lon: lineEntry.coordinates[midIdx][0] };
      } else if (trafoEntry) {
        location = { lat: trafoEntry.lat, lon: trafoEntry.lon };
      }
      
      viol.push({
        type: 'loading',
        element: el,
        elementType: el.startsWith('line') ? 'line' : 'transformer',
        value: v.value,
        limit: v.limit,
        severity: v.value > v.limit * 1.02 ? 'critical' : 'warning',
        location,
        timestamp: currentStepData?.timestep || 0,
      });
    });
    return viol;
  }, [gridDiagnostics, currentStepData, networkGeometry]);

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
        // Find the substation/transformer as grid connection point
        const gridConnection = networkGeometry?.transformers[0] 
          ? { lat: networkGeometry.transformers[0].lat, lon: networkGeometry.transformers[0].lon }
          : { lat: 0, lon: 0 };
        
        flows.push({
          from: { lat: b.location!.lat, lon: b.location!.lon, type: 'building', id: b.building_id },
          to: { lat: gridConnection.lat, lon: gridConnection.lon, type: 'grid', id: 'grid' },
          power_kw: load,
          type: 'consumption',
        });
      }
    });

    batteryAssets.forEach(bat => {
      const power = currentStepData.observations[`${bat.asset_id}_battery_power_kw`] || 0;
      if (Math.abs(power) > 1) {
        const gridConnection = networkGeometry?.transformers[0] 
          ? { lat: networkGeometry.transformers[0].lat, lon: networkGeometry.transformers[0].lon }
          : { lat: 0, lon: 0 };
          
        flows.push({
          from: { lat: bat.location!.lat, lon: bat.location!.lon, type: 'battery', id: bat.asset_id },
          to: { lat: gridConnection.lat, lon: gridConnection.lon, type: 'grid', id: 'grid' },
          power_kw: Math.abs(power),
          type: power > 0 ? 'storage_charge' : 'storage_discharge',
        });
      }
    });

    evAssets.forEach(ev => {
      const power = currentStepData.observations[`${ev.asset_id}_ev_charge_kw`] || 0;
      if (power > 1) {
        const gridConnection = networkGeometry?.transformers[0] 
          ? { lat: networkGeometry.transformers[0].lat, lon: networkGeometry.transformers[0].lon }
          : { lat: 0, lon: 0 };
          
        flows.push({
          from: { lat: gridConnection.lat, lon: gridConnection.lon, type: 'grid', id: 'grid' },
          to: { lat: ev.location!.lat, lon: ev.location!.lon, type: 'ev', id: ev.asset_id },
          power_kw: power,
          type: 'ev_charge',
        });
      }
    });

    return flows;
  }, [currentStepData, buildings, batteryAssets, evAssets, networkGeometry]);

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

    if (layerVisibility.voltage_heatmap && gridDiagnostics && networkGeometry) {
      const voltageLayer = createVoltageHeatmapLayer({
        buses: Object.entries(gridDiagnostics.voltage_profile).map(([bus, voltage]) => {
          const busEntry = Object.values(networkGeometry.buses).find((b: NetworkBus) => b.name === bus);
          const location = busEntry ? { lat: busEntry.lat, lon: busEntry.lon } : { lat: 0, lon: 0 };
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

    if (layerVisibility.loading_heatmap && gridDiagnostics && networkGeometry) {
      const loadingLayer = createLoadingHeatmapLayer({
        elements: [
          ...Object.entries(gridDiagnostics.loading_profile.lines).map(([line, loading]) => {
            const lineEntry = networkGeometry.lines.find((l) => l.name === line);
            let location = { lat: 0, lon: 0 };
            if (lineEntry && lineEntry.coordinates.length > 0) {
              const midIdx = Math.floor(lineEntry.coordinates.length / 2);
              location = { lat: lineEntry.coordinates[midIdx][1], lon: lineEntry.coordinates[midIdx][0] };
            }
            return {
              element_id: line,
              lat: location.lat,
              lon: location.lon,
              loading_pct: loading * 100,
              type: 'line' as const,
            };
          }),
          ...Object.entries(gridDiagnostics.loading_profile.trafos).map(([trafo, loading]) => {
            const trafoEntry = networkGeometry.transformers.find((t) => t.name === trafo);
            const location = trafoEntry ? { lat: trafoEntry.lat, lon: trafoEntry.lon } : { lat: 0, lon: 0 };
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

    // LMP Prices layer (Phase 2)
    if (layerVisibility.lmp_prices && buildings.length > 0 && Object.keys(lmpPrices).length > 0) {
      const lmpLayer = createLMPLayer({
        buildings,
        lmpPrices,
        timestepData,
        selectedBuildingId: selectedAsset?.type === 'building' ? selectedAsset.id : null,
        onSelect: (id: string) => selectAsset({ type: 'building', id, data: buildings.find(b => b.building_id === id) }),
      });
      if (lmpLayer) layers.push(lmpLayer);
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
    networkGeometry,
    lmpPrices,
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
        {sourceNetworkGeometry?.coordinate_system === 'schematic' && (
          <div className="pointer-events-none absolute left-1/2 top-20 z-10 -translate-x-1/2 rounded border border-white/20 bg-black/70 px-3 py-1.5 text-xs text-white">
            Schematic network layout
          </div>
        )}
        <MapGL
          viewState={{
            ...viewport,
            width: mapRef.current?.clientWidth || window.innerWidth,
            height: mapRef.current?.clientHeight || window.innerHeight,
            padding: { top: 0, bottom: 0, left: 0, right: 0 },
          }}
          onMove={(event) => handleViewportChange(event.viewState)}
          mapStyle={mapStyleUrl}
          attributionControl={false}
        >
          {layerVisibility.buildings && buildings.map((building) => building.location && (
            <Marker key={building.building_id} longitude={building.location.lon} latitude={building.location.lat} style={{ zIndex: 5 }}>
              <button
                type="button"
                aria-label={`Select ${building.building_id}`}
                title={building.building_id}
                className="flex h-7 w-7 items-center justify-center rounded border-2 border-white bg-emerald-600 text-white shadow"
                onClick={() => selectAsset({ type: 'building', id: building.building_id, data: building })}
              >
                <Building2 size={16} />
              </button>
            </Marker>
          ))}
        </MapGL>

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
