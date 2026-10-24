import { useState } from 'react';
import { FileText, Download, Copy, CheckCircle, Eye, Edit } from 'lucide-react';
import { Button } from '../ui/Button';
import { useAgentStore } from '../../store/agentStore';

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
          <div className="prose prose-invert max-w-none">
            {renderMarkdown(taskReport)}
          </div>
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

// Simple markdown renderer (in production, use react-markdown or similar)
function renderMarkdown(markdown: string): React.ReactNode {
  const lines = markdown.split('\n');
  const elements: React.ReactNode[] = [];

  let inCodeBlock = false;
  let codeBlockContent = '';
  let codeBlockLang = '';

  lines.forEach((line, index) => {
    if (line.startsWith('```')) {
      if (!inCodeBlock) {
        inCodeBlock = true;
        codeBlockLang = line.slice(3).trim();
        codeBlockContent = '';
      } else {
        inCodeBlock = false;
        elements.push(
          <pre key={index} className="bg-space rounded-lg p-4 overflow-x-auto my-3">
            <code className={`language-${codeBlockLang} font-mono text-body-sm text-text`}>
              {codeBlockContent.trim()}
            </code>
          </pre>
        );
      }
      return;
    }

    if (inCodeBlock) {
      codeBlockContent += line + '\n';
      return;
    }

    if (line.startsWith('# ')) {
      elements.push(<h1 key={index} className="font-display font-bold text-heading-1 text-text mt-6 mb-3">{line.slice(2)}</h1>);
    } else if (line.startsWith('## ')) {
      elements.push(<h2 key={index} className="font-display font-semibold text-heading-2 text-text mt-5 mb-2">{line.slice(3)}</h2>);
    } else if (line.startsWith('### ')) {
      elements.push(<h3 key={index} className="font-display font-medium text-heading-3 text-text mt-4 mb-2">{line.slice(4)}</h3>);
    }
    else if (line.startsWith('- ') || line.startsWith('* ')) {
      elements.push(<li key={index} className="ml-4 mb-1 text-text">{line.slice(2)}</li>);
    }
    else if (line.trim()) {
      elements.push(<p key={index} className="text-text mb-3">{line}</p>);
    }
    else {
      elements.push(<br key={index} />);
    }
  });

  return <div>{elements}</div>;
}