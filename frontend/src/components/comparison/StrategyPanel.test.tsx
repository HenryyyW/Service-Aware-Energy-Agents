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

describe('StrategyPanel OPF fallback labelling', () => {
  it('shows fallback steps + reason when backend provides them', () => {
    render(
      <StrategyPanel
        strategy={{ ...baseStrategy, fallback_steps: 2, fallback_reason: 'voltage violation cleared' }}
        buildings={buildings}
        currentTimestep={0}
        maxTimestep={95}
      />
    )
    expect(screen.getByText('OPF Fallback')).toBeInTheDocument()
    expect(screen.getByText('2 steps')).toBeInTheDocument()
    expect(screen.getByText('voltage violation cleared')).toBeInTheDocument()
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
    expect(screen.getByText('OPF Fallback')).toBeInTheDocument()
    expect(screen.getByText('無紀錄 / no record')).toBeInTheDocument()
    expect(screen.queryByText('steps')).not.toBeInTheDocument()
  })
})
