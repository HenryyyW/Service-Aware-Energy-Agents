import { useState } from 'react';
import { FileText, Download, Copy, CheckCircle, Eye, Edit } from 'lucide-react';
import { Button } from '../ui/Button';
import { useAgentStore } from '../../store/agentStore';
import { sanitizeMarkdown } from '../../utils/sanitize';

interface ReportViewProps {
  report?: string;
  onDownload?: (format: 'markdown') => void;
}

export function ReportView({ report, onDownload }: ReportViewProps) {
  const { currentTask } = useAgentStore();
  const taskReport = report || currentTask?.report;
  const [viewMode, setViewMode] = useState<'rendered' | 'source'>('rendered');

  if (!taskReport) {
    return (
      <div className="glass-card p-8 text-center text-text-muted">
        <FileText className="w-16 h-16 mx-auto mb-4 text-text-muted/30" />
        <p className="text-body">No report generated yet</p>
        <p className="text-caption mt-2">The reporter will produce a reproducible report with evidence</p>
      </div>
    );
  }

  return (
    <div className="glass-card flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-border/30">
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-comfort" />
          <span className="font-body font-medium text-body-sm text-text">Report</span>
          <span className="text-caption text-text-muted">
            {taskReport.split('\n').length} lines
          </span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant={viewMode === 'rendered' ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => setViewMode('rendered')}
          >
            <Eye className="w-4 h-4 mr-1" />
            Rendered
          </Button>
          <Button
            variant={viewMode === 'source' ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => setViewMode('source')}
          >
            <Edit className="w-4 h-4 mr-1" />
            Source
          </Button>
          <Button variant="ghost" size="icon" onClick={() => navigator.clipboard.writeText(taskReport)} aria-label="Copy report">
            <Copy className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="icon" onClick={() => onDownload?.('markdown')} aria-label="Download Markdown">
            <Download className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {viewMode === 'rendered' ? (
          <div 
            className="prose prose-invert max-w-none"
            dangerouslySetInnerHTML={{ __html: sanitizeMarkdown(taskReport) }}
          />
        ) : (
          <pre className="font-mono text-body-sm text-text leading-relaxed whitespace-pre-wrap">
            {taskReport}
          </pre>
        )}
      </div>

      {/* Status Bar */}
      <div className="flex items-center justify-between px-4 py-2 border-t border-border/30 bg-surface/50">
        <div className="flex items-center gap-4 text-caption text-text-muted">
          <span>{taskReport.length} characters</span>
          <span>{taskReport.split('\n').length} lines</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1 text-energy">
            <CheckCircle className="w-3 h-3" />
            Ready
          </span>
        </div>
      </div>
    </div>
  );
}