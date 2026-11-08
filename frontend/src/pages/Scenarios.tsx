import { Search, Filter, Download, Edit, Trash2, Eye } from '../utils/lucide'
import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useScenarioStore } from '../store/scenarioStore'
import type { ScenarioConfig } from '../api/types'
import './Scenarios.css'

export default function Scenarios() {
  const [scenarios, setScenarios] = useState<ScenarioConfig[]>([])
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedScenario, setSelectedScenario] = useState<ScenarioConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()
  const setCurrentScenario = useScenarioStore((state) => state.setCurrentScenario)

  const fetchScenarios = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const list = await api.getScenarios()
      setScenarios(Array.isArray(list) ? list : [])
    } catch {
      setError('Failed to load scenarios from the API')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchScenarios()
  }, [fetchScenarios])

  const filteredScenarios = scenarios.filter((s) => {
    const haystack = [
      s.name || s.community?.name || '',
      s.description || '',
      s.scenario_id || '',
    ].join(' ').toLowerCase()
    const term = searchTerm.toLowerCase()
    return !term || haystack.includes(term)
  })

  const handleRunExperiment = () => {
    if (!selectedScenario) return
    setCurrentScenario(selectedScenario)
    navigate('/studio')
  }

  const scenarioName = (s: ScenarioConfig) => s.name || s.community?.name || 'Unnamed'
  const scenarioBuildings = (s: ScenarioConfig) => s.community?.buildings ?? 0
  const scenarioTimestep = (s: ScenarioConfig) => s.community?.timestep_minutes ?? 15
  const scenarioGridLimit = (s: ScenarioConfig) =>
    s.community_import_limit_kw ?? s.grid?.import_limit_kw ?? 0
  const scenarioCreated = () => ''

  return (
    <div className="page">
      <div className="page-header">
        <div className="header-left">
          <h1>Scenarios</h1>
          <p>Manage simulation scenarios and configurations</p>
        </div>
      </div>

      {error && (
        <div className="card p-4 border border-violation/30 bg-violation/10">
          <p className="text-violation text-body-sm">{error}</p>
        </div>
      )}

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
                disabled={loading}
              />
            </div>
            <div className="filter-actions">
              <button className="btn btn-secondary" disabled={loading}>
                <Filter size={18} /> Filters
              </button>
              <button className="btn btn-secondary" disabled={loading}>
                <Download size={18} /> Export
              </button>
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
                {loading ? (
                  <tr>
                    <td colSpan={7} className="text-center text-text-muted py-4">
                      Loading scenarios…
                    </td>
                  </tr>
                ) : filteredScenarios.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="text-center text-text-muted py-4">
                      No scenarios found{error ? '. ' + error : '.'}
                    </td>
                  </tr>
                ) : (
                  filteredScenarios.map((scenario) => (
                    <tr key={scenario.scenario_id || scenarioName(scenario)}>
                      <td>
                        <strong>{scenarioName(scenario)}</strong>
                        <br />
                        <span className="text-secondary text-sm">{scenario.description || ''}</span>
                        <span className="block text-xs text-text-muted mt-0.5">
                          {scenario.scenario_id || scenarioName(scenario)}
                        </span>
                      </td>
                      <td>{scenarioBuildings(scenario)}</td>
                      <td>{scenarioTimestep(scenario)} min</td>
                      <td>{scenarioGridLimit(scenario)} kW</td>
                      <td>{scenarioCreated()}</td>
                      <td>
                        <div className="action-buttons">
                          <button
                            className="btn-icon"
                            onClick={() => setSelectedScenario(scenario)}
                            title="View"
                          >
                            <Eye size={16} />
                          </button>
                          <button
                            className="btn-icon"
                            onClick={() => setSelectedScenario(scenario)}
                            title="Edit"
                          >
                            <Edit size={16} />
                          </button>
                          <button
                            className="btn-icon danger"
                            onClick={() => {}}
                            title="Delete"
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
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
              <h2>{scenarioName(selectedScenario)}</h2>
              <button onClick={() => setSelectedScenario(null)} className="close-btn">×</button>
            </div>
            <div className="modal-body">
              <p>{selectedScenario.description || ''}</p>
              <div className="detail-grid">
                <div className="detail-item">
                  <span className="label">Buildings</span>
                  <span className="value">{scenarioBuildings(selectedScenario)}</span>
                </div>
                <div className="detail-item">
                  <span className="label">Timestep</span>
                  <span className="value">{scenarioTimestep(selectedScenario)} min</span>
                </div>
                <div className="detail-item">
                  <span className="label">Grid Import Limit</span>
                  <span className="value">{scenarioGridLimit(selectedScenario)} kW</span>
                </div>
                <div className="detail-item">
                  <span className="label">ID</span>
                  <span className="value">{selectedScenario.scenario_id || scenarioName(selectedScenario)}</span>
                </div>
                <div className="detail-item">
                  <span className="label">Created</span>
                  <span className="value">{scenarioCreated()}</span>
                </div>
              </div>
              <div className="modal-footer">
                <button
                  className="btn btn-primary"
                  onClick={() => {
                    setSelectedScenario(null)
                    handleRunExperiment()
                  }}
                >
                  Run Experiment
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
