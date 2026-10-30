import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ScenarioConfig, SimulationRun } from '../api/types';

interface ScenarioState {
  // Current scenario being edited
  currentScenario: ScenarioConfig | null;
  setCurrentScenario: (scenario: ScenarioConfig | null) => void;
  updateScenarioField: (path: string, value: any) => void;

  // Saved scenarios
  scenarios: ScenarioConfig[];
  setScenarios: (scenarios: ScenarioConfig[]) => void;
  addScenario: (scenario: ScenarioConfig) => void;
  updateScenario: (id: string, scenario: Partial<ScenarioConfig>) => void;
  deleteScenario: (id: string) => void;

  // Comparison
  comparisonRunA: SimulationRun | null;
  comparisonRunB: SimulationRun | null;
  setComparisonRunA: (run: SimulationRun | null) => void;
  setComparisonRunB: (run: SimulationRun | null) => void;
  clearComparison: () => void;

  // Scenario form state (for builder)
  formValues: Record<string, any>;
  setFormValue: (key: string, value: any) => void;
  resetForm: () => void;
}

const DEFAULT_SCENARIO: ScenarioConfig = {
  community: {
    name: 'New Community',
    buildings: 5,
    simulation_period: '7_days',
    timestep_minutes: 15,
  },
  assets: {
    pv: {
      penetration: 0.4,
      orientation: 'rooftop',
    },
    batteries: {
      community_capacity_kwh: 800,
      max_power_kw: 250,
    },
    evs: {
      number: 35,
      charging_power_kw: [7, 22, 60],
      departure_soc_requirement: 0.8,
    },
    flexible_loads: {
      share: 0.15,
    },
  },
  grid: {
    model: 'simbench_lv_grid_1',
    transformer_capacity_kva: 630,
    voltage_limits_pu: [0.95, 1.05],
    import_limit_kw: 500,
    export_limit_kw: 200,
  },
  control: {
    strategy: 'rule_based',
    objective: [
      'minimize_cost',
      'minimize_peak',
      'maximize_renewable_self_consumption',
      'preserve_ev_service',
      'preserve_comfort',
    ],
  },
  energy_sharing: {
    enabled: false,
    market_type: 'uniform_price',
    settlement_interval: '1h',
    dynamic_pricing: {
      enabled: false,
      pricing_type: 'lmp',
      lmp_update_interval_minutes: 60,
      congestion_cost_method: 'dc_approx',
      loss_factor: 1.0,
      price_cap_per_kwh: 1.0,
      fallback_to_tariff: true,
    },
  },
};

function setNestedValue(obj: any, path: string, value: any) {
  const keys = path.split('.');
  let current = obj;
  for (let i = 0; i < keys.length - 1; i++) {
    if (!(keys[i] in current)) {
      current[keys[i]] = {};
    }
    current = current[keys[i]];
  }
  current[keys[keys.length - 1]] = value;
}

export const useScenarioStore = create<ScenarioState>()(
  persist(
    (set) => ({
      currentScenario: { ...DEFAULT_SCENARIO },
      setCurrentScenario: (scenario) => set({ currentScenario: scenario }),
      updateScenarioField: (path, value) => set((state) => {
        const newScenario = state.currentScenario ? JSON.parse(JSON.stringify(state.currentScenario)) : { ...DEFAULT_SCENARIO };
        setNestedValue(newScenario, path, value);
        return { currentScenario: newScenario };
      }),

      scenarios: [],
      setScenarios: (scenarios) => set({ scenarios }),
      addScenario: (scenario) => set((state) => ({ scenarios: [...state.scenarios, scenario] })),
      updateScenario: (id, scenario) => set((state) => ({
        scenarios: state.scenarios.map(s => s.community.name === id ? { ...s, ...scenario } : s),
      })),
      deleteScenario: (id) => set((state) => ({
        scenarios: state.scenarios.filter(s => s.community.name !== id),
      })),

      comparisonRunA: null,
      comparisonRunB: null,
      setComparisonRunA: (run) => set({ comparisonRunA: run }),
      setComparisonRunB: (run) => set({ comparisonRunB: run }),
      clearComparison: () => set({ comparisonRunA: null, comparisonRunB: null }),

      formValues: {},
      setFormValue: (key, value) => set((state) => ({ formValues: { ...state.formValues, [key]: value } })),
      resetForm: () => set({ formValues: {} }),
    }),
    {
      name: 'scenario-store',
      partialize: (state) => ({
        scenarios: state.scenarios,
      }),
    }
  )
);