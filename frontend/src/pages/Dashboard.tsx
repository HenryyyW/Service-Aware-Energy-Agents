import { DollarSign, Zap, Home, TrendingUp, TrendingDown } from '../utils/lucide'
import { useState } from 'react'
import './Dashboard.css'

interface MetricCardProps {
  title: string
  value: string | number
  change?: string
  trend?: 'up' | 'down' | 'neutral'
  icon: React.ReactElement<{ size?: number }>
  color: string
}

function MetricCard({ title, value, change, trend, icon, color }: MetricCardProps) {
  return (
    <div className="metric-card" style={{ '--accent-color': color } as React.CSSProperties}>
      <div className="metric-header">
        <span className="metric-title">{title}</span>
        <div className="metric-icon" style={{ backgroundColor: `${color}20`, borderColor: color }}>
          {icon}
        </div>
      </div>
      <div className="metric-value">{value}</div>
      {change && (
        <div className={`metric-change ${trend}`}>
          {trend === 'up' && <TrendingUp size={14} />}
          {trend === 'down' && <TrendingDown size={14} />}
          {trend === 'neutral' && <span>→</span>}
          <span>{change}</span>
        </div>
      )}
    </div>
  )
}

interface GridStatusProps {
  voltage: number
  lineLoading: number
  transformerLoading: number
  importUsage: number
  exportUsage: number
}

function GridStatus({ voltage, lineLoading, transformerLoading, importUsage, exportUsage }: GridStatusProps) {
  const getStatusColor = (value: number, warning: number, danger: number) => {
    if (value >= danger) return 'danger'
    if (value >= warning) return 'warning'
    return 'success'
  }

  const gauges = [
    { label: 'Voltage', value: `${voltage.toFixed(2)} pu`, unit: 'pu', current: voltage, warning: 1.03, danger: 1.05, invert: true },
    { label: 'Line Loading', value: `${lineLoading.toFixed(1)}%`, unit: '%', current: lineLoading, warning: 80, danger: 100 },
    { label: 'Transformer', value: `${transformerLoading.toFixed(1)}%`, unit: '%', current: transformerLoading, warning: 80, danger: 100 },
    { label: 'Import Usage', value: `${importUsage.toFixed(1)}%`, unit: '%', current: importUsage, warning: 80, danger: 100 },
    { label: 'Export Usage', value: `${exportUsage.toFixed(1)}%`, unit: '%', current: exportUsage, warning: 80, danger: 100 },
  ]

  return (
    <div className="card">
      <div className="card-header">
        <h2>Grid Status</h2>
        <span className="badge badge-success">All Systems Normal</span>
      </div>
      <div className="card-body">
        <div className="gauges-grid">
          {gauges.map((gauge) => {
            const color = getStatusColor(
              gauge.invert ? (1 / gauge.current) * 100 : gauge.current,
              gauge.warning,
              gauge.danger
            )
            return (
              <div key={gauge.label} className={`gauge ${color}`}>
                <div className="gauge-label">{gauge.label}</div>
                <div className="gauge-value">{gauge.value}</div>
                <div className="gauge-bar">
                  <div className="gauge-fill" style={{ width: `${Math.min(gauge.current, 100)}%` }}></div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

interface RecentExperimentsProps {
  experiments: Array<{
    id: string
    scenario: string
    controller: string
    status: string
    cost: number
    time: string
  }>
}

function RecentExperiments({ experiments }: RecentExperimentsProps) {
  return (
    <div className="card">
      <div className="card-header">
        <h2>Recent Experiments</h2>
        <a href="/experiments" className="view-all">View All</a>
      </div>
      <div className="card-body">
        <table className="table">
          <thead>
            <tr>
              <th>Run ID</th>
              <th>Scenario</th>
              <th>Controller</th>
              <th>Status</th>
              <th>Cost</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            {experiments.map((exp) => (
              <tr key={exp.id}>
                <td>{exp.id}</td>
                <td>{exp.scenario}</td>
                <td>{exp.controller}</td>
                <td><span className={`badge badge-${exp.status === 'completed' ? 'success' : exp.status === 'running' ? 'info' : 'warning'}`}>{exp.status}</span></td>
                <td>${exp.cost.toFixed(2)}</td>
                <td>{exp.time}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [metrics] = useState({
    totalCost: { value: '$12,450', change: '-2.3%', trend: 'down' as const },
    totalEnergy: { value: '1.24 MWh', change: '+1.2%', trend: 'up' as const },
    avgComfort: { value: '0.87', change: '+0.02', trend: 'up' as const },
    gridEvents: { value: '23', change: '-5', trend: 'down' as const },
  })
  const [gridStatus] = useState({
    voltage: 1.01,
    lineLoading: 67,
    transformerLoading: 45,
    importUsage: 42,
    exportUsage: 28,
  })
  const [experiments] = useState([
    { id: 'exp_001', scenario: 'Scenario A', controller: 'multi_agent', status: 'completed', cost: 1245.50, time: '2h ago' },
    { id: 'exp_002', scenario: 'Scenario B', controller: 'mpc', status: 'completed', cost: 1389.20, time: '4h ago' },
    { id: 'exp_003', scenario: 'Scenario E', controller: 'llm_agent', status: 'running', cost: 0, time: 'Just now' },
    { id: 'exp_004', scenario: 'Scenario A', controller: 'rule_based', status: 'completed', cost: 1420.10, time: '1d ago' },
  ])

  return (
    <div className="dashboard">
      <div className="page-header">
        <h1>Dashboard</h1>
        <p>System overview and key metrics</p>
      </div>

      <div className="metrics-grid">
        <MetricCard
          title="Total Cost"
          value={metrics.totalCost.value}
          change={metrics.totalCost.change}
          trend={metrics.totalCost.trend}
          icon={<DollarSign size={24} />}
          color="#2563eb"
        />
        <MetricCard
          title="Energy Traded"
          value={metrics.totalEnergy.value}
          change={metrics.totalEnergy.change}
          trend={metrics.totalEnergy.trend}
          icon={<Zap size={24} />}
          color="#10b981"
        />
        <MetricCard
          title="Avg Comfort"
          value={metrics.avgComfort.value}
          change={metrics.avgComfort.change}
          trend={metrics.avgComfort.trend}
          icon={<Home size={24} />}
          color="#f59e0b"
        />
        <MetricCard
          title="Grid Events"
          value={metrics.gridEvents.value}
          change={metrics.gridEvents.change}
          trend={metrics.gridEvents.trend}
          icon={<TrendingDown size={24} />}
          color="#ef4444"
        />
      </div>

      <div className="dashboard-grid">
        <GridStatus
          voltage={gridStatus.voltage}
          lineLoading={gridStatus.lineLoading}
          transformerLoading={gridStatus.transformerLoading}
          importUsage={gridStatus.importUsage}
          exportUsage={gridStatus.exportUsage}
        />
        <RecentExperiments experiments={experiments} />
      </div>
    </div>
  )
}