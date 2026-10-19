import { clsx } from 'clsx';
import { CheckCircle, AlertCircle, AlertTriangle, Shield, Zap, Battery, Car, FileText } from 'lucide-react';
import { useAgentStore } from '../../store/agentStore';
import type { VerificationResult } from '../../api/types';

interface VerificationViewProps {
  verification?: VerificationResult;
}

export function VerificationView({ verification }: VerificationViewProps) {
  const { currentTask } = useAgentStore();
  const taskVerification = verification || currentTask?.verification;

  if (!taskVerification) {
    return (
      <div className="glass-card p-8 text-center text-text-muted">
        <Shield className="w-16 h-16 mx-auto mb-4 text-text-muted/30" />
        <p className="text-body">No verification results yet</p>
        <p className="text-caption mt-2">The verifier will check physical, electrical, and service constraints</p>
      </div>
    );
  }

  const allPassed = taskVerification.passed;
  const totalViolations = taskVerification.violations.length;
  const errorCount = taskVerification.violations.filter(v => v.severity === 'error').length;
  const warningCount = taskVerification.violations.filter(v => v.severity === 'warning').length;

  return (
    <div className="space-y-4">
      {/* Overall Status */}
      <div className={clsx('glass-card p-4', allPassed ? 'border-energy/30' : 'border-violation/30')}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className={clsx('w-12 h-12 rounded-xl flex items-center justify-center', allPassed ? 'bg-energy/20' : 'bg-violation/20')}>
              {allPassed ? (
                <CheckCircle className="w-6 h-6 text-energy" />
              ) : (
                <AlertCircle className="w-6 h-6 text-violation" />
              )}
            </div>
            <div>
              <h3 className="font-display font-semibold text-body text-text">
                {allPassed ? 'Verification Passed' : 'Verification Failed'}
              </h3>
              <p className="text-caption text-text-muted">
                {totalViolations} issue{totalViolations !== 1 ? 's' : ''} found
                ({errorCount} error{errorCount !== 1 ? 's' : ''}, {warningCount} warning{warningCount !== 1 ? 's' : ''})
              </p>
            </div>
          </div>
          <div className="flex items-center gap-4 text-caption text-text-muted">
            <span className="flex items-center gap-1">
              <Shield className="w-3 h-3" />
              {allPassed ? 'All checks passed' : 'Issues require attention'}
            </span>
          </div>
        </div>
      </div>

      {/* Diagnostic Categories */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <DiagnosticCategory
          title="Physical"
          icon={<Zap className="w-5 h-5" />}
          items={taskVerification.diagnostics.physical}
          color="text-sun"
        />
        <DiagnosticCategory
          title="Electrical"
          icon={<Battery className="w-5 h-5" />}
          items={taskVerification.diagnostics.electrical}
          color="text-battery"
        />
        <DiagnosticCategory
          title="Service"
          icon={<Car className="w-5 h-5" />}
          items={taskVerification.diagnostics.service}
          color="text-ev"
        />
        <DiagnosticCategory
          title="Reporting"
          icon={<FileText className="w-5 h-5" />}
          items={taskVerification.diagnostics.reporting}
          color="text-comfort"
        />
      </div>

      {/* Violations List */}
      {totalViolations > 0 && (
        <div className="glass-card">
          <div className="p-4 border-b border-border/30">
            <h3 className="font-body font-medium text-body text-text">Violations</h3>
          </div>
          <div className="divide-y divide-border/30">
            {taskVerification.violations.map((violation, index) => {
              const severity = violation.severity;
              const isError = severity === 'error';
              return (
                <div key={index} className="p-4 flex items-start gap-3">
                  <div className={clsx(
                    'flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center',
                    isError ? 'bg-violation/20' : 'bg-sun/20'
                  )}>
                    {isError ? (
                      <AlertCircle className={clsx('w-5 h-5', isError ? 'text-violation' : 'text-sun')} />
                    ) : (
                      <AlertTriangle className={clsx('w-5 h-5', isError ? 'text-violation' : 'text-sun')} />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-body text-body-sm text-text">{violation.message}</p>
                    <p className="text-caption text-text-muted capitalize">{violation.type} • {severity}</p>
                  </div>
                  <span className={clsx(
                    'badge px-2 py-1 text-caption',
                    isError ? 'badge-violation' : 'badge-sun'
                  )}>
                    {severity.toUpperCase()}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {allPassed && (
        <div className="glass-card p-6 text-center">
          <CheckCircle className="w-12 h-12 mx-auto mb-3 text-energy" />
          <h3 className="font-body font-medium text-body text-text mb-1">All Checks Passed</h3>
          <p className="text-caption text-text-muted">
            Physical constraints, electrical limits, service requirements, and reporting standards are all satisfied.
          </p>
        </div>
      )}
    </div>
  );
}

function DiagnosticCategory({ title, icon, items, color }: {
  title: string;
  icon: React.ReactNode;
  items: string[];
  color: string;
}) {
  return (
    <div className="glass-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className={clsx('p-2 rounded-lg', `${color}/20`)}>{icon}</span>
        <h4 className="font-body font-medium text-body-sm text-text">{title}</h4>
      </div>
      {items.length > 0 ? (
        <ul className="space-y-2">
          {items.map((item, i) => (
            <li key={i} className="flex items-start gap-2 text-body-sm text-text">
              <CheckCircle className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: `var(--color-${color.replace('text-', '')})` }} />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-caption text-text-muted">No issues</p>
      )}
    </div>
  );
}