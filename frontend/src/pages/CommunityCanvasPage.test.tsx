import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { CommunityCanvasPage } from '@/pages/CommunityCanvasPage'
import { api } from '@/api/client'
import { useNavigate } from 'react-router-dom'

vi.mock('@/api/client', () => ({
  api: {
    getRuns: vi.fn(),
    getScenario: vi.fn(),
    getTrajectories: vi.fn(),
    getNetworkGeometry: vi.fn(),
    getAssetMetadata: vi.fn(),
  },
  wsManager: { on: vi.fn(), off: vi.fn(), send: vi.fn(), disconnect: vi.fn() },
}))

vi.mock('react-router-dom', async (importActual) => {
  const actual = await importActual<typeof import('react-router-dom')>()
  return {
    ...actual,
    useNavigate: vi.fn(() => vi.fn()),
  }
})

const mockApi = vi.mocked(api)
const mockNavigate = vi.mocked(useNavigate)

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  sessionStorage.clear()
})

describe('CommunityCanvasPage', () => {
  const run = {
    run_id: 'run_abc',
    scenario_id: 'scenario_a',
    controller_type: 'rule_based',
    status: 'completed',
  } as any

  const scenario = {
    scenario_id: 'scenario_a',
    name: 'Scenario A',
    buildings: [
      { building_id: 'building_1', location: { lat: 40, lon: -105 } },
    ],
    pandapower: { bus_mappings: [{ building_id: 'building_1', bus_idx: 0 }] },
  } as any

  const trajectories = [
    { timestep: 0, observations: { 'building_1_solar_generation': 5 } },
  ] as any

  it('shows empty state when no runs exist', async () => {
    mockApi.getRuns.mockResolvedValue([])
    render(
      <MemoryRouter>
        <CommunityCanvasPage />
      </MemoryRouter>,
    )
    await screen.findByText(/no community data/i)
  })

  it('navigates to scenario generator from empty state create button', async () => {
    mockApi.getRuns.mockResolvedValue([])
    mockNavigate.mockReturnValue(vi.fn())
    render(
      <MemoryRouter>
        <CommunityCanvasPage />
      </MemoryRouter>,
    )
    await screen.findByText(/no community data/i)
    const createBtn = screen.getByRole('button', { name: /create scenario/i })
    fireEvent.click(createBtn)
    expect(mockNavigate()).toHaveBeenCalledWith('/scenarios/generate')
  })

  it('renders run-based canvas data when runs exist', async () => {
    mockApi.getRuns.mockResolvedValue([run])
    mockApi.getScenario.mockResolvedValue(scenario)
    mockApi.getTrajectories.mockResolvedValue(trajectories)
    mockApi.getNetworkGeometry.mockResolvedValue({
      coordinate_system: 'geographic',
      buses: { '0': { bus_idx: 0, name: 'bus_0', lat: 40, lon: -105 } },
      lines: [],
      transformers: [],
      bounds: { min_lon: -105.1, max_lon: -104.9, min_lat: 39.9, max_lat: 40.1 },
    } as any)
    mockApi.getAssetMetadata.mockResolvedValue({ pv: [], batteries: [], evs: [] } as any)
    render(
      <MemoryRouter>
        <CommunityCanvasPage />
      </MemoryRouter>,
    )
    // Run-based data path: load scenario + trajectories for the run
    await waitFor(() => expect(mockApi.getScenario).toHaveBeenCalledWith('scenario_a'))
    await waitFor(() => expect(mockApi.getTrajectories).toHaveBeenCalledWith('run_abc'))
    // Canvas exits loading once run + scenario + trajectories + geometry ready,
    // and paints buildings instead of the empty state.
    await waitFor(() => expect(screen.queryByText(/no community data/i)).not.toBeInTheDocument())
  })
})
