import { useState } from 'react';
import { clsx } from 'clsx';
import { Mic, Zap, Brain, RotateCcw, X } from 'lucide-react';
import { Button } from '../ui/Button';
import { Textarea } from '../ui/Input';
import { useAgentStore } from '../../store/agentStore';
import { api } from '../../api/client';

const exampleTasks = [
  {
    title: 'High EV Penetration',
    description: 'Create a renewable energy community with 15 buildings, rooftop PV, building batteries, and 50 EVs. Each EV must reach at least 80% SOC before 07:00. Limit total community grid import to 300 kW. Compare rule-based charging with coordinated agent-based policy.',
  },
  {
    title: 'PV Export Constraints',
    description: 'Increase PV capacity to 80% penetration. Apply feeder-level export limit of 200 kW. Evaluate voltage rise, reverse power flow, and curtailment. Test whether local storage and demand shifting reduce grid violations.',
  },
  {
    title: 'Local Energy Sharing',
    description: 'Enable community energy sharing with 10 buildings. Compare: no sharing, uniform price sharing, weighted importer/exporter settlement, and carbon-aware settlement. Report both community savings and distribution of savings among members.',
  },
  {
    title: 'Failure Recovery',
    description: 'Inject PV inverter failure at Building 3 during peak generation (12:00-14:00). Measure how quickly the system detects the issue, repairs the policy, and restores service. Compare with and without battery backup.',
  },
];

export function TaskInput() {
  const { currentTask, setCurrentTask, addTask, updateTaskStatus } = useAgentStore();
  const [taskDescription, setTaskDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showExamples, setShowExamples] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!taskDescription.trim() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      // Create agent task via API
      const task = await api.createAgentTask(taskDescription.trim());
      setCurrentTask(task);
      addTask(task);
      updateTaskStatus('planning');
      setTaskDescription('');
    } catch (error) {
      console.error('Failed to create agent task:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleExampleClick = (example: typeof exampleTasks[0]) => {
    setTaskDescription(example.description);
    setShowExamples(false);
  };

  const handleClear = () => {
    setCurrentTask(null);
    setTaskDescription('');
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="font-display font-semibold text-heading-2 text-text">Agent Workspace</h2>
        {currentTask && (
          <Button variant="ghost" size="icon" onClick={handleClear} aria-label="Clear task">
            <X className="w-4 h-4" />
          </Button>
        )}
      </div>

      {/* Task Input Form */}
      <form onSubmit={handleSubmit} className="space-y-3">
        <Textarea
          value={taskDescription}
          onChange={(e) => setTaskDescription(e.target.value)}
          placeholder="Describe the simulation task for the agent... e.g., 'Create a community with 10 buildings, rooftop PV, batteries, and 20 EVs. Each EV must reach 80% SOC before 07:00. Limit grid import to 200 kW. Compare rule-based vs coordinated charging.'"
          rows={4}
          className="font-body"
        />

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Button type="button" variant="ghost" size="icon" onClick={() => setShowExamples(!showExamples)} aria-label="Show examples">
              <Brain className="w-4 h-4" />
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => { /* voice input */ }} aria-label="Voice input" disabled>
              <Mic className="w-4 h-4 mr-1" />
              Voice
            </Button>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" type="button" onClick={() => setTaskDescription('')}>
              <RotateCcw className="w-4 h-4 mr-1" />
              Clear
            </Button>
            <Button
              variant="primary"
              type="submit"
              disabled={!taskDescription.trim() || isSubmitting}
              className="px-6"
            >
              {isSubmitting ? (
                <>
                  <div className="animate-spin w-4 h-4 mr-2 border-2 border-white/30 border-t-white rounded-full" />
                  Starting...
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4 mr-2" />
                  Run Agent
                </>
              )}
            </Button>
          </div>
        </div>
      </form>

      {/* Example Tasks */}
      {showExamples && (
        <div className="glass-card p-4 animate-slide-down">
          <h4 className="font-body font-medium text-body-sm text-text mb-3">Example Tasks</h4>
          <div className="grid gap-2 sm:grid-cols-2">
            {exampleTasks.map((example, i) => (
              <button
                key={i}
                onClick={() => handleExampleClick(example)}
                className="glass-card p-3 text-left hover:border-sun/50 transition-colors"
              >
                <p className="font-body font-medium text-body-sm text-text mb-1">{example.title}</p>
                <p className="text-caption text-text-muted">{example.description.slice(0, 100)}...</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Current Task Status */}
      {currentTask && (
        <div className="glass-card p-4">
          <div className="flex items-center gap-3 mb-3">
            <div className={clsx(
              'w-3 h-3 rounded-full',
              currentTask.status === 'completed' ? 'bg-energy' :
              currentTask.status === 'failed' ? 'bg-violation' :
              'bg-sun animate-pulse'
            )} />
            <div>
              <p className="font-body font-medium text-body text-text">
                Task: {currentTask.task_id.slice(0, 8)}...
              </p>
              <p className="text-caption text-text-muted capitalize">{currentTask.status}</p>
            </div>
            <div className="flex-1" />
            <span className="badge badge-sun">
              {currentTask.status === 'planning' && '📋 Planning'}
              {currentTask.status === 'coding' && '💻 Coding'}
              {currentTask.status === 'executing' && '▶️ Executing'}
              {currentTask.status === 'verifying' && '✅ Verifying'}
              {currentTask.status === 'repairing' && '🔧 Repairing'}
              {currentTask.status === 'reporting' && '📄 Reporting'}
              {currentTask.status === 'completed' && '✅ Completed'}
              {currentTask.status === 'failed' && '❌ Failed'}
            </span>
          </div>

          <div className="text-body-sm text-text-muted">
            {currentTask.description}
          </div>
        </div>
      )}

      {/* Task History */}
      {/* Would show recent tasks here */}
    </div>
  );
}