import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { StrategyPanel } from './StrategyPanel'
import { api } from '../../api/client'
import type { TimeStepData } from '../../api/types'

const mockApi = vi.mocked(api)

vi.mock('../../api/client', () => ({
  api: {
    getTrajectories: vi.fn(),
  },
}))

const buildings = [
  { building_id: 'building_1', building_type: 'residential', location: { lat: 40, lon: -105 } },
]

const baseStrategy = {
  name: 'Rule-Based',
  controller: 'rule_based',
  total_cost: 1200,
  carbon_emissions_kg: 400,
  grid_import_kwh: 100,
  grid_export_kwh: 50,
  import_limit_kwh: 200,
  export_limit_kwh: 100,
  voltage_violations_count: 0,
  max_voltage_pu: 1.02,
  run_id: 'run_xyz',
  status: 'completed' as const,
  power_flow_converged: true,
}

const trajectories: TimeStepData[] = [
  {
    timestep: 0,
    timestamp: '2026-01-01T00:00:00Z',
    observations: {},
    applied_actions: [
      { asset_id: 'battery_1', action_type: 'battery_charge', value_kw: 50, requested_kw: 50 },
      { asset_id: 'ev_1', action_type: 'ev_charge', value_kw: 11, requested_kw: 11 },
    ],
    costs: {},
  },
  {
    timestep: 1,
    timestamp: '2026-01-01T00:15:00Z',
    observations: {},
    applied_actions: [
      { asset_id: 'battery_1', action_type: 'battery_discharge', value_kw: 30, requested_kw: 30 },
      { asset_id: 'flex_1', action_type: 'flexible_load', value_kw: 5, requested_kw: 5 },
    ],
    costs: {},
  },
]

describe('StrategyPanel controller fallback labelling', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockApi.getTrajectories.mockResolvedValue([])
  })

  it('shows controller_type, fallback_steps/total_steps, reason and effective controller', () => {
    render(
      <StrategyPanel
        strategy={{
          ...baseStrategy,
          controller: 'mpc',
          fallback_steps: 24,
          fallback_reason: 'semantic_fallback_to_rule_based',
        }}
        buildings={buildings}
        currentTimestep={0}
        maxTimestep={23}
      />
    )
    expect(screen.getByText('Controller Fallback')).toBeInTheDocument()
    expect(screen.getByText('Controller: mpc')).toBeInTheDocument()
    expect(screen.getByText('24/24 steps')).toBeInTheDocument()
    expect(screen.getByText('semantic_fallback_to_rule_based')).toBeInTheDocument()
    expect(
      screen.getByText('Effective controller: rule_based (via fallback)')
    ).toBeInTheDocument()
  })

  it('shows "no record" when no fallback marker is provided', () => {
    render(
      <StrategyPanel
        strategy={{ ...baseStrategy }}
        buildings={buildings}
        currentTimestep={0}
        maxTimestep={95}
      />
    )
    expect(screen.getByText('Controller Fallback')).toBeInTheDocument()
    expect(screen.getByText('無紀錄 / no record')).toBeInTheDocument()
    expect(screen.queryByText('steps')).not.toBeInTheDocument()
  })
})

describe('StrategyPanel dispatch trace', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockApi.getTrajectories.mockResolvedValue([])
  })

  it('shows "No dispatch trace data for this run" when no trajectories', async () => {
    mockApi.getTrajectories.mockResolvedValue([])
    render(
      <StrategyPanel
        strategy={{ ...baseStrategy }}
        buildings={buildings}
        currentTimestep={0}
        maxTimestep={23}
      />
    )
    await waitFor(() => expect(mockApi.getTrajectories).toHaveBeenCalledWith('run_xyz'))
    expect(screen.getByText('No dispatch trace data for this run')).toBeInTheDocument()
  })

  it('shows battery/EV/flexible dispatch values for the current timestep', async () => {
    mockApi.getTrajectories.mockResolvedValue(trajectories)
    render(
      <StrategyPanel
        strategy={{ ...baseStrategy }}
        buildings={buildings}
        currentTimestep={0}
        maxTimestep={23}
      />
    )
    await waitFor(() => expect(screen.getByText('Battery: 50.0 kW')).toBeInTheDocument())
    expect(screen.getByText('EV: 11.0 kW')).toBeInTheDocument()
    expect(screen.queryByText('Flexible load: 5.0 kW')).not.toBeInTheDocument()
  })

  it('shows different dispatch values when the timestep changes', async () => {
    mockApi.getTrajectories.mockResolvedValue(trajectories)
    render(
      <StrategyPanel
        strategy={{ ...baseStrategy }}
        buildings={buildings}
        currentTimestep={1}
        maxTimestep={23}
      />
    )
    await waitFor(() => expect(screen.getByText('Battery: 30.0 kW')).toBeInTheDocument())
    expect(screen.queryByText('EV: 11.0 kW')).not.toBeInTheDocument()
    expect(screen.getByText('Flexible load: 5.0 kW')).toBeInTheDocument()
  })
})
