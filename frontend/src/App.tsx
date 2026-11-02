import { Routes, Route } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Scenarios from './pages/Scenarios'
import Experiments from './pages/Experiments'
import Network from './pages/Network'
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
      </Route>
    </Routes>
  )
}

export default App