import { useEffect } from 'react';
import { useAgentStore } from '../store/agentStore';
import { api } from '../api/client';
import { TaskInput } from '../components/agent/TaskInput';
import { AgentTimeline } from '../components/agent/AgentTimeline';
import { ToastProvider } from '../components/ui/Toast';

function AgentWorkspacePageContent() {
  const { currentTask, tasks, setCurrentTask } = useAgentStore();

  useEffect(() => {
    // Load existing agent tasks
    const loadTasks = async () => {
      try {
        await api.getAgentTasks();
        // Would populate agent store
      } catch (error) {
        console.error('Failed to load agent tasks:', error);
      }
    };
    loadTasks();
  }, []);

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-border/30 bg-surface/50">
        <h1 className="font-display font-semibold text-heading-1 text-text">Agent Workspace</h1>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Task Input */}
        <div className="w-96 flex-shrink-0 border-r border-border/30 bg-surface/30">
          <div className="p-4 h-full overflow-auto">
            <TaskInput />
          </div>
        </div>

        {/* Right: Timeline */}
        <div className="flex-1 min-w-0">
          <div className="p-4 h-full">
            {currentTask ? (
              <AgentTimeline compact={false} />
            ) : (
              <div className="h-full flex items-center justify-center text-text-muted">
                <div className="text-center">
                  <p className="text-body mb-2">No active agent task</p>
                  <p className="text-caption">Submit a task from the panel to start the workflow</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Task History */}
      {tasks.length > 0 && (
        <div className="border-t border-border/30 bg-surface/30">
          <div className="p-4">
            <h3 className="font-body font-medium text-body-sm text-text mb-3">Recent Tasks</h3>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {tasks.slice(0, 8).map((task) => (
                <button
                  key={task.task_id}
                  onClick={() => setCurrentTask(task)}
                  className="glass-card p-3 text-left hover:border-sun/50 transition-colors"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-data text-xs">{task.task_id.slice(0, 8)}</span>
                    <span className={[
                      'badge px-2 py-0.5 text-caption',
                      task.status === 'completed' && 'badge-energy',
                      task.status === 'failed' && 'badge-violation',
                      task.status === 'planning' && 'badge-sun',
                      task.status === 'coding' && 'badge-battery',
                      task.status === 'executing' && 'badge-ev',
                      task.status === 'verifying' && 'badge-grid',
                      task.status === 'repairing' && 'badge-load',
                      task.status === 'reporting' && 'badge-comfort',
                    ].filter(Boolean).join(' ')}>
                      {task.status}
                    </span>
                  </div>
                  <p className="text-caption text-text-muted line-clamp-2">{task.description}</p>
                  <p className="text-caption text-text-muted/50 mt-1">{new Date(task.created_at).toLocaleString()}</p>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function AgentWorkspacePage() {
  return (
    <ToastProvider>
      <AgentWorkspacePageContent />
    </ToastProvider>
  );
}