import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import Scenarios from '@/pages/Scenarios'
import { api } from '@/api/client'
import { useScenarioStore } from '@/store/scenarioStore'
import { useNavigate } from 'react-router-dom'
import type { ScenarioConfig } from '@/api/types'

// Mock react-router-dom so Scenarios can render without a Router, while the
// `navigate` call from "Run Experiment" is captured for assertion.
vi.mock('react-router-dom', async (importActual) => {
  const actual = await importActual<typeof import('react-router-dom')>()
  return {
    ...actual,
    useNavigate: vi.fn(() => vi.fn()),
  }
})

vi.mock('../api/client', () => ({
  api: {
    getScenarios: vi.fn(),
    getScenario: vi.fn(),
    createScenario: vi.fn(),
    updateScenario: vi.fn(),
    deleteScenario: vi.fn(),
  },
  wsManager: {},
}))

const mockApi = vi.mocked(api)

const scenarios: ScenarioConfig[] = [
  {
    scenario_id: 'scenario_a',
    name: 'Scenario A',
    description: 'Base residential community',
    community: {
      name: 'Scenario A',
      buildings: 5,
      simulation_period: '7_days',
      timestep_minutes: 15,
    },
    assets: {
      pv: { penetration: 0.4, orientation: 'rooftop' },
      batteries: { community_capacity_kwh: 800, max_power_kw: 250 },
      evs: { number: 5, charging_power_kw: [7], departure_soc_requirement: 0.8 },
      flexible_loads: { share: 0.1 },
    },
    grid: {
      model: 'simbench_lv_grid_1',
      transformer_capacity_kva: 630,
      voltage_limits_pu: [0.95, 1.05],
      import_limit_kw: 200,
      export_limit_kw: 100,
    },
    control: { strategy: 'rule_based', objective: ['minimize_cost'] },
  },
  {
    scenario_id: 'scenario_b',
    name: 'Scenario B',
    description: 'Mixed commercial/residential',
    community: {
      name: 'Scenario B',
      buildings: 8,
      simulation_period: '7_days',
      timestep_minutes: 15,
    },
    assets: {
      pv: { penetration: 0.4, orientation: 'rooftop' },
      batteries: { community_capacity_kwh: 800, max_power_kw: 250 },
      evs: { number: 10, charging_power_kw: [7, 22], departure_soc_requirement: 0.8 },
      flexible_loads: { share: 0.15 },
    },
    grid: {
      model: 'simbench_lv_grid_1',
      transformer_capacity_kva: 630,
      voltage_limits_pu: [0.95, 1.05],
      import_limit_kw: 300,
      export_limit_kw: 150,
    },
    control: { strategy: 'multi_agent', objective: ['minimize_cost'] },
  },
]

const navigateCalls = () =>
  vi.mocked(useNavigate).mock.results.flatMap(
    (r) => (r.value as ReturnType<typeof vi.fn>).mock.calls,
  )

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  sessionStorage.clear()
})

describe('Scenarios page', () => {
  it('fetches api.getScenarios and lists every scenario id', async () => {
    mockApi.getScenarios.mockResolvedValue(scenarios)
    render(<Scenarios />)
    await screen.findByText(scenarios[0].scenario_id as string)
    await screen.findByText(scenarios[1].scenario_id as string)
    expect(mockApi.getScenarios).toHaveBeenCalledTimes(1)
  })

  it('selecting a row then Run Experiment writes currentScenario and lands on /studio', async () => {
    mockApi.getScenarios.mockResolvedValue(scenarios)
    render(<Scenarios />)

    await screen.findByText(scenarios[0].scenario_id as string)

    // Select the first row via its View button.
    const viewButtons = screen.getAllByTitle('View')
    fireEvent.click(viewButtons[0])

    // Run Experiment in the opened modal.
    const runBtn = await screen.findByRole('button', { name: /run experiment/i })
    fireEvent.click(runBtn)

    expect(useScenarioStore.getState().currentScenario).toEqual(scenarios[0])
    expect(navigateCalls()).toContainEqual(['/studio'])
  })
})
