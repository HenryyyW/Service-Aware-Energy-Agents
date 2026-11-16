import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StrategyPanel } from './StrategyPanel'

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

describe('StrategyPanel controller fallback labelling', () => {
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
