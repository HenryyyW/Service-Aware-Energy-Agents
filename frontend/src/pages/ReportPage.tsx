import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useSimulationStore } from '../store/simulationStore';
import { useAgentStore } from '../store/agentStore';
import { api } from '../api/client';
import { ReportView } from '../components/agent/ReportView';
import { ToastProvider, useToast } from '../components/ui/Toast';
import { Button } from '../components/ui/Button';
import { Tabs, TabList, Tab, TabPanel } from '../components/ui/Tabs';
import { Download, ChevronLeft, RotateCcw, FileText } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Table, TableHeaderCell, TableCell } from '../components/ui/Table';
import type { ReportResponse } from '../api/types';

function SettlementView({ settlement, run }: { settlement: any; run: any }) {
  if (!settlement) {
    return (
      <div className="glass-card p-8 text-center text-text-muted">
        <FileText className="w-16 h-16 mx-auto mb-4 text-text-muted/30" />
        <p className="text-body">No settlement data available</p>
        <p className="text-caption mt-2">Run a simulation with energy sharing enabled to see settlement data</p>
      </div>
    );
  }

  const settlementData = settlement.building_contributions || settlement.building_settlements || settlement;
  const entries = Object.entries(settlementData);

  if (entries.length === 0) {
    return (
      <div className="glass-card p-8 text-center text-text-muted">
        <FileText className="w-16 h-16 mx-auto mb-4 text-text-muted/30" />
        <p className="text-body">No settlement data available</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="glass-card p-4">
        <h3 className="font-body font-medium text-body text-text mb-4">Per-Member Settlement</h3>
        <div className="overflow-x-auto">
          <Table>
            <thead>
              <tr>
                <TableHeaderCell>Building</TableHeaderCell>
                <TableHeaderCell className="text-right">Net Settlement ($)</TableHeaderCell>
                <TableHeaderCell className="text-right">Grid Import (kWh)</TableHeaderCell>
                <TableHeaderCell className="text-right">Grid Export (kWh)</TableHeaderCell>
                <TableHeaderCell className="text-right">Community Import (kWh)</TableHeaderCell>
                <TableHeaderCell className="text-right">Community Export (kWh)</TableHeaderCell>
                <TableHeaderCell className="text-right">Savings vs Baseline ($)</TableHeaderCell>
              </tr>
            </thead>
            <tbody>
              {entries.map(([buildingId, data]) => (
                <tr key={buildingId}>
                  <TableCell className="font-mono">{buildingId}</TableCell>
                  <TableCell className="text-right text-energy">
                    {typeof data === 'object' && data !== null && 'net_settlement' in data
                      ? (data.net_settlement as number).toFixed(2)
                      : typeof data === 'number' ? data.toFixed(2) : 'N/A'}
                  </TableCell>
                  <TableCell className="text-right">
                    {typeof data === 'object' && data !== null && 'total_grid_import_kwh' in data
                      ? (data.total_grid_import_kwh as number).toFixed(2)
                      : 'N/A'}
                  </TableCell>
                  <TableCell className="text-right">
                    {typeof data === 'object' && data !== null && 'total_grid_export_kwh' in data
                      ? (data.total_grid_export_kwh as number).toFixed(2)
                      : 'N/A'}
                  </TableCell>
                  <TableCell className="text-right">
                    {typeof data === 'object' && data !== null && 'total_community_import_kwh' in data
                      ? (data.total_community_import_kwh as number).toFixed(2)
                      : 'N/A'}
                  </TableCell>
                  <TableCell className="text-right">
                    {typeof data === 'object' && data !== null && 'total_community_export_kwh' in data
                      ? (data.total_community_export_kwh as number).toFixed(2)
                      : 'N/A'}
                  </TableCell>
                  <TableCell className="text-right">
                    {typeof data === 'object' && data !== null && 'savings_vs_baseline' in data
                      ? (data.savings_vs_baseline as number).toFixed(2)
                      : typeof data === 'object' && data !== null && 'net_settlement' in data
                        ? (data.net_settlement as number).toFixed(2)
                        : 'N/A'}
                  </TableCell>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      </div>

      {run && (
        <div className="glass-card p-4">
          <h3 className="font-body font-medium text-body text-text mb-4">Run Summary</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-caption text-text-muted">Scenario</p>
              <p className="font-mono text-body">{run.scenario_id}</p>
            </div>
            <div>
              <p className="text-caption text-text-muted">Controller</p>
              <p className="font-mono text-body">{run.controller_type}</p>
            </div>
            <div>
              <p className="text-caption text-text-muted">Start Time</p>
              <p className="font-mono text-body">{run.start_time ? new Date(run.start_time).toLocaleString() : 'N/A'}</p>
            </div>
            <div>
              <p className="text-caption text-text-muted">Status</p>
              <p className="font-mono text-body capitalize">{run.status}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ReportPageContent() {
  const { runId } = useParams<{ runId: string }>();
  const { runs, currentRun } = useSimulationStore();
  const { currentTask } = useAgentStore();
  const { addToast } = useToast();
  const [report, setReport] = useState<ReportResponse | null>(null);
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
        setReport({
          markdown: currentTask.report,
          kpi_blocks: {},
          detail_sections: {},
          run_id: '',
          scenario_id: '',
          controller_type: '',
          status: '',
          generation_status: 'ready',
          outcome_sentence: undefined,
          start_time: '',
          end_time: undefined,
        } as ReportResponse);
      } else {
        // Fallback to API
        const reportResponse = await api.getReport(runId!);
        setReport(reportResponse);
      }
    } catch (error) {
      console.error('Failed to load report:', error);
      addToast({ type: 'error', title: 'Failed to load report' });
      setReport({
        markdown: '# Report Not Available\n\nCould not load the report for this run.',
        kpi_blocks: {},
        detail_sections: {},
        run_id: '',
        scenario_id: '',
        controller_type: '',
        status: 'failed',
        generation_status: 'failed',
        outcome_sentence: undefined,
        start_time: '',
        end_time: undefined,
      } as ReportResponse);
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
            <Tabs defaultValue="report">
              <TabList className="mb-4">
                <Tab value="report">Report</Tab>
                <Tab value="settlement">Settlement</Tab>
              </TabList>

              <TabPanel value="report">
                <ReportView
                  report={report?.markdown || ''}
                  onDownload={handleDownload}
                />
              </TabPanel>

              <TabPanel value="settlement">
                <SettlementView
                  settlement={null}
                  run={run}
                />
              </TabPanel>
            </Tabs>
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