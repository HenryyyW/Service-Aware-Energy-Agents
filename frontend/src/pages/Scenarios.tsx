import { Plus, Search, Filter, Download, Edit, Trash2, Eye } from 'lucide-react'
import { useState } from 'react'
import './Scenarios.css'

interface Scenario {
  id: string
  name: string
  description: string
  buildings: number
  timestep: number
  gridLimit: number
  createdAt: string
}

const mockScenarios: Scenario[] = [
  { id: 'scenario_a', name: 'Scenario A', description: 'Base residential community', buildings: 5, timestep: 15, gridLimit: 200, createdAt: '2026-10-15' },
  { id: 'scenario_b', name: 'Scenario B', description: 'Mixed commercial/residential', buildings: 8, timestep: 15, gridLimit: 300, createdAt: '2026-10-18' },
  { id: 'scenario_c', name: 'Scenario C', description: 'High PV penetration', buildings: 6, timestep: 15, gridLimit: 250, createdAt: '2026-10-20' },
  { id: 'scenario_d', name: 'Scenario D', description: 'Energy sharing enabled', buildings: 5, timestep: 15, gridLimit: 200, createdAt: '2026-10-22' },
  { id: 'scenario_e', name: 'Scenario E', description: 'Failure injection test', buildings: 5, timestep: 15, gridLimit: 200, createdAt: '2026-10-25' },
]

export default function Scenarios() {
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedScenario, setSelectedScenario] = useState<Scenario | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)

  const filteredScenarios = mockScenarios.filter(s =>
    s.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    s.description.toLowerCase().includes(searchTerm.toLowerCase())
  )

  return (
    <div className="page">
      <div className="page-header">
        <div className="header-left">
          <h1>Scenarios</h1>
          <p>Manage simulation scenarios and configurations</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreateModal(true)}>
          <span>+</span> New Scenario
        </button>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="search-filter">
            <div className="search-box">
              <Search size={18} />
              <input
                type="text"
                placeholder="Search scenarios..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <div className="filter-actions">
              <button className="btn btn-secondary"><Filter size={18} /> Filters</button>
              <button className="btn btn-secondary"><Download size={18} /> Export</button>
            </div>
          </div>
        </div>
        <div className="card-body">
          <div className="table-responsive">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Description</th>
                  <th>Buildings</th>
                  <th>Timestep</th>
                  <th>Grid Limit</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredScenarios.map((scenario) => (
                  <tr key={scenario.id}>
                    <td>
                      <strong>{scenario.name}</strong>
                      <br />
                      <span className="text-secondary text-sm">{scenario.description}</span>
                    </td>
                    <td>{scenario.buildings}</td>
                    <td>{scenario.timestep} min</td>
                    <td>{scenario.gridLimit} kW</td>
                    <td>{scenario.createdAt}</td>
                    <td>
                      <div className="action-buttons">
                        <button className="btn-icon" onClick={() => setSelectedScenario(scenario)} title="View">
                          <Eye size={16} />
                        </button>
                        <button className="btn-icon" onClick={() => setSelectedScenario(scenario)} title="Edit">
                          <Edit size={16} />
                        </button>
                        <button className="btn-icon danger" onClick={() => {}} title="Delete">
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Detail Modal */}
      {selectedScenario && (
        <div className="modal-overlay" onClick={() => setSelectedScenario(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{selectedScenario.name}</h2>
              <button onClick={() => setSelectedScenario(null)} className="close-btn">×</button>
            </div>
            <div className="modal-body">
              <p>{selectedScenario.description}</p>
              <div className="detail-grid">
                <div className="detail-item">
                  <span className="label">Buildings</span>
                  <span className="value">{selectedScenario.buildings}</span>
                </div>
                <div className="detail-item">
                  <span className="label">Timestep</span>
                  <span className="value">{selectedScenario.timestep} min</span>
                </div>
                <div className="detail-item">
                  <span className="label">Grid Import Limit</span>
                  <span className="value">{selectedScenario.gridLimit} kW</span>
                </div>
                <div className="detail-item">
                  <span className="label">Created</span>
                  <span className="value">{selectedScenario.createdAt}</span>
                </div>
              </div>
              <div className="modal-footer">
                <button className="btn btn-primary" onClick={() => {}}>Run Experiment</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}