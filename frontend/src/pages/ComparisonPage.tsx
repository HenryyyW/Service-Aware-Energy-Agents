import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useSimulationStore } from '../store/simulationStore';
import { useScenarioStore } from '../store/scenarioStore';
// import { api } from '../api/client';
import { ScenarioComparison } from '../components/scenario/ScenarioComparison';
import { ToastProvider, useToast } from '../components/ui/Toast';
import { Button } from '../components/ui/Button';
import { ChevronLeft, GitCompare, Download } from 'lucide-react';
import { Link } from 'react-router-dom';

function ComparisonPageContent() {
  const { runIdA, runIdB } = useParams<{ runIdA: string; runIdB: string }>();
  const { runs } = useSimulationStore();
  const { comparisonRunA, comparisonRunB, setComparisonRunA, setComparisonRunB, clearComparison } = useScenarioStore();
  const { addToast } = useToast();
  // Comparison data state removed
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (runIdA && runIdB) {
      loadComparison();
    }
  }, [runIdA, runIdB]);

  const loadComparison = async () => {
    setLoading(true);
    try {
      const runA = runs.find(r => r.run_id === runIdA);
      const runB = runs.find(r => r.run_id === runIdB);

      if (runA && runB) {
        setComparisonRunA(runA);
        setComparisonRunB(runB);
      }

      // Try to get detailed comparison from API
      try {
      } catch {
        // API might not have comparison endpoint yet
      }
    } catch (error) {
      console.error('Failed to load comparison:', error);
      addToast({ type: 'error', title: 'Failed to load comparison' });
    } finally {
      setLoading(false);
    }
  };

  const handleSelectA = (run: any) => {
    setComparisonRunA(run);
  };

  const handleSelectB = (run: any) => {
    setComparisonRunB(run);
  };

  const handleClear = () => {
    clearComparison();
  };

  const handleDownload = () => {
    // Would generate comparison report
    addToast({ type: 'info', title: 'Generating comparison report...', duration: 2000 });
  };

  const selectedA = comparisonRunA || runs.find(r => r.run_id === runIdA);
  const selectedB = comparisonRunB || runs.find(r => r.run_id === runIdB);

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-border/30 bg-surface/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link to="/" className="btn-ghost p-2" aria-label="Back to canvas">
              <ChevronLeft className="w-5 h-5" />
            </Link>
            <div>
              <h1 className="font-display font-semibold text-heading-1 text-text">Scenario Comparison</h1>
              <p className="text-caption text-text-muted">Side-by-side analysis of two simulation runs</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={handleDownload}>
              <Download className="w-4 h-4 mr-2" />
              Export Report
            </Button>
            {comparisonRunA && comparisonRunB && (
              <Button variant="ghost" size="icon" onClick={handleClear} aria-label="Clear comparison">
                <GitCompare className="w-4 h-4" />
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Comparison Content */}
      <div className="flex-1 overflow-auto p-4">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <div className="animate-spin w-8 h-8 border-2 border-sun/30 border-t-sun rounded-full" />
          </div>
        ) : (
          <ScenarioComparison
            runA={selectedA || null}
            runB={selectedB || null}
            onSelectRunA={handleSelectA}
            onSelectRunB={handleSelectB}
            onClear={handleClear}
          />
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-border/30 bg-surface/50">
        <Link to="/" className="btn-secondary">
          <ChevronLeft className="w-4 h-4 mr-2" />
          Back to Canvas
        </Link>
      </div>
    </div>
  );
}

export function ComparisonPage() {
  return (
    <ToastProvider>
      <ComparisonPageContent />
    </ToastProvider>
  );
}