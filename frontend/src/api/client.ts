import axios, { type AxiosInstance, type AxiosError } from 'axios';
import type {
  ScenarioConfig,
  SimulationRun,
  TimeStepData,
  AgentTask,
  WebSocketMessage,
  NetworkGeometry,
  AssetMetadata,
  ReportResponse,
} from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';
const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`;

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 30000,
    });

    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        console.error('API Error:', error.response?.data || error.message);
        return Promise.reject(error);
      }
    );
  }

  // Scenario endpoints
  async getScenarios(): Promise<ScenarioConfig[]> {
    const response = await this.client.get('/api/scenarios');
    return response.data;
  }

  async getScenario(scenarioId: string): Promise<ScenarioConfig> {
    const response = await this.client.get(`/api/scenarios/${scenarioId}`);
    return response.data;
  }

  async createScenario(scenario: ScenarioConfig): Promise<ScenarioConfig> {
    const response = await this.client.post('/api/scenarios', {
      scenario_id: scenario.scenario_id,
      name: scenario.name || scenario.community.name,
      description: scenario.description || '',
      config: scenario,
    });
    return response.data;
  }

  async updateScenario(scenarioId: string, scenario: Partial<ScenarioConfig>): Promise<ScenarioConfig> {
    const response = await this.client.patch(`/api/scenarios/${scenarioId}`, scenario);
    return response.data;
  }

  async deleteScenario(scenarioId: string): Promise<void> {
    await this.client.delete(`/api/scenarios/${scenarioId}`);
  }

  // Network geometry endpoints
  async getNetworkGeometry(scenarioId: string): Promise<NetworkGeometry> {
    const response = await this.client.get('/api/network/geometry', {
      params: { scenario_id: scenarioId }
    });
    return response.data;
  }

  async getAssetMetadata(scenarioId: string): Promise<AssetMetadata> {
    const response = await this.client.get(`/api/network/asset-metadata/${scenarioId}`);
    return response.data;
  }

  // Simulation endpoints
  async getRuns(): Promise<SimulationRun[]> {
    const response = await this.client.get('/api/simulations');
    return response.data;
  }

  async getRun(runId: string): Promise<SimulationRun> {
    const response = await this.client.get(`/api/simulations/${runId}`);
    return response.data;
  }

  async runSimulation(scenarioId: string, controllerType: string, params?: Record<string, any>): Promise<SimulationRun> {
    const response = await this.client.post('/api/simulations', {
      scenario_id: scenarioId,
      controller_type: controllerType,
      parameters: params,
    });
    return response.data;
  }

  async getTrajectories(runId: string): Promise<TimeStepData[]> {
    const response = await this.client.get(`/api/simulations/${runId}/trajectories`);
    return response.data;
  }

  async getGridDiagnostics(runId: string): Promise<TimeStepData[]> {
    const response = await this.client.get(`/api/simulations/${runId}/grid`);
    return response.data;
  }

  // Agent endpoints
  async getAgentTasks(): Promise<AgentTask[]> {
    const response = await this.client.get('/api/agent/tasks');
    return response.data;
  }

  async createAgentTask(description: string): Promise<AgentTask> {
    const response = await this.client.post('/api/agent/tasks', { description });
    return response.data;
  }

  async getAgentTask(taskId: string): Promise<AgentTask> {
    const response = await this.client.get(`/api/agent/tasks/${taskId}`);
    return response.data;
  }

  // Report endpoints
  async getReport(runId: string): Promise<ReportResponse> {
    const response = await this.client.get(`/api/reports/${runId}`);
    return response.data;
  }

  async downloadReport(runId: string, format: 'markdown'): Promise<Blob> {
    const response = await this.client.get(`/api/reports/${runId}/download`, {
      params: { format },
      responseType: 'blob',
    });
    return response.data;
  }

  // Comparison endpoints
  async compareRuns(runIdA: string, runIdB: string): Promise<any> {
    const response = await this.client.get('/api/compare', {
      params: { run_id_a: runIdA, run_id_b: runIdB },
    });
    return response.data;
  }
}

export const api = new ApiClient();

// WebSocket connection state
export interface WebSocketConnectionState {
  isConnected: boolean;
  isReconnecting: boolean;
  lastMessageTime: number | null;
  stale: boolean;
  reconnectAttempts: number;
}

// WebSocket connection manager
export class WebSocketManager {
  private ws: WebSocket | null = null;
  private messageHandlers: Map<string, Set<(payload: any, meta?: WebSocketMessage['meta']) => void>> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private connectionState: WebSocketConnectionState = {
    isConnected: false,
    isReconnecting: false,
    lastMessageTime: null,
    stale: false,
    reconnectAttempts: 0,
  };
  private stateListeners: Set<(state: WebSocketConnectionState) => void> = new Set();
  private staleCheckInterval: number | null = null;
  private readonly STALE_THRESHOLD = 5000; // 5 seconds

  connect(runId?: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const url = runId
        ? `${WS_BASE_URL}/ws/simulation/${runId}`
        : `${WS_BASE_URL}/ws`;

      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        this.updateConnectionState({
          isConnected: true,
          isReconnecting: false,
          reconnectAttempts: 0,
        });
        this.startStaleCheck();
        resolve();
      };

      this.ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          const now = Date.now();
          this.updateConnectionState({
            lastMessageTime: now,
            stale: false,
          });
          this.dispatchMessage(message.type, message.payload, message.meta);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        reject(error);
      };

      this.ws.onclose = () => {
        console.log('WebSocket disconnected');
        this.updateConnectionState({
          isConnected: false,
        });
        this.stopStaleCheck();
        this.attemptReconnect(runId);
      };
    });
  }

  private updateConnectionState(partial: Partial<WebSocketConnectionState>) {
    this.connectionState = { ...this.connectionState, ...partial };
    this.stateListeners.forEach((listener) => listener(this.connectionState));
  }

  private startStaleCheck() {
    this.stopStaleCheck();
    this.staleCheckInterval = window.setInterval(() => {
      if (this.connectionState.lastMessageTime) {
        const timeSinceLastMessage = Date.now() - this.connectionState.lastMessageTime;
        if (timeSinceLastMessage > this.STALE_THRESHOLD && !this.connectionState.stale) {
          this.updateConnectionState({ stale: true });
        }
      }
    }, 1000);
  }

  private stopStaleCheck() {
    if (this.staleCheckInterval !== null) {
      clearInterval(this.staleCheckInterval);
      this.staleCheckInterval = null;
    }
  }

  private attemptReconnect(runId?: string) {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      this.updateConnectionState({
        isReconnecting: true,
        reconnectAttempts: this.reconnectAttempts,
      });
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
      console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
      setTimeout(() => this.connect(runId), delay);
    } else {
      this.updateConnectionState({
        isReconnecting: false,
      });
    }
  }

  private dispatchMessage(type: string, payload: any, meta?: WebSocketMessage['meta']) {
    const handlers = this.messageHandlers.get(type);
    if (handlers) {
      handlers.forEach((handler) => handler(payload, meta));
    }
    // Also dispatch to wildcard handlers
    const wildcardHandlers = this.messageHandlers.get('*');
    if (wildcardHandlers) {
      wildcardHandlers.forEach((handler) => handler({ type, payload }, meta));
    }
  }

  on(messageType: string, handler: (payload: any, meta?: WebSocketMessage['meta']) => void): () => void {
    if (!this.messageHandlers.has(messageType)) {
      this.messageHandlers.set(messageType, new Set());
    }
    this.messageHandlers.get(messageType)!.add(handler);

    // Return unsubscribe function
    return () => {
      this.messageHandlers.get(messageType)?.delete(handler);
    };
  }

  off(messageType: string, handler: (payload: any, meta?: WebSocketMessage['meta']) => void) {
    this.messageHandlers.get(messageType)?.delete(handler);
  }

  onConnectionStateChange(listener: (state: WebSocketConnectionState) => void): () => void {
    this.stateListeners.add(listener);
    // Immediately call with current state
    listener(this.connectionState);
    return () => {
      this.stateListeners.delete(listener);
    };
  }

  send(message: any) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  disconnect() {
    this.stopStaleCheck();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.messageHandlers.clear();
    this.stateListeners.clear();
    this.updateConnectionState({
      isConnected: false,
      isReconnecting: false,
      lastMessageTime: null,
      stale: false,
      reconnectAttempts: 0,
    });
  }

  getConnectionState(): WebSocketConnectionState {
    return { ...this.connectionState };
  }
}

export const wsManager = new WebSocketManager();