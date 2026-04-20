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
  | 'ATTACK_EFFECTIVENESS_UPDATE'
  | 'DEFENSE_QUALITY_UPDATE'
  | 'CONVERGENCE_UPDATE'
  | 'JUDGE_DECISION'
  | 'ERROR';

export interface AttackEffectivenessData {
  [key: string]: any;
}

export type AttackEffectivenessSeries = AttackEffectivenessData[];

export interface DefenseQualityData {
  [key: string]: any;
}

export interface ConvergenceData {
  [key: string]: any;
}

type GenericEventType = Exclude<
  EventType,
  'ATTACK_EFFECTIVENESS_UPDATE' | 'DEFENSE_QUALITY_UPDATE' | 'CONVERGENCE_UPDATE'
>;

export interface GenericWebSocketEvent {
  type: GenericEventType;
  data: Record<string, any>;
}

export interface AttackEffectivenessEvent {
  type: 'ATTACK_EFFECTIVENESS_UPDATE';
  data: AttackEffectivenessSeries;
}

export interface DefenseQualityEvent {
  type: 'DEFENSE_QUALITY_UPDATE';
  data: DefenseQualityData;
}

export interface ConvergenceEvent {
  type: 'CONVERGENCE_UPDATE';
  data: ConvergenceData;
}

export type WebSocketEvent =
  | GenericWebSocketEvent
  | AttackEffectivenessEvent
  | DefenseQualityEvent
  | ConvergenceEvent;

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
