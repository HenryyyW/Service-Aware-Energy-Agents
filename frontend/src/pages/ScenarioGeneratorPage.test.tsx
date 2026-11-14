import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ScenarioGeneratorPage } from '@/pages/ScenarioGeneratorPage'
import { api } from '@/api/client'

vi.mock('@/api/client', () => ({
  api: {
    generateScenario: vi.fn(),
    createScenario: vi.fn(),
    validateScenario: vi.fn(),
  },
  wsManager: { on: vi.fn(), off: vi.fn(), send: vi.fn(), disconnect: vi.fn() },
}))

const mockApi = vi.mocked(api)

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  sessionStorage.clear()
})

const fakeConfig = {
  scenario_id: 'scenario_x',
  name: 'Fake Community',
  description: 'A test community',
  timestep_minutes: 15,
  random_seed: 42,
  community_import_limit_kw: 200,
  community_export_limit_kw: 100,
  buildings: [{ building_id: 'building_1', building_type: 'residential', location: { lat: 40, lon: -105 } }],
  pandapower: { bus_mappings: [{ building_id: 'building_1', bus_idx: 0 }] },
  energy_sharing: { enabled: false },
} as any

describe('ScenarioGeneratorPage confirm screen', () => {
  it('renders all section icons after generate — no white screen', async () => {
    mockApi.generateScenario.mockResolvedValue({
      config: fakeConfig,
      plan_source: 'llm',
      rejected_fields: [],
      success: true,
      iterations: 1,
      final_verdict: null,
      elapsed_s: 0,
    })

    render(
      <MemoryRouter>
        <ScenarioGeneratorPage />
      </MemoryRouter>,
    )

    // Input step: describe and generate
    const textarea = screen.getByPlaceholderText(/describe the community/i)
    fireEvent.change(textarea, { target: { value: 'A renewable community with PV and batteries' } })
    fireEvent.click(screen.getByRole('button', { name: /generate config/i }))

    // Confirm step renders without crashing
    await waitFor(() => expect(screen.getByText(/confirm scenario/i)).toBeInTheDocument())

    // All seven sections render with their icons (none undefined)
    for (const title of ['Community', 'Buildings', 'PV', 'Battery', 'EV', 'Grid', 'Sharing']) {
      expect(screen.getByText(title)).toBeInTheDocument()
    }

    // No React element-type crash surface
    expect(screen.queryByText(/element type is invalid/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/undefined/i)).not.toBeInTheDocument()
  })
})
