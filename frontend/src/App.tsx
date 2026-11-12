import { Routes, Route } from 'react-router-dom'
import { ScenarioDetailPage } from './pages/ScenarioDetailPage';
import Dashboard from './pages/Dashboard'
import Scenarios from './pages/Scenarios'
import Experiments from './pages/Experiments'
import Network from './pages/Network'
import { ScenarioStudioPage } from './pages/ScenarioStudioPage'
import { AgentWorkspacePage } from './pages/AgentWorkspacePage'
import { ReportPage } from './pages/ReportPage'
import { ScenarioGeneratorPage } from './pages/ScenarioGeneratorPage'
import { ScenarioProbePage } from './pages/ScenarioProbePage'
import { StrategyComparisonPage } from './pages/StrategyComparisonPage'
import { CommunityCanvasPage } from './pages/CommunityCanvasPage'
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
        <Route path="scenarios/:scenarioId" element={<ScenarioDetailPage />} />
        <Route path="scenarios/generate" element={<ScenarioGeneratorPage />} />
        <Route path="scenarios/probe/:scenarioId" element={<ScenarioProbePage />} />
        <Route path="comparison/strategy/:scenarioId" element={<StrategyComparisonPage />} />
        <Route path="canvas" element={<CommunityCanvasPage />} />
        <Route path="runs/:runId/report" element={<ReportPage />} />
      </Route>
    </Routes>
  )
}

export default App
