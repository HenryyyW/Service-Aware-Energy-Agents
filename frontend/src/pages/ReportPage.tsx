import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useSimulationStore } from '../store/simulationStore';
import { useAgentStore } from '../store/agentStore';
import { api } from '../api/client';
import { ReportView } from '../components/agent/ReportView';
import { ToastProvider, useToast } from '../components/ui/Toast';
import { Button } from '../components/ui/Button';
import { Download, ChevronLeft, RotateCcw } from 'lucide-react';
import { Link } from 'react-router-dom';

function ReportPageContent() {
  const { runId } = useParams<{ runId: string }>();
  const { runs, currentRun } = useSimulationStore();
  const { currentTask } = useAgentStore();
  const { addToast } = useToast();
  const [report, setReport] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [format] = useState<'markdown'>('markdown');

  useEffect(() => {
    if (runId) {
      loadReport();
    }
  }, [runId]);

  const loadReport = async () => {
    setLoading(true);
    try {
      // Try to get report from agent task first
      if (currentTask?.report) {
        setReport(currentTask.report);
      } else {
        // Fallback to API
        const reportText = await api.getReport(runId!);
        setReport(reportText);
      }
    } catch (error) {
      console.error('Failed to load report:', error);
      addToast({ type: 'error', title: 'Failed to load report' });
      setReport('# Report Not Available\n\nCould not load the report for this run.');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (fmt: 'markdown') => {
    try {
      addToast({ type: 'info', title: `Generating ${fmt.toUpperCase()}...`, duration: 2000 });
      const blob = await api.downloadReport(runId!, fmt);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report_${runId}.${fmt === 'markdown' ? 'md' : fmt}`;
      a.click();
      URL.revokeObjectURL(url);
      addToast({ type: 'success', title: 'Report downloaded' });
    } catch (error) {
      console.error('Failed to download report:', error);
      addToast({ type: 'error', title: 'Download failed' });
    }
  };

  const run = runs.find(r => r.run_id === runId) || currentRun;

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
              <h1 className="font-display font-semibold text-heading-1 text-text">Simulation Report</h1>
              <p className="text-caption text-text-muted">{runId}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={format}
              className="input w-auto min-w-[140px] py-1.5 text-body-sm"
            >
              <option value="markdown">Markdown</option>
            </select>
            <Button onClick={() => handleDownload(format)}>
              <Download className="w-4 h-4 mr-2" />
              Download
            </Button>
            <Button variant="ghost" size="icon" onClick={loadReport} aria-label="Refresh">
              <RotateCcw className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>

      {/* Report Content */}
      <div className="flex-1 overflow-auto p-4">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <div className="animate-spin w-8 h-8 border-2 border-sun/30 border-t-sun rounded-full" />
          </div>
        ) : (
          <div className="max-w-4xl mx-auto">
            <ReportView
              report={report}
              onDownload={handleDownload}
            />
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-border/30 bg-surface/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4 text-caption text-text-muted">
            <span>Run: {run?.run_id || runId}</span>
            <span>Scenario: {run?.scenario_id || 'Unknown'}</span>
            <span>Controller: {run?.controller_type || 'Unknown'}</span>
            <span>{run?.start_time ? new Date(run.start_time).toLocaleString() : ''}</span>
          </div>
          <Link to="/" className="btn-secondary">
            <ChevronLeft className="w-4 h-4 mr-2" />
            Back to Canvas
          </Link>
        </div>
      </div>
    </div>
  );
}

export function ReportPage() {
  return (
    <ToastProvider>
      <ReportPageContent />
    </ToastProvider>
  );
}