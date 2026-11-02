import { Zap, Wifi, Battery, AlertTriangle, CheckCircle, AlertCircle, Minimize2, Maximize2 } from 'lucide-react'
import { useState } from 'react'
import './Network.css'

interface Bus {
  id: number
  voltage: number
  angle: number
  type: 'slack' | 'pv' | 'pq'
  violations: string[]
}

interface Line {
  from: number
  to: number
  loading: number
  limit: number
  violations: string[]
}

interface Transformer {
  id: number
  loading: number
  limit: number
  violations: string[]
}

const mockBuses: Bus[] = [
  { id: 0, voltage: 1.02, angle: 0, type: 'slack', violations: [] },
  { id: 1, voltage: 1.015, angle: -0.02, type: 'pq', violations: [] },
  { id: 2, voltage: 1.008, angle: -0.04, type: 'pq', violations: [] },
  { id: 3, voltage: 1.002, angle: -0.06, type: 'pq', violations: ['Voltage low: 0.94 pu'] },
  { id: 3, voltage: 0.94, angle: -0.08, type: 'pq', violations: ['Voltage low: 0.94 pu'] },
]

const mockLines: Line[] = [
  { from: 0, to: 1, loading: 45, limit: 100, violations: [] },
  { from: 1, to: 2, loading: 67, limit: 100, violations: [] },
  { from: 2, to: 3, loading: 115, limit: 100, violations: ['Line overloaded: 115%'] },
]

const mockTransformers: Transformer[] = [
  { id: 0, loading: 78, limit: 100, violations: [] },
  { id: 1, loading: 92, limit: 100, violations: ['Transformer near limit: 92%'] },
]

