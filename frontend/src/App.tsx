import { Routes, Route } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Scenarios from './pages/Scenarios'
import Experiments from './pages/Experiments'
import Network from './pages/Network'
import { ScenarioStudioPage } from './pages/ScenarioStudioPage'
import { AgentWorkspacePage } from './pages/AgentWorkspacePage'
import { ReportPage } from './pages/ReportPage'
import Layout from './components/Layout'
import './App.css'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="scenarios" element={<Scenarios />} />
        <Route path="experiments" element={<Experiments />} />
        <Route path="network" element={<Network />} />
        <Route path="studio" element={<ScenarioStudioPage />} />
        <Route path="workspace" element={<AgentWorkspacePage />} />
        <Route path="runs/:runId/report" element={<ReportPage />} />
      </Route>
    </Routes>
  )
}

export default App
