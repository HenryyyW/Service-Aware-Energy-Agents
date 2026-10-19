// Shared TypeScript types for the frontend

export interface Building {
  building_id: string;
  name?: string;
  location?: {
    lat: number;
    lon: number;
  };
  geometry?: GeoJSON.Polygon;
  pv_capacity_kw?: number;
  battery_capacity_kwh?: number;
  battery_power_kw?: number;
  ev_capacity_kwh?: number;
  ev_charger_power_kw?: number;
  flexible_load_kw?: number;
}

export interface PVAsset {
  asset_id: string;
  building_id: string;
  capacity_kw?: number;
  orientation?: number;
  tilt?: number;
}

export interface BatteryAsset {
  asset_id: string;
  building_id?: string;
  community?: boolean;
  capacity_kwh?: number;
  power_kw?: number;
  soc: number;
  location?: { lat: number; lon: number };
}

export interface EVAsset {
  asset_id: string;
  building_id?: string;
  hub?: boolean;
  capacity_kwh?: number;
  charger_power_kw?: number;
  soc: number;
  departure_time?: number;
  target_soc?: number;
  location?: { lat: number; lon: number };
}

export interface FlexibleLoadAsset {
  asset_id: string;
  building_id: string;
  power_kw: number;
  deadline: number;
  status: 'pending' | 'shifted' | 'completed' | 'delayed' | 'failed';
}

export interface Feeder {
  feeder_id: string;
  name: string;
  geometry: GeoJSON.LineString;
  buses: Bus[];
}

export interface Bus {
  bus_id: string;
  name: string;
  lat: number;
  lon: number;
  voltage_pu?: number;
  violation?: boolean;
}

export interface Transformer {
  transformer_id: string;
  name: string;
  lat: number;
  lon: number;
  capacity_kva: number;
  loading_pct?: number;
  violation?: boolean;
}

export interface GridDiagnostics {
  power_flow_converged: boolean;
  voltage_profile: Record<string, number>;
  loading_profile: {
    lines: Record<string, number>;
    trafos: Record<string, number>;
  };
  violations?: {
    voltage?: Array<{ bus: string; value: number; limit: number }> | Record<string, { value: number; limit: number }>;
    loading?: Array<{ element: string; value: number; limit: number }> | Record<string, { value: number; limit: number }>;
  };
}

export interface TimeStepData {
  timestep: number;
  timestamp: string;
  observations: Record<string, number>;
  applied_actions: AppliedAction[];
  costs: Record<string, number>;
  grid_diagnostics?: GridDiagnostics;
}

export interface AppliedAction {
  asset_id: string;
  action_type: 'battery_charge' | 'battery_discharge' | 'ev_charge' | 'flexible_load';
  value_kw: number;
  requested_kw?: number;
  limited_kw?: number;
}

export interface ScenarioConfig {
  community: {
    name: string;
    buildings: number;
    simulation_period: string;
    timestep_minutes: number;
  };
  assets: {
    pv: {
      penetration: number;
      orientation: string;
    };
    batteries: {
      community_capacity_kwh: number;
      max_power_kw: number;
    };
    evs: {
      number: number;
      charging_power_kw: number[];
      departure_soc_requirement: number;
    };
    flexible_loads: {
      share: number;
    };
  };
  grid: {
    model: string;
    transformer_capacity_kva: number;
    voltage_limits_pu: [number, number];
    import_limit_kw: number;
    export_limit_kw: number;
  };
  control: {
    strategy: string;
    objective: string[];
  };
}

export interface SimulationRun {
  run_id: string;
  scenario_id: string;
  controller_type: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  start_time: string;
  end_time?: string;
  energy_metrics?: EnergyMetrics;
  service_metrics?: ServiceMetrics;
  grid_metrics?: GridMetrics;
  random_seed?: number;
}

export interface EnergyMetrics {
  total_cost: number;
  grid_import_kwh: number;
  grid_export_kwh: number;
  peak_demand_kw: number;
  pv_self_consumption: number;
  pv_generation_kwh?: number;
  pv_curtailment: number;
  battery_throughput_kwh: number;
  carbon_emissions_kg: number;
}

export interface ServiceMetrics {
  ev_completion_rate: number;
  avg_ev_soc_at_departure: number;
  comfort_violation_degree_hours: number;
  flexible_load_completion_rate: number;
  dr_delivery_rate: number;
  gini_coefficient: number;
  worst_member_savings: number;
}

export interface GridMetrics {
  power_flow_convergence_rate: number;
  voltage_violations_count: number;
  max_voltage_pu: number;
  min_voltage_pu: number;
  max_line_loading_pct: number;
  max_transformer_loading_pct: number;
}

export interface AgentTask {
  task_id: string;
  description: string;
  status: 'planning' | 'coding' | 'executing' | 'verifying' | 'repairing' | 'reporting' | 'completed' | 'failed';
  created_at: string;
  updated_at: string;
  plan?: AgentPlan;
  code?: string;
  execution_log?: string[];
  verification?: VerificationResult;
  repairs?: RepairPatch[];
  report?: string;
}

export interface AgentPlan {
  assets: string[];
  constraints: string[];
  kpis: string[];
  simulations_needed: number;
  estimated_duration_seconds: number;
}

export interface VerificationResult {
  passed: boolean;
  diagnostics: {
    physical: string[];
    electrical: string[];
    service: string[];
    reporting: string[];
  };
  violations: Array<{ type: string; message: string; severity: 'error' | 'warning' }>;
}

export interface RepairPatch {
  file: string;
  description: string;
  diff: string;
}

export interface WebSocketMessage {
  type: 'simulation_update' | 'simulation_complete' | 'simulation_error' | 'agent_update' | 'agent_complete';
  payload: any;
}

export interface TimePlayerState {
  currentTimestep: number;
  minTimestep: number;
  maxTimestep: number;
  playing: boolean;
  speed: 1 | 2 | 4;
  totalTimesteps: number;
}

export interface MapViewport {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
}

export interface SelectedAsset {
  type: 'building' | 'pv' | 'battery' | 'ev' | 'flexible_load' | 'feeder' | 'transformer' | 'bus' | 'violation';
  id: string;
  data: any;
}

export interface LayerVisibility {
  buildings: boolean;
  pv: boolean;
  batteries: boolean;
  evs: boolean;
  flexible_loads: boolean;
  feeders: boolean;
  transformers: boolean;
  violations: boolean;
  flows: boolean;
  voltage_heatmap: boolean;
  loading_heatmap: boolean;
}