import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ReportPage } from './ReportPage'
import { api } from '@/api/client'
import { useSimulationStore } from '@/store/simulationStore'
import { useAgentStore } from '@/store/agentStore'

vi.mock('../api/client', () => ({
  api: {
    getReport: vi.fn(),
    getSimulationRun: vi.fn(),
    getScenarios: vi.fn(),
    getScenario: vi.fn(),
    getRun: vi.fn(),
    getRuns: vi.fn(),
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

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  sessionStorage.clear()
  useSimulationStore.getState().setRuns([])
  useSimulationStore.getState().setCurrentRun(null)
  useAgentStore.getState().setCurrentTask(null)
})

const renderReport = (runId: string) =>
  render(
    <MemoryRouter initialEntries={[`/runs/${runId}/report`]}>
      <Routes>
        <Route path="/runs/:runId/report" element={<ReportPage />} />
      </Routes>
    </MemoryRouter>
  )

describe('ReportPage effective timestep', () => {
  it('shows "Unknown effective timestep" when effective_timestep_minutes is undefined', async () => {
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
    mockApi.getSimulationRun.mockResolvedValue({
      run_id: 'run_123',
      scenario_id: 'scenario_test',
      scenario_config: {},
      controller_type: 'rule_based',
      status: 'completed',
      start_time: new Date().toISOString(),
    })

    renderReport('run_123')
    expect(await screen.findByText('Unknown effective timestep')).toBeInTheDocument()
  })

  it('shows "Unknown effective timestep" when effective_timestep_minutes is null', async () => {
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
    mockApi.getSimulationRun.mockResolvedValue({
      run_id: 'run_123',
      scenario_id: 'scenario_test',
      scenario_config: { effective_timestep_minutes: null },
      controller_type: 'rule_based',
      status: 'completed',
      start_time: new Date().toISOString(),
    })

    renderReport('run_123')
    expect(await screen.findByText('Unknown effective timestep')).toBeInTheDocument()
  })

  it('shows "Dataset resolution N min" when effective_timestep_minutes is provided', async () => {
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
    mockApi.getSimulationRun.mockResolvedValue({
      run_id: 'run_123',
      scenario_id: 'scenario_test',
      scenario_config: { effective_timestep_minutes: 60 },
      controller_type: 'rule_based',
      status: 'completed',
      start_time: new Date().toISOString(),
    })

    renderReport('run_123')
    expect(await screen.findByText(/Dataset resolution/)).toBeInTheDocument()
  })
})
