import { clsx } from 'clsx';
import { Clock, CheckCircle, Zap, Brain, Terminal, Shield, Wrench, FileText } from 'lucide-react';
import { useAgentStore, AGENT_TIMELINE_STEPS, getStepIndex } from '../../store/agentStore';
import { PlanView } from './PlanView';
import { CodeView } from './CodeView';
import { ExecutionLog } from './ExecutionLog';
import { VerificationView } from './VerificationView';
import { RepairView } from './RepairView';
import { ReportView } from './ReportView';

interface AgentTimelineProps {
  compact?: boolean;
}

export function AgentTimeline({ compact = false }: AgentTimelineProps) {
  const { currentTask, activeTimelineStep, setActiveTimelineStep } = useAgentStore();

  if (!currentTask) {
    return (
      <div className="glass-card p-8 text-center text-text-muted">
        <Brain className="w-16 h-16 mx-auto mb-4 text-text-muted/30" />
        <p className="text-body">No active agent task</p>
        <p className="text-caption mt-2">Submit a task to start the agent workflow</p>
      </div>
    );
  }

  const currentStepIndex = getStepIndex(currentTask.status);
  const isCompleted = currentTask.status === 'completed' || currentTask.status === 'failed';

  const stepComponents = {
    planner: <PlanView plan={currentTask.plan} activeStep={activeTimelineStep} />,
    coder: <CodeView code={currentTask.code} language="python" />,
    executor: <ExecutionLog logs={currentTask.execution_log} />,
    verifier: <VerificationView verification={currentTask.verification} />,
    repairer: <RepairView repairs={currentTask.repairs} />,
    reporter: <ReportView report={currentTask.report} />,
  };

  const activeStepComponent = stepComponents[AGENT_TIMELINE_STEPS[activeTimelineStep]?.id as keyof typeof stepComponents] || null;

  if (compact) {
    return (
      <div className="space-y-2">
        {/* Compact Timeline */}
        <div className="flex items-center gap-2 overflow-x-auto pb-2">
          {AGENT_TIMELINE_STEPS.map((step, index) => {
            const isActive = index === currentStepIndex;
            const isStepCompleted = index < currentStepIndex || (isCompleted && index <= currentStepIndex);
            const isSelected = index === activeTimelineStep;

            return (
              <button
                key={step.id}
                onClick={() => setActiveTimelineStep(index)}
                className={clsx(
                  'flex-shrink-0 flex items-center gap-2 px-3 py-2 rounded-lg text-body-sm font-medium transition-all duration-fast whitespace-nowrap',
                  isSelected ? 'bg-sun/20 border border-sun/30 text-sun' :
                  isStepCompleted ? 'bg-energy/10 border border-energy/30 text-energy' :
                  isActive ? 'bg-sun/10 border border-sun/30 text-sun' :
                  'bg-surface border border-border text-text-muted hover:bg-white/5'
                )}
                aria-current={isSelected ? 'step' : undefined}
              >
                <div className={clsx(
                  'flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center font-mono text-caption',
                  isStepCompleted ? 'bg-energy text-space' :
                  isActive ? 'bg-sun text-space animate-pulse' :
                  'bg-surface border border-border text-text-muted'
                )}>
                  {isStepCompleted ? <CheckCircle className="w-4 h-4" /> : index + 1}
                </div>
                <span>{step.label}</span>
                {index < AGENT_TIMELINE_STEPS.length - 1 && !isSelected && (
                  <div className={clsx('w-16 h-0.5 mx-1', isStepCompleted ? 'bg-energy' : 'bg-border')} />
                )}
              </button>
            );
          })}
        </div>

        {/* Active Step Content */}
        {activeStepComponent && (
          <div className="glass-card p-4 animate-fade-in">
            {activeStepComponent}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Timeline Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-display font-semibold text-heading-2 text-text">Agent Workflow</h2>
        <div className="flex items-center gap-2">
          <span className={clsx(
            'badge px-3 py-1',
            currentTask.status === 'completed' ? 'badge-energy' :
            currentTask.status === 'failed' ? 'badge-violation' :
            'badge-sun'
          )}>
            {currentTask.status.toUpperCase()}
          </span>
          {currentTask.status !== 'completed' && currentTask.status !== 'failed' && (
            <Clock className="w-5 h-5 text-sun animate-pulse" />
          )}
        </div>
      </div>

      {/* Full Timeline */}
      <div className="flex flex-1 gap-4">
        {/* Vertical Timeline */}
        <div className="flex-shrink-0 w-48">
          <div className="relative">
            {/* Timeline Line */}
            <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-border/30" />

            <div className="space-y-6">
              {AGENT_TIMELINE_STEPS.map((step, index) => {
                const isActive = index === currentStepIndex;
                const isStepCompleted = index < currentStepIndex || (isCompleted && index <= currentStepIndex);
                const isSelected = index === activeTimelineStep;
                const hasError = currentTask.status === 'failed' && index === currentStepIndex;

                const stepIcons = {
                  planner: Brain,
                  coder: FileText,
                  executor: Terminal,
                  verifier: Shield,
                  repairer: Wrench,
                  reporter: FileText,
                };

                const StepIcon = stepIcons[step.id as keyof typeof stepIcons] || Zap;

                return (
                  <button
                    key={step.id}
                    onClick={() => setActiveTimelineStep(index)}
                    className={clsx(
                      'relative flex flex-col items-start gap-2 transition-all duration-fast',
                      isSelected && 'opacity-100',
                      !isSelected && 'opacity-60 hover:opacity-100'
                    )}
                    aria-current={isSelected ? 'step' : undefined}
                  >
                    <div className={clsx(
                      'relative z-10 w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0',
                      isStepCompleted ? 'bg-energy text-space shadow-lg shadow-energy/25' :
                      isActive ? 'bg-sun text-space shadow-lg shadow-sun/25 animate-pulse' :
                      hasError ? 'bg-violation text-white shadow-lg shadow-violation/25' :
                      'bg-surface border-2 border-border text-text-muted'
                    )}>
                      {isStepCompleted ? <CheckCircle className="w-6 h-6" /> : <StepIcon className="w-6 h-6" />}
                    </div>

                    <div className={clsx(
                      'text-left min-w-0',
                      isSelected ? 'text-text' : 'text-text-muted'
                    )}>
                      <p className={clsx('font-body font-medium text-body-sm', isSelected && 'text-text')}>
                        {step.label}
                      </p>
                      <p className="text-caption line-clamp-1">{step.description}</p>
                    </div>

                    {index < AGENT_TIMELINE_STEPS.length - 1 && (
                      <div
                        className="absolute left-10 top-12 bottom-0 w-0.5"
                        style={{ background: isStepCompleted ? 'var(--color-energy)' : 'var(--color-border)' }}
                      />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Content Panel */}
        <div className="flex-1 min-w-0">
          {activeStepComponent ? (
            <div className="glass-card flex flex-col h-full animate-fade-in">
              <div className="p-4 border-b border-border/30 bg-surface/50">
                <h3 className="font-body font-medium text-body text-text">
                  {AGENT_TIMELINE_STEPS[activeTimelineStep].label}
                </h3>
                <p className="text-caption text-text-muted mt-0.5">
                  {AGENT_TIMELINE_STEPS[activeTimelineStep].description}
                </p>
              </div>
              <div className="flex-1 overflow-auto p-4">
                {activeStepComponent}
              </div>
            </div>
          ) : (
            <div className="glass-card p-8 text-center text-text-muted">
              <Zap className="w-12 h-12 mx-auto mb-3 text-text-muted/30" />
              <p className="text-body">Select a step to view details</p>
            </div>
          )}
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mt-4 pt-4 border-t border-border/30">
        <div className="flex items-center justify-between mb-2">
          <span className="text-caption text-text-muted">Overall Progress</span>
          <span className="font-mono text-data text-sun">
            {Math.round(((currentStepIndex + (isCompleted ? 1 : 0)) / AGENT_TIMELINE_STEPS.length) * 100)}%
          </span>
        </div>
        <div className="h-2 bg-surface rounded-full overflow-hidden">
          <div
            className="h-full bg-sun rounded-full transition-all duration-500 ease-spring"
            style={{ width: `${Math.min(100, ((currentStepIndex + (isCompleted ? 1 : 0)) / AGENT_TIMELINE_STEPS.length) * 100)}%` }}
          />
        </div>
      </div>
    </div>
  );
}