import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CommunityCanvasPage } from './pages/CommunityCanvasPage';
import { ScenarioStudioPage } from './pages/ScenarioStudioPage';
import { AgentWorkspacePage } from './pages/AgentWorkspacePage';
import { ReportPage } from './pages/ReportPage';
import { ComparisonPage } from './pages/ComparisonPage';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen w-full bg-space">
          <Routes>
            <Route path="/" element={<CommunityCanvasPage />} />
            <Route path="/scenarios" element={<ScenarioStudioPage />} />
            <Route path="/agent" element={<AgentWorkspacePage />} />
            <Route path="/reports/:runId" element={<ReportPage />} />
            <Route path="/compare/:runIdA/:runIdB" element={<ComparisonPage />} />
          </Routes>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;