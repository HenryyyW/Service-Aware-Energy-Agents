import { create } from 'zustand';
import type { AgentTask } from '../api/types';

interface AgentState {
  // Current agent task
  currentTask: AgentTask | null;
  setCurrentTask: (task: AgentTask | null) => void;
  updateTaskStatus: (status: AgentTask['status']) => void;
  updateTaskField: (field: keyof AgentTask, value: any) => void;

  // Task history
  tasks: AgentTask[];
  setTasks: (tasks: AgentTask[]) => void;
  addTask: (task: AgentTask) => void;
  updateTask: (taskId: string, updates: Partial<AgentTask>) => void;

  // Active step in timeline (for UI)
  activeTimelineStep: number;
  setActiveTimelineStep: (step: number) => void;

  // WebSocket connection status
  wsConnected: boolean;
  setWsConnected: (connected: boolean) => void;
}

const TIMELINE_STEPS = [
  { id: 'planner', label: 'Planner', description: 'Parsing task, identifying assets & constraints' },
  { id: 'coder', label: 'Coder', description: 'Generating controller code & configuration' },
  { id: 'executor', label: 'Executor', description: 'Running CityLearn & pandapower simulation' },
  { id: 'verifier', label: 'Verifier', description: 'Checking physical, electrical & service validity' },
  { id: 'repairer', label: 'Repairer', description: 'Diagnosing failures & proposing patches' },
  { id: 'reporter', label: 'Reporter', description: 'Producing reproducible report with evidence' },
];

export const useAgentStore = create<AgentState>((set) => ({
  currentTask: null,
  setCurrentTask: (task) => set({ currentTask: task, activeTimelineStep: 0 }),
  updateTaskStatus: (status) => set((state) => ({
    currentTask: state.currentTask ? { ...state.currentTask, status } : null,
  })),
  updateTaskField: (field, value) => set((state) => ({
    currentTask: state.currentTask ? { ...state.currentTask, [field]: value } : null,
  })),

  tasks: [],
  setTasks: (tasks) => set({ tasks }),
  addTask: (task) => set((state) => ({ tasks: [task, ...state.tasks] })),
  updateTask: (taskId, updates) => set((state) => ({
    tasks: state.tasks.map(t => t.task_id === taskId ? { ...t, ...updates } : t),
    currentTask: state.currentTask?.task_id === taskId ? { ...state.currentTask, ...updates } : state.currentTask,
  })),

  activeTimelineStep: 0,
  setActiveTimelineStep: (step) => set({ activeTimelineStep: step }),

  wsConnected: false,
  setWsConnected: (connected) => set({ wsConnected: connected }),
}));

// Timeline steps configuration
export const AGENT_TIMELINE_STEPS = TIMELINE_STEPS;

export const getStepIndex = (status: AgentTask['status']): number => {
  const stepOrder = ['planning', 'coding', 'executing', 'verifying', 'repairing', 'reporting', 'completed'];
  return stepOrder.indexOf(status);
};