export default function Network() {
  const [selectedBus, setSelectedBus] = useState<number | null>(null)
  const [selectedLine, setSelectedLine] = useState<number | null>(null)
  const [viewMode, setViewMode] = useState<'overview' | 'detailed'>('overview')

  return (
    <div className="page">
      <div className="page-header">
        <div className="header-left">
          <h1>Network Monitor</h1>
          <p>Real-time grid monitoring and diagnostics</p>
        </div>
        <div className="header-actions">
          <select value={viewMode} onChange={(e) => setViewMode(e.target as HTMLSelectElement).value} className="filter-select">
            <option value="overview">Overview</option>
            <option value="detailed">Detailed View</option>
          </select>
          <button className="btn btn-secondary"><RefreshCw size={18} /> Refresh</button>
        </div>
      </div>

      <div className="dashboard-grid">
        {/* Bus Voltages */}
        <div className="card">
          <div className="card-header">
            <h2>Bus Voltages</h2>
            <span className="badge badge-success">All Normal</span>
          </div>
          <div className="card-body">
            <div className="table-responsive">
              <table className="table">
                <thead>
                  <tr>
                    <th>Bus</th>
                    <th>Type</th>
                    <th>Voltage (pu)</th>
                    <th>Angle (deg)</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {mockBuses.map((bus) => (
                    <tr key={bus.id} onClick={() => setSelectedBus(bus.id)} className={selectedBus === bus.id ? 'selected' : ''}>
                      <td>Bus {bus.id}</td>
                      <td>
                        <span className={`badge badge-${bus.type === 'slack' ? 'info' : bus.type === 'pv' ? 'warning' : 'secondary'}`}>
                          {bus.type.toUpperCase()}
                        </span>
                      </td>
                      <td>
                        <span className={bus.violations.length > 0 ? 'text-danger font-bold' : ''}>
                          {bus.voltage.toFixed(3)}
                        </span>
                      </td>
                      <td>{bus.angle.toFixed(4)}</td>
                      <td>
                        {bus.violations.length > 0 ? (
                          <span className="badge badge-danger">Violation</span>
                        ) : (
                          <span className="badge badge-success">OK</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Line Loadings */}
        <div className="card">
          <div className="card-header">
            <h2>Line Loadings</h2>
            <span className="badge badge-warning">1 Overloaded</span>
          </div>
          <div className="card-body">
            <div className="table-responsive">
              <table className="table">
                <thead>
                  <tr>
                    <th>From</th>
                    <th>To</th>
                    <th>Loading (%)</th>
                    <th>Limit (%)</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {mockLines.map((line, idx) => (
                    <tr key={idx} onClick={() => setSelectedLine(idx)} className={selectedLine === idx ? 'selected' : ''}>
                      <td>Bus {line.from}</td>
                      <td>Bus {line.to}</td>
                      <td>
                        <div className="progress-container">
                          <div className="progress-bar">
                            <div className="progress-fill" style={{ width: `${Math.min(line.loading, 100)}%` }}></div>
                          </div>
                          <span>{line.loading}%</span>
                        </div>
                      </td>
                      <td>{line.limit}%</td>
                      <td>
                        {line.violations.length > 0 ? (
                          <span className="badge badge-danger">Overloaded</span>
                        ) : (
                          <span className="badge badge-success">OK</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Transformer Loadings */}
        <div className="card">
          <div className="card-header">
            <h2>Transformer Loadings</h2>
            <span className="badge badge-warning">1 Near Limit</span>
          </div>
          <div className="card-body">
            <div className="table-responsive">
              <table className="table">
                <thead>
                  <tr>
                    <th>Transformer</th>
                    <th>Loading (%)</th>
                    <th>Limit (%)</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {mockTransformers.map((tx, idx) => (
                    <tr key={idx}>
                      <td>Transformer {tx.id}</td>
                      <td>
                        <div className="progress-container">
                          <div className="progress-bar">
                            <div className="progress-fill" style={{ width: `${Math.min(tx.loading, 100)}%` }}></div>
                          </div>
                          <span>{tx.loading}%</span>
                        </div>
                      </td>
                      <td>{tx.limit}%</td>
                      <td>
                        {tx.violations.length > 0 ? (
                          <span className="badge badge-warning">Near Limit</span>
                        ) : (
                          <span className="badge badge-success">OK</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Voltage Profile */}
        <div className="card">
          <div className="card-header">
            <h2>Voltage Profile</h2>
          </div>
          <div className="card-body">
            <div className="voltage-chart">
              {mockBuses.map((bus, idx) => (
                <div key={idx} className="voltage-bar">
                  <div className="bar-label">Bus {bus.id}</div>
                  <div className="bar-container">
                    <div className="bar" style={{ 
                      height: `${Math.max(0, (bus.voltage - 0.9) * 200)}%`,
                      backgroundColor: bus.violations.length > 0 ? 'var(--danger-color)' : 
                                     bus.voltage < 0.97 || bus.voltage > 1.03 ? 'var(--warning-color)' : 'var(--success-color)'
                    }}></div>
                  </div>
                  <div className="bar-value">{bus.voltage.toFixed(3)} pu</div>
                </div>
))}
            </div>
          </div>
        </div>

        {/* Violations Summary */}
        <div className="card">
          <div className="card-header">
            <h2>Active Violations</h2>
            <span className="badge badge-danger">3 Active</span>
          </div>
          <div className="card-body">
            <ul className="violations-list">
              <li className="violation-item danger">
                <AlertCircle size={18} />
                <div>
                  <strong>Voltage Violation</strong>
                  <span>Bus 3: 0.94 pu (limit: 0.95-1.05)</span>
                </div>
              </li>
              <li className="violation-item warning">
                <AlertTriangle size={18} />
                <div>
                  <strong>Line Overload</strong>
                  <span>Line 2-3: 115% (limit: 100%)</span>
                </div>
              </li>
              <li className="violation-item warning">
                <AlertTriangle size={18} />
                <div>
                  <strong>Transformer Near Limit</strong>
                  <span>Transformer 1: 92% loading</span>
                </div>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}