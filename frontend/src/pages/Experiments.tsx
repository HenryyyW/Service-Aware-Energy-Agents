import { Plus, Search, Filter, Download, Play, Pause, Stop, RefreshCw, Eye, Settings } from 'lucide-react'
import { useState } from 'react'
import './Experiments.css'

interface Experiment {
  id: string
  runId: string
  scenario: string
  controller: string
  regime: string
  seed: number
  status: string
  cost: number
  progress: number
  startedAt: string
  duration?: string
}

const mockExperiments: Experiment[] = [
  { id: '1', runId: 'scenario_a_rule_based_42', scenario: 'Scenario A', controller: 'rule_based', regime: 'pool_tou', seed: 42, status: 'completed', cost: 1245.50, progress: 100, startedAt: '2026-10-30T10:00:00', duration: '45 min' },
  { id: '2', runId: 'scenario_a_mpc_42', scenario: 'Scenario A', controller: 'mpc', regime: 'pool_tou', seed: 42, status: 'completed', cost: 1180.30, progress: 100, startedAt: '2026-10-30T11:00:00', duration: '52 min' },
  { id: '3', runId: 'scenario_a_llm_agent_42', scenario: 'Scenario A', controller: 'llm_agent', regime: 'pool_tou', seed: 42, status: 'running', cost: 0, progress: 45, startedAt: '2026-10-30T12:00:00' },
  { id: '4', runId: 'scenario_b_rule_based_42', scenario: 'Scenario B', controller: 'rule_based', regime: 'lmp', seed: 42, status: 'completed', cost: 2150.75, progress: 100, startedAt: '2026-10-29T10:00:00', duration: '38 min' },
  { id: '5', runId: 'scenario_e_multi_agent_42', scenario: 'Scenario E', controller: 'multi_agent', regime: 'p2p', seed: 42, status: 'completed', cost: 980.20, progress: 100, startedAt: '2026-10-28T15:00:00', duration: '67 min' },
]

const controllers = ['rule_based', 'mpc', 'llm_agent', 'llm_agent_verified', 'centralized', 'multi_agent']
const scenarios = ['Scenario A', 'Scenario B', 'Scenario C', 'Scenario D', 'Scenario E']
const regimes = ['pool_tou', 'lmp', 'p2p']

export default function Experiments() {
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [controllerFilter, setControllerFilter] = useState('all')
  const [scenarioFilter, setScenarioFilter] = useState('all')
  const [regimeFilter, setRegimeFilter] = useState('all')
  const [showCreateModal, setShowCreateModal] = useState(false)

  const filteredExperiments = mockExperiments.filter(exp => {
    const matchesSearch = exp.runId.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesStatus = statusFilter === 'all' || exp.status === statusFilter
    const matchesController = controllerFilter === 'all' || exp.controller === controllerFilter
    const matchesScenario = scenarioFilter === 'all' || exp.scenario === scenarioFilter
    const matchesRegime = regimeFilter === 'all' || exp.regime === regimeFilter
    return matchesSearch && matchesStatus && matchesController && matchesScenario && matchesRegime
  })

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed': return 'badge-success'
      case 'running': return 'badge-info'
      case 'pending': return 'badge-warning'
      case 'failed': return 'badge-danger'
      default: return 'badge-info'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return '✓'
      case 'running': return '⟳'
      case 'pending': return '○'
      case 'failed': return '✕'
      default: return '?'
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <div className="header-left">
          <h1>Experiments</h1>
          <p>Manage and monitor simulation experiments</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreateModal(true)}>
          <Plus size={18} /> New Experiment
        </button>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="search-filter">
            <div className="search-box">
              <Search size={18} />
              <input
                type="text"
                placeholder="Search experiments..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <div className="filters">
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="filter-select">
                <option value="all">All Status</option>
                <option value="completed">Completed</option>
                <option value="running">Running</option>
                <option value="pending">Pending</option>
                <option value="failed">Failed</option>
              </select>
              <select value={controllerFilter} onChange={(e) => setControllerFilter(e.target.value)} className="filter-select">
                <option value="all">All Controllers</option>
                {controllers.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
              <select value={scenarioFilter} onChange={(e) => setScenarioFilter(e.target.value)} className="filter-select">
                <option value="all">All Scenarios</option>
                {scenarios.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
              <select value={regimeFilter} onChange={(e) => setRegimeFilter(e.target.value)} className="filter-select">
                <option value="all">All Regimes</option>
                {regimes.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
          </div>
        </div>
        <div className="card-body">
          <div className="table-responsive">
            <table className="table">
              <thead>
                <tr>
                  <th>Run ID</th>
                  <th>Scenario</th>
                  <th>Controller</th>
                  <th>Regime</th>
                  <th>Seed</th>
                  <th>Status</th>
                  <th>Progress</th>
                  <th>Cost</th>
                  <th>Started</th>
                  <th>Duration</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredExperiments.map((exp) => (
                  <tr key={exp.id}>
                    <td><code>{exp.runId}</code></td>
                    <td>{exp.scenario}</td>
                    <td>{exp.controller}</td>
                    <td>{exp.regime}</td>
                    <td>{exp.seed}</td>
                    <td>
                      <span className={`badge ${getStatusBadge(exp.status)}`}>
                        {getStatusIcon(exp.status)} {exp.status}
                      </span>
                    </td>
                    <td>
                      <div className="progress-bar">
                        <div className="progress-fill" style={{ width: `${exp.progress}%` }}></div>
                      </div>
                      <span className="text-sm">{exp.progress}%</span>
                    </td>
                    <td>${exp.cost.toFixed(2)}</td>
                    <td>{exp.startedAt}</td>
                    <td>{exp.duration || '-'}</td>
                    <td>
                      <div className="action-buttons">
                        <button className="btn-icon" title="View Details"><Eye size={16} /></button>
                        <button className="btn-icon" title="View Results"><Settings size={16} /></button>
                        {exp.status === 'running' && (
                          <>
                            <button className="btn-icon" title="Pause"><Pause size={16} /></button>
                            <button className="btn-icon danger" title="Stop"><Stop size={16} /></button>
                          </>
                        )}
                        {exp.status === 'pending' && (
                          <button className="btn-icon" title="Start"><Play size={16} /></button>
                        )}
                        <button className="btn-icon" title="Retry"><RefreshCw size={16} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}