import { create } from 'zustand';
import type { TimeStepData, TimePlayerState, SimulationRun } from '../api/types';

interface SimulationState {
  // Current run
  currentRun: SimulationRun | null;
  setCurrentRun: (run: SimulationRun | null) => void;

  // Trajectory data
  trajectories: TimeStepData[];
  setTrajectories: (data: TimeStepData[] | ((prev: TimeStepData[]) => TimeStepData[])) => void;

  // Time player state
  timePlayer: TimePlayerState;
  setTimePlayer: (player: Partial<TimePlayerState>) => void;
  setCurrentTimestep: (timestep: number) => void;
  play: () => void;
  pause: () => void;
  stepForward: () => void;
  stepBackward: () => void;
  setSpeed: (speed: 1 | 2 | 4) => void;
  reset: () => void;

  // Current timestep data (derived)
  currentStepData: TimeStepData | null;
  getCurrentStepData: () => TimeStepData | null;

  // Building IDs in current run
  buildingIds: string[];
  setBuildingIds: (ids: string[]) => void;

  // Available runs
  runs: SimulationRun[];
  setRuns: (runs: SimulationRun[]) => void;
  addRun: (run: SimulationRun) => void;
  updateRun: (runId: string, updates: Partial<SimulationRun>) => void;
}

const DEFAULT_TIME_PLAYER: TimePlayerState = {
  currentTimestep: 0,
  minTimestep: 0,
  maxTimestep: 0,
  playing: false,
  speed: 1,
  totalTimesteps: 0,
};

export const useSimulationStore = create<SimulationState>((set, get) => ({
  currentRun: null,
  setCurrentRun: (run) => set({ currentRun: run }),

  trajectories: [],
  setTrajectories: (trajectoriesOrFn: TimeStepData[] | ((prev: TimeStepData[]) => TimeStepData[])) => {
    set((state) => {
      const newTrajectories = typeof trajectoriesOrFn === 'function'
        ? trajectoriesOrFn(state.trajectories)
        : trajectoriesOrFn;
      if (newTrajectories.length > 0) {
        const minTimestep = Math.min(...newTrajectories.map((t: TimeStepData) => t.timestep));
        const maxTimestep = Math.max(...newTrajectories.map((t: TimeStepData) => t.timestep));
        const buildingIds: string[] = Array.from(new Set(
          newTrajectories.flatMap((t: TimeStepData) => Object.keys(t.observations)
            .map((key) => key.match(/^(building_\d+)_/)?.[1])
            .filter((id): id is string => Boolean(id))
          )
        )).sort();

        return {
          trajectories: newTrajectories,
          timePlayer: {
            ...DEFAULT_TIME_PLAYER,
            minTimestep,
            maxTimestep,
            currentTimestep: minTimestep,
            totalTimesteps: maxTimestep - minTimestep + 1,
          },
          buildingIds,
        };
      } else {
        return { trajectories: newTrajectories, buildingIds: [] };
      }
    });
  },

  timePlayer: DEFAULT_TIME_PLAYER,
  setTimePlayer: (player) => set((state) => ({ timePlayer: { ...state.timePlayer, ...player } })),
  setCurrentTimestep: (timestep) => set((state) => ({
    timePlayer: { ...state.timePlayer, currentTimestep: Math.max(state.timePlayer.minTimestep, Math.min(state.timePlayer.maxTimestep, timestep)) }
  })),
  play: () => set((state) => ({ timePlayer: { ...state.timePlayer, playing: true } })),
  pause: () => set((state) => ({ timePlayer: { ...state.timePlayer, playing: false } })),
  stepForward: () => set((state) => ({
    timePlayer: { ...state.timePlayer, currentTimestep: Math.min(state.timePlayer.maxTimestep, state.timePlayer.currentTimestep + 1) }
  })),
  stepBackward: () => set((state) => ({
    timePlayer: { ...state.timePlayer, currentTimestep: Math.max(state.timePlayer.minTimestep, state.timePlayer.currentTimestep - 1) }
  })),
  setSpeed: (speed) => set((state) => ({ timePlayer: { ...state.timePlayer, speed } })),
  reset: () => set((state) => ({ timePlayer: { ...state.timePlayer, currentTimestep: state.timePlayer.minTimestep, playing: false } })),

  getCurrentStepData: () => {
    const { trajectories, timePlayer } = get();
    return trajectories.find(t => t.timestep === timePlayer.currentTimestep) || null;
  },

  currentStepData: null,

  buildingIds: [],
  setBuildingIds: (ids) => set({ buildingIds: ids }),

  runs: [],
  setRuns: (runs) => set({ runs }),
  addRun: (run) => set((state) => ({ runs: [run, ...state.runs] })),
  updateRun: (runId, updates) => set((state) => ({
    runs: state.runs.map(r => r.run_id === runId ? { ...r, ...updates } : r),
    currentRun: state.currentRun?.run_id === runId ? { ...state.currentRun, ...updates } : state.currentRun,
  })),
}));

// Selector for current step data (reactive)
export const useCurrentStepData = () => {
  const trajectories = useSimulationStore((state) => state.trajectories);
  const currentTimestep = useSimulationStore((state) => state.timePlayer.currentTimestep);
  return trajectories.find(t => t.timestep === currentTimestep) || null;
};