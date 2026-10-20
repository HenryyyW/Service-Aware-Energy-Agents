import axios, { type AxiosInstance, type AxiosError } from 'axios';
import type {
  ScenarioConfig,
  SimulationRun,
  TimeStepData,
  AgentTask,
  WebSocketMessage,
  NetworkGeometry,
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
    const response = await this.client.post('/api/scenarios', scenario);
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
  async getNetworkGeometry(): Promise<NetworkGeometry> {
    const response = await this.client.get('/api/network/geometry');
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
  async getReport(runId: string): Promise<string> {
    const response = await this.client.get(`/api/reports/${runId}`, {
      responseType: 'text',
    });
    return response.data;
  }

  async downloadReport(runId: string, format: 'markdown' | 'pdf' | 'zip'): Promise<Blob> {
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

// WebSocket connection manager
export class WebSocketManager {
  private ws: WebSocket | null = null;
  private messageHandlers: Map<string, Set<(payload: any) => void>> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;

  connect(runId?: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const url = runId
        ? `${WS_BASE_URL}/ws/simulation/${runId}`
        : `${WS_BASE_URL}/ws`;

      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        resolve();
      };

      this.ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          this.dispatchMessage(message.type, message.payload);
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
        this.attemptReconnect(runId);
      };
    });
  }

  private attemptReconnect(runId?: string) {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
      console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
      setTimeout(() => this.connect(runId), delay);
    }
  }

  private dispatchMessage(type: string, payload: any) {
    const handlers = this.messageHandlers.get(type);
    if (handlers) {
      handlers.forEach((handler) => handler(payload));
    }
    // Also dispatch to wildcard handlers
    const wildcardHandlers = this.messageHandlers.get('*');
    if (wildcardHandlers) {
      wildcardHandlers.forEach((handler) => handler({ type, payload }));
    }
  }

  on(messageType: string, handler: (payload: any) => void): () => void {
    if (!this.messageHandlers.has(messageType)) {
      this.messageHandlers.set(messageType, new Set());
    }
    this.messageHandlers.get(messageType)!.add(handler);

    // Return unsubscribe function
    return () => {
      this.messageHandlers.get(messageType)?.delete(handler);
    };
  }

  off(messageType: string, handler: (payload: any) => void) {
    this.messageHandlers.get(messageType)?.delete(handler);
  }

  send(message: any) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.messageHandlers.clear();
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

export const wsManager = new WebSocketManager();