import { useTranslation } from 'react-i18next';
import { useToast } from '../ui/Toast';
import { Button } from '../ui/Button';
import { Copy } from 'lucide-react';

interface CopySummaryButtonProps {
  report: {
    outcome_sentence?: string | null;
    kpi_blocks: Record<string, any>;
  } | null;
}

export function CopySummaryButton({ report }: CopySummaryButtonProps) {
  const { t } = useTranslation('report');
  const { addToast } = useToast();

  const handleCopy = () => {
    if (!report) return;
    const lines = [
      report.outcome_sentence || '',
      '',
      'KPIs:',
      ...Object.entries(report.kpi_blocks || {}).flatMap(([category, metrics]) => [
        `${category.toUpperCase()}:`,
        ...Object.entries(metrics || {}).map(([key, value]) =>
          `  ${key.replace(/_/g, ' ')}: ${typeof value === 'number' ? value.toFixed(2) : value}`
        ),
      ]),
    ].filter(Boolean);

    const text = lines.join('\n');
    navigator.clipboard.writeText(text);
    addToast({ type: 'success', title: t('actions.copied'), duration: 2000 });
  };

  if (!report) return null;

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={handleCopy}
      className="flex items-center gap-2"
    >
      <Copy className="w-4 h-4" />
      <span>{t('actions.copySummary')}</span>
    </Button>
  );
}