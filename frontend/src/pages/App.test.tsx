import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from '@/App'
import { api } from '@/api/client'
import { useScenarioStore } from '@/store/scenarioStore'
import { useAgentStore } from '@/store/agentStore'
import { useSimulationStore } from '@/store/simulationStore'
import type { ScenarioConfig, AgentTask } from '@/api/types'

vi.mock('../api/client', () => ({
  api: {
    getScenarios: vi.fn(),
    getScenario: vi.fn(),
    getRun: vi.fn(),
    getRuns: vi.fn(),
    getReport: vi.fn(),
    getAgentTasks: vi.fn(),
    runSimulation: vi.fn(),
    createScenario: vi.fn(),
    updateScenario: vi.fn(),
    deleteScenario: vi.fn(),
    getNetworkGeometry: vi.fn(),
    getAssetMetadata: vi.fn(),
    getTrajectories: vi.fn(),
    getGridDiagnostics: vi.fn(),
    createAgentTask: vi.fn(),
    getAgentTask: vi.fn(),
    downloadReport: vi.fn(),
    compareRuns: vi.fn(),
  },
  wsManager: {},
}))

const mockApi = vi.mocked(api)

const testScenario: ScenarioConfig = {
  scenario_id: 'scenario_test',
  name: 'Test Community',
  description: 'A test scenario',
  community: {
    name: 'Test Community',
    buildings: 3,
    simulation_period: '7_days',
    timestep_minutes: 15,
  },
  assets: {
    pv: { penetration: 0.4, orientation: 'rooftop' },
    batteries: { community_capacity_kwh: 800, max_power_kw: 250 },
    evs: { number: 10, charging_power_kw: [7, 22], departure_soc_requirement: 0.8 },
    flexible_loads: { share: 0.1 },
  },
  grid: {
    model: 'simbench_lv_grid_1',
    transformer_capacity_kva: 630,
    voltage_limits_pu: [0.95, 1.05],
    import_limit_kw: 500,
    export_limit_kw: 200,
  },
  control: { strategy: 'rule_based', objective: ['minimize_cost'] },
}

const testTask: AgentTask = {
  task_id: 'task_1',
  description: 'Test agent task',
  status: 'executing',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  sessionStorage.clear()
  useScenarioStore.getState().setCurrentScenario(testScenario)
  useAgentStore.getState().setCurrentTask(null)
  useSimulationStore.getState().setRuns([])
  useSimulationStore.getState().setCurrentRun(null)
})

const renderApp = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>
  )

describe('frontend routes', () => {
  it('/studio renders ScenarioEditor', () => {
    mockApi.getScenarios.mockResolvedValue([])
    renderApp('/studio')
    expect(screen.getByRole('tab', { name: 'Scenario Editor' })).toBeInTheDocument()
    expect(screen.getByText('Test Community')).toBeInTheDocument()
  })

  it('/workspace renders the timeline side', () => {
    mockApi.getAgentTasks.mockResolvedValue([])
    mockApi.getRuns.mockResolvedValue([])
    useAgentStore.getState().setCurrentTask(testTask)
    renderApp('/workspace')
    expect(screen.getByText('Agent Workflow')).toBeInTheDocument()
  })

  it('/runs/:runId/report renders ReportView', async () => {
    mockApi.getReport.mockResolvedValue({
      run_id: 'run_123',
      scenario_id: 'scenario_test',
      controller_type: 'rule_based',
      status: 'completed',
      generation_status: 'ready',
      markdown: '# Report',
      kpi_blocks: {},
      detail_sections: {},
      start_time: new Date().toISOString(),
    })
    renderApp('/runs/run_123/report')
    expect(await screen.findByText('Simulation Report')).toBeInTheDocument()
  })
})
