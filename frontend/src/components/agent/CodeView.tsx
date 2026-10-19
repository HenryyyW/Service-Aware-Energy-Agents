import { useState } from 'react';
import { clsx } from 'clsx';
import { FileCode, Copy, Download, Check, X, RotateCcw } from 'lucide-react';
import { Button } from '../ui/Button';
import { useAgentStore } from '../../store/agentStore';

interface CodeViewProps {
  code?: string;
  language?: 'python' | 'yaml' | 'json';
  readOnly?: boolean;
  onSave?: (code: string) => void;
}

export function CodeView({ code, language = 'python', readOnly = true, onSave }: CodeViewProps) {
  const { currentTask } = useAgentStore();
  const taskCode = code || currentTask?.code;
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (taskCode) {
      navigator.clipboard.writeText(taskCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDownload = () => {
    if (taskCode) {
      const blob = new Blob([taskCode], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `controller_${currentTask?.task_id?.slice(0, 8) || 'generated'}.${language}`;
      a.click();
      URL.revokeObjectURL(url);
    }
  };

  if (!taskCode) {
    return (
      <div className="glass-card p-8 text-center text-text-muted">
        <FileCode className="w-16 h-16 mx-auto mb-4 text-text-muted/30" />
        <p className="text-body">No code generated yet</p>
        <p className="text-caption mt-2">The coder will generate controller code based on the plan</p>
      </div>
    );
  }

  const languageColors = {
    python: 'text-sun',
    yaml: 'text-energy',
    json: 'text-battery',
  };

  return (
    <div className="glass-card flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-border/30">
        <div className="flex items-center gap-2">
          <FileCode className={clsx('w-5 h-5', languageColors[language])} />
          <span className="font-body font-medium text-body-sm text-text capitalize">{language}</span>
          <span className="text-caption text-text-muted">
            {taskCode.split('\n').length} lines
          </span>
        </div>
        <div className="flex items-center gap-1">
          {!readOnly && onSave && (
            <Button variant="ghost" size="icon" onClick={() => onSave(taskCode)} aria-label="Save">
              <Check className="w-4 h-4" />
            </Button>
          )}
          <Button variant="ghost" size="icon" onClick={handleCopy} aria-label={copied ? 'Copied!' : 'Copy'}>
            {copied ? <Check className="w-4 h-4 text-energy" /> : <Copy className="w-4 h-4" />}
          </Button>
          <Button variant="ghost" size="icon" onClick={handleDownload} aria-label="Download">
            <Download className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Code Editor */}
      <div className="flex-1 overflow-auto p-3">
        <pre className="font-mono text-body-sm text-text leading-relaxed">
          <code className={clsx('language-' + language)}>
            {highlightCode(taskCode, language)}
          </code>
        </pre>
      </div>

      {/* Status Bar */}
      <div className="flex items-center justify-between px-3 py-2 border-t border-border/30 bg-surface/50">
        <div className="flex items-center gap-4 text-caption text-text-muted">
          <span>Ln {taskCode.split('\n').length}</span>
          <span>Col 1</span>
          <span>{language}</span>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" aria-label="Format code">
            <RotateCcw className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="icon" aria-label="Lint">
            <X className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}

// Simple syntax highlighting (in production, use Prism.js or similar)
function highlightCode(code: string, _language: string): string {
  // This is a placeholder - in production, use a proper syntax highlighter
  return code
    .replace(/&/g, '&')
    .replace(/</g, '<')
    .replace(/>/g, '>')
    .replace(/(".*?"|'.*?')/g, '<span class="text-sun">$1</span>')
    .replace(/(\b(def|class|import|from|return|if|else|elif|for|while|try|except|with|as|pass|break|continue|yield|lambda|and|or|not|in|is|None|True|False)\b)/g, '<span class="text-ev">$1</span>')
    .replace(/(#.*$)/gm, '<span class="text-text-muted">$1</span>');
}