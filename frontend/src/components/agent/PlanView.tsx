import { clsx } from 'clsx';
import { FileText, Target, Zap, Settings, CheckCircle, Clock } from 'lucide-react';
import { useAgentStore, AGENT_TIMELINE_STEPS, getStepIndex } from '../../store/agentStore';
import type { AgentPlan } from '../../api/types';

interface PlanViewProps {
  plan?: AgentPlan;
  activeStep?: number;
}

export function PlanView({ plan, activeStep = 0 }: PlanViewProps) {
  const { currentTask } = useAgentStore();
  const taskPlan = plan || currentTask?.plan;

  if (!taskPlan) {
    return (
      <div className="glass-card p-8 text-center text-text-muted">
        <FileText className="w-16 h-16 mx-auto mb-4 text-text-muted/30" />
        <p className="text-body">No plan generated yet</p>
        <p className="text-caption mt-2">The planner will analyze the task and create a plan</p>
      </div>
    );
  }

  const currentStepIndex = getStepIndex(currentTask?.status || 'planning');

  return (
    <div className="space-y-4">
      {/* Timeline Steps */}
      <div className="space-y-3">
        {AGENT_TIMELINE_STEPS.map((step, index) => {
          const isActive = index === currentStepIndex;
          const isCompleted = index < currentStepIndex;
          const isCurrent = index === activeStep;

          return (
            <div
              key={step.id}
              className={clsx(
                'flex items-center gap-4 p-3 rounded-lg transition-colors',
                isActive && 'bg-sun/10 border border-sun/30',
                isCompleted && 'bg-energy/10 border border-energy/30',
                isCurrent && 'bg-sun/5 ring-1 ring-sun/30',
                !isActive && !isCompleted && 'hover:bg-white/5'
              )}
            >
              <div className={clsx(
                'flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center font-mono text-caption',
                isCompleted ? 'bg-energy text-space' :
                isActive ? 'bg-sun text-space' :
                'bg-surface border border-border text-text-muted'
              )}>
                {isCompleted ? <CheckCircle className="w-5 h-5" /> : index + 1}
              </div>
              <div className="flex-1 min-w-0">
                <p className={clsx('font-body text-body-sm', isActive || isCompleted ? 'text-text' : 'text-text-muted')}>
                  {step.label}
                </p>
                <p className={clsx('text-caption', isActive || isCompleted ? 'text-text-muted' : 'text-text-muted/50')}>
                  {step.description}
                </p>
              </div>
              {isActive && (
                <Clock className="w-5 h-5 text-sun animate-pulse" />
              )}
              {isCompleted && (
                <CheckCircle className="w-5 h-5 text-energy" />
              )}
            </div>
          );
        })}
      </div>

      {/* Plan Details */}
      <div className="glass-card p-4 space-y-4">
        <h3 className="font-body font-medium text-body text-text">Plan Details</h3>

        <div className="grid gap-4 sm:grid-cols-2">
          <PlanSection title="Assets Identified" icon={<Target className="w-5 h-5 text-sun" />}>
            {taskPlan.assets.length > 0 ? (
              <ul className="space-y-1">
                {taskPlan.assets.map((asset, i) => (
                  <li key={i} className="flex items-center gap-2 text-body-sm text-text">
                    <span className="w-2 h-2 rounded-full bg-sun/50" />
                    {asset}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-caption text-text-muted">No specific assets identified</p>
            )}
          </PlanSection>

          <PlanSection title="Constraints" icon={<Settings className="w-5 h-5 text-grid" />}>
            {taskPlan.constraints.length > 0 ? (
              <ul className="space-y-1">
                {taskPlan.constraints.map((constraint, i) => (
                  <li key={i} className="flex items-center gap-2 text-body-sm text-text">
                    <span className="w-2 h-2 rounded-full bg-grid/50" />
                    {constraint}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-caption text-text-muted">No constraints specified</p>
            )}
          </PlanSection>

          <PlanSection title="KPIs to Optimize" icon={<Zap className="w-5 h-5 text-energy" />}>
            {taskPlan.kpis.length > 0 ? (
              <ul className="space-y-1">
                {taskPlan.kpis.map((kpi, i) => (
                  <li key={i} className="flex items-center gap-2 text-body-sm text-text">
                    <span className="w-2 h-2 rounded-full bg-energy/50" />
                    {kpi.replace(/_/g, ' ')}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-caption text-text-muted">No KPIs specified</p>
            )}
          </PlanSection>

          <PlanSection title="Simulations Needed" icon={<FileText className="w-5 h-5 text-battery" />}>
            <p className="font-mono text-data text-2xl">{taskPlan.simulations_needed}</p>
            <p className="text-caption text-text-muted">Estimated: ~{taskPlan.estimated_duration_seconds}s</p>
          </PlanSection>
        </div>
      </div>
    </div>
  );
}

function PlanSection({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="glass-card p-4">
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <h4 className="font-body font-medium text-body-sm text-text">{title}</h4>
      </div>
      {children}
    </div>
  );
}