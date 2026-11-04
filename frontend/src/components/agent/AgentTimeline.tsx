import { useEffect, useRef } from 'react';
import { clsx } from 'clsx';
import { Clock, CheckCircle, Zap, Brain, Terminal, Shield, Wrench, FileText, AlertTriangle } from 'lucide-react';
import { useAgentStore, AGENT_TIMELINE_STEPS, getStepIndex } from '../../store/agentStore';
import { PlanView } from './PlanView';
import { CodeView } from './CodeView';
import { ExecutionLog } from './ExecutionLog';
import { VerificationView } from './VerificationView';
import { RepairView } from './RepairView';
import { ReportView } from './ReportView';

interface AgentTimelineProps {
  compact?: boolean;
  /** Full view layout: 'rail' (default) horizontal track, 'vertical' legacy list. */
  variant?: 'rail' | 'vertical';
}

type StepState = 'done' | 'active' | 'error' | 'pending';

const STEP_ICONS = {
  planner: Brain,
  coder: FileText,
  executor: Terminal,
  verifier: Shield,
  repairer: Wrench,
  reporter: FileText,
} as const;

const STEP_COUNT = AGENT_TIMELINE_STEPS.length;

function getStepState(
  index: number,
  currentStepIndex: number,
  isCompleted: boolean,
  errorIndex: number,
): StepState {
  if (index === errorIndex) return 'error';
  if (index < currentStepIndex || (isCompleted && index <= currentStepIndex)) return 'done';
  if (index === currentStepIndex) return 'active';
  return 'pending';
}

const NODE_STYLES: Record<StepState, string> = {
  done: 'bg-energy text-space shadow-lg shadow-energy/25',
  active: 'bg-sun text-space shadow-lg shadow-sun/25 animate-pulse',
  error: 'bg-violation text-white shadow-lg shadow-violation/25',
  pending: 'bg-surface border-2 border-border text-text-muted',
};

export function AgentTimeline({ compact = false, variant = 'rail' }: AgentTimelineProps) {
  const { currentTask, activeTimelineStep, setActiveTimelineStep } = useAgentStore();

  const nodeRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const currentStepIndex = currentTask ? getStepIndex(currentTask.status) : -1;

  // Keep the live step in view while the workflow advances on narrow screens.
  useEffect(() => {
    if (compact || variant !== 'rail') return;
    const node = nodeRefs.current[Math.max(0, currentStepIndex)];
    node?.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
  }, [compact, variant, currentStepIndex]);

  if (!currentTask) {
    return (
      <div className="glass-card p-8 text-center text-text-muted">
        <Brain className="w-16 h-16 mx-auto mb-4 text-text-muted/30" />
        <p className="text-body">No active agent task</p>
        <p className="text-caption mt-2">Submit a task to start the agent workflow</p>
      </div>
    );
  }

  const isCompleted = currentTask.status === 'completed' || currentTask.status === 'failed';
  // Failed tasks route to the Repairer step — surface the error state there
  // ('failed' itself maps to no step index).
  const errorIndex = currentTask.status === 'failed' ? getStepIndex('repairing') : -1;
  const progress = Math.min(
    100,
    ((currentStepIndex + (isCompleted ? 1 : 0)) / STEP_COUNT) * 100,
  );

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
            const state = getStepState(index, currentStepIndex, isCompleted, errorIndex);
            const isSelected = index === activeTimelineStep;

            return (
              <button
                key={step.id}
                onClick={() => setActiveTimelineStep(index)}
                className={clsx(
                  'flex-shrink-0 flex items-center gap-2 px-3 py-2 rounded-lg text-body-sm font-medium transition-all duration-fast whitespace-nowrap',
                  isSelected ? 'bg-sun/20 border border-sun/30 text-sun' :
                  state === 'done' ? 'bg-energy/10 border border-energy/30 text-energy' :
                  state === 'active' ? 'bg-sun/10 border border-sun/30 text-sun' :
                  'bg-surface border border-border text-text-muted hover:bg-white/5'
                )}
                aria-current={isSelected ? 'step' : undefined}
              >
                <div className={clsx(
                  'flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center font-mono text-caption',
                  state === 'done' ? 'bg-energy text-space' :
                  state === 'active' ? 'bg-sun text-space animate-pulse' :
                  state === 'error' ? 'bg-violation text-white' :
                  'bg-surface border border-border text-text-muted'
                )}>
                  {state === 'done' ? <CheckCircle className="w-4 h-4" /> :
                   state === 'error' ? <AlertTriangle className="w-4 h-4" /> :
                   index + 1}
                </div>
                <span>{step.label}</span>
                {index < STEP_COUNT - 1 && !isSelected && (
                  <div className={clsx('w-16 h-0.5 mx-1', state === 'done' ? 'bg-energy' : 'bg-border')} />
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

  // Header shared by both full-view variants.
  const header = (
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
  );

  if (variant === 'vertical') {
    return (
      <div className="flex flex-col h-full">
        {header}

        <div className="flex flex-1 gap-4">
          {/* Vertical Timeline (legacy) */}
          <div className="flex-shrink-0 w-48">
            <div className="relative">
              {/* Timeline Line */}
              <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-border/30" />

              <div className="space-y-6">
                {AGENT_TIMELINE_STEPS.map((step, index) => {
                  const state = getStepState(index, currentStepIndex, isCompleted, errorIndex);
                  const isSelected = index === activeTimelineStep;
                  const StepIcon = STEP_ICONS[step.id as keyof typeof STEP_ICONS] || Zap;

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
                        NODE_STYLES[state]
                      )}>
                        {state === 'done' ? <CheckCircle className="w-6 h-6" /> :
                         state === 'error' ? <AlertTriangle className="w-6 h-6" /> :
                         <StepIcon className="w-6 h-6" />}
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

                      {index < STEP_COUNT - 1 && (
                        <div
                          className="absolute left-10 top-12 bottom-0 w-0.5"
                          style={{ background: state === 'done' ? 'var(--color-energy)' : 'var(--color-border)' }}
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
            <span className="font-mono text-data text-sun">{Math.round(progress)}%</span>
          </div>
          <div className="h-2 bg-surface rounded-full overflow-hidden">
            <div
              className="h-full bg-sun rounded-full transition-all duration-500 ease-spring"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {header}

      {/* Horizontal Rail */}
      <nav aria-label="Agent workflow steps" className="relative mb-6">
        <div className="overflow-x-auto pb-2 -mx-1 px-1">
          <div className="relative min-w-[40rem]">
            {/* Track line behind the nodes: connects the first and last node centres */}
            <div className="absolute left-12 right-12 top-6 h-0.5 bg-border/30" aria-hidden="true">
              <div
                className={clsx(
                  'h-full transition-all duration-500 ease-spring',
                  currentTask.status === 'failed' ? 'bg-violation' :
                  isCompleted ? 'bg-energy' : 'bg-sun'
                )}
                style={{ width: `${progress}%` }}
              />
            </div>

            <div className="relative flex justify-between">
              {AGENT_TIMELINE_STEPS.map((step, index) => {
                const state = getStepState(index, currentStepIndex, isCompleted, errorIndex);
                const isSelected = index === activeTimelineStep;
                const StepIcon = STEP_ICONS[step.id as keyof typeof STEP_ICONS] || Zap;

                return (
                  <button
                    key={step.id}
                    ref={(el) => { nodeRefs.current[index] = el; }}
                    onClick={() => setActiveTimelineStep(index)}
                    title={step.description}
                    aria-current={isSelected ? 'step' : undefined}
                    className={clsx(
                      'group relative z-10 flex w-24 flex-shrink-0 cursor-pointer flex-col items-center gap-2 rounded-lg px-1 pt-1 pb-2 transition-all duration-fast',
                      'focus:outline-none',
                      isSelected ? 'opacity-100' : 'opacity-60 hover:opacity-100'
                    )}
                  >
                    <div className={clsx(
                      'w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0 transition-shadow duration-fast',
                      NODE_STYLES[state],
                      isSelected && 'ring-2 ring-sun ring-offset-2 ring-offset-space'
                    )}>
                      {state === 'done' ? <CheckCircle className="w-6 h-6" /> :
                       state === 'error' ? <AlertTriangle className="w-6 h-6" /> :
                       <StepIcon className="w-6 h-6" />}
                    </div>

                    <div className="text-center min-w-0">
                      <p className={clsx(
                        'font-body font-medium text-body-sm',
                        isSelected || state === 'active' ? 'text-text' : 'text-text-muted',
                        state === 'error' && 'text-violation'
                      )}>
                        {step.label}
                      </p>
                      <p className="hidden sm:block text-caption text-text-muted line-clamp-2 normal-case tracking-normal mt-0.5">
                        {step.description}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </nav>

      {/* Detail Panel */}
      <div className="flex-1 min-h-0">
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

      {/* Progress Bar */}
      <div className="mt-4 pt-4 border-t border-border/30">
        <div className="flex items-center justify-between mb-2">
          <span className="text-caption text-text-muted">Overall Progress</span>
          <span className="font-mono text-data text-sun">{Math.round(progress)}%</span>
        </div>
        <div className="h-2 bg-surface rounded-full overflow-hidden">
          <div
            className="h-full bg-sun rounded-full transition-all duration-500 ease-spring"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
    </div>
  );
}
