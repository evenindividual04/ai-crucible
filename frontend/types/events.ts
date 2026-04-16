/**
 * WebSocket event type definitions
 */

export type EventType =
  | 'SYSTEM_INIT'
  | 'SIMULATION_END'
  | 'ITERATION_START'
  | 'AGENT_SPAWN'
  | 'AGENT_THINKING'
  | 'COMPONENT_CREATED'
  | 'COMPONENT_RISK_UPDATE'
  | 'VULNERABILITY_FOUND'
  | 'PATCH_APPLIED'
  | 'SCORE_UPDATE'
  | 'JUDGE_DECISION'
  | 'ERROR';

export interface WebSocketEvent {
  type: EventType;
  data: any;
}

export interface Component {
  id: number;
  name: string;
  type: string;
  dependencies?: number[];
  riskLevel?: 'SECURE' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  vulnerabilityCount?: number;
}

export interface Vulnerability {
  id: number;
  title: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  domain: string;
  component_id: number;
  found_by: string;
  iteration: number;
  description?: string;
}

export interface Agent {
  id: string;
  name: string;
  type: 'RED_TEAM' | 'DEFENDER';
  status?: 'IDLE' | 'THINKING' | 'ATTACKING' | 'PATCHING';
  position?: { x: number; y: number };
}

export interface ScoreData {
  score: number;
  grade: string;
  risk_level: string;
  delta?: number;
  unpatched?: {
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
}
