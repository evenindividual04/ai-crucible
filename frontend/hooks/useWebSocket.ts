import { useEffect, useRef, useState, useCallback } from 'react';
import { useCrucibleStore } from '@/store/crucibleStore';
import { WebSocketEvent } from '@/types/events';
import {
    Component,
    Vulnerability,
    Agent,
    ScoreData,
    AttackEffectivenessSeries,
    DefenseQualityData,
    ConvergenceData,
} from '@/types/events';

interface UseWebSocketOptions {
    reconnectInterval?: number;
    maxReconnectAttempts?: number;
    heartbeatInterval?: number;
}

function isObject(value: unknown): value is Record<string, any> {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function hasRequiredKeys(value: Record<string, any>, keys: string[]): boolean {
    return keys.every((key) => key in value);
}

function parseWebSocketEvent(raw: unknown): WebSocketEvent | null {
    if (!isObject(raw) || typeof raw.type !== 'string' || !('data' in raw)) {
        return null;
    }

    const eventType = raw.type;
    const eventData = raw.data;

    if (eventType === 'ATTACK_EFFECTIVENESS_UPDATE') {
        if (!Array.isArray(eventData) || !eventData.every((entry) => isObject(entry))) {
            return null;
        }
        return { type: eventType, data: eventData };
    }

    if (eventType === 'DEFENSE_QUALITY_UPDATE' || eventType === 'CONVERGENCE_UPDATE') {
        if (!isObject(eventData)) {
            return null;
        }
        return { type: eventType, data: eventData } as WebSocketEvent;
    }

    if (!isObject(eventData)) {
        return null;
    }

    const requiredByType: Record<string, string[]> = {
        SYSTEM_INIT: ['prompt', 'config', 'timestamp'],
        SIMULATION_END: ['status', 'iterations'],
        ITERATION_START: ['iteration', 'max_iterations'],
        AGENT_SPAWN: ['id', 'name', 'type'],
        AGENT_THINKING: [],
        COMPONENT_CREATED: ['id', 'name', 'type'],
        COMPONENT_RISK_UPDATE: ['component_id', 'risk_level', 'vulnerability_count'],
        VULNERABILITY_FOUND: ['id', 'severity', 'title'],
        PATCH_APPLIED: ['id', 'target_vulnerability_id', 'description'],
        SCORE_UPDATE: ['score'],
        JUDGE_DECISION: ['decision', 'reason'],
        ERROR: ['message'],
    };

    const required = requiredByType[eventType];
    if (required && !hasRequiredKeys(eventData, required)) {
        return null;
    }

    return { type: eventType as WebSocketEvent['type'], data: eventData } as WebSocketEvent;
}

export function useWebSocket(url: string, options: UseWebSocketOptions = {}) {
    const {
        reconnectInterval = 3000,
        maxReconnectAttempts = 5,
        heartbeatInterval = 30000,
    } = options;

    const ws = useRef<WebSocket | null>(null);
    const reconnectAttempts = useRef(0);
    const reconnectTimeout = useRef<NodeJS.Timeout | undefined>(undefined);
    const heartbeatTimeout = useRef<NodeJS.Timeout | undefined>(undefined);
    const messageQueue = useRef<any[]>([]);

    const [status, setStatus] = useState<'connecting' | 'connected' | 'disconnected'>('disconnected');

    const store = useCrucibleStore();

    const clearTimeouts = () => {
        if (reconnectTimeout.current) {
            clearTimeout(reconnectTimeout.current);
        }
        if (heartbeatTimeout.current) {
            clearTimeout(heartbeatTimeout.current);
        }
    };

    const startHeartbeat = useCallback(() => {
        clearTimeout(heartbeatTimeout.current);
        heartbeatTimeout.current = setInterval(() => {
            if (ws.current?.readyState === WebSocket.OPEN) {
                ws.current.send(JSON.stringify({ type: 'PING' }));
            }
        }, heartbeatInterval);
    }, [heartbeatInterval]);

    const flushMessageQueue = useCallback(() => {
        while (messageQueue.current.length > 0 && ws.current?.readyState === WebSocket.OPEN) {
            const message = messageQueue.current.shift();
            ws.current.send(JSON.stringify(message));
        }
    }, []);

    const connect = useCallback(() => {
        if (!url) return;

        setStatus('connecting');
        ws.current = new WebSocket(url);

        ws.current.onopen = () => {
            setStatus('connected');
            store.setConnected(true);
            reconnectAttempts.current = 0;
            console.log('✅ WebSocket connected');

            // Flush queued messages
            flushMessageQueue();

            // Start heartbeat
            startHeartbeat();
        };

        ws.current.onmessage = (event) => {
            try {
                const parsed = parseWebSocketEvent(JSON.parse(event.data));
                if (!parsed) {
                    console.warn('Dropped malformed WebSocket event payload');
                    return;
                }

                // Handle PONG response (if backend sends it)
                if ((parsed.type as string) === 'PONG') {
                    return;
                }

                handleEvent(parsed);
            } catch (e) {
                console.error('Failed to parse WebSocket message:', e);
            }
        };

        ws.current.onerror = (error) => {
            console.error('❌ WebSocket error:', error);
        };

        ws.current.onclose = () => {
            setStatus('disconnected');
            store.setConnected(false);
            clearTimeouts();
            console.log('🔌 WebSocket disconnected');

            // Attempt reconnection
            if (reconnectAttempts.current < maxReconnectAttempts) {
                reconnectAttempts.current++;
                console.log(`🔄 Reconnecting... (${reconnectAttempts.current}/${maxReconnectAttempts})`);

                reconnectTimeout.current = setTimeout(() => {
                    connect();
                }, reconnectInterval);
            } else {
                console.error('❌ Max reconnection attempts reached');
                store.setSimulating(false);
            }
        };
    }, [url, reconnectInterval, maxReconnectAttempts, flushMessageQueue, startHeartbeat]);

    useEffect(() => {
        connect();

        return () => {
            clearTimeouts();
            ws.current?.close();
        };
    }, [connect]);

    const handleEvent = (event: WebSocketEvent) => {
        console.log('📨 Event:', event.type, event.data);

        switch (event.type) {
            case 'SYSTEM_INIT':
                store.reset();
                store.setSimulating(true);
                store.setSimulationStartTime(Date.now());
                break;

            case 'COMPONENT_CREATED':
                store.addComponent(event.data as Component);
                break;

            case 'VULNERABILITY_FOUND':
                store.addVulnerability(event.data as Vulnerability);
                break;

            case 'PATCH_APPLIED':
                store.incrementPatchCount();
                break;

            case 'AGENT_SPAWN':
                store.addAgent(event.data as Agent);
                break;

            case 'COMPONENT_RISK_UPDATE':
                store.updateComponentRisk(
                    (event.data as Record<string, any>).component_id,
                    (event.data as Record<string, any>).risk_level,
                    (event.data as Record<string, any>).vulnerability_count
                );
                break;

            case 'SCORE_UPDATE':
                store.updateScore(event.data as ScoreData);
                break;

            case 'ATTACK_EFFECTIVENESS_UPDATE':
                store.updateAttackEffectiveness(event.data as AttackEffectivenessSeries);
                break;

            case 'DEFENSE_QUALITY_UPDATE':
                store.updateDefenseQuality(event.data as DefenseQualityData);
                break;

            case 'CONVERGENCE_UPDATE':
                store.updateConvergenceData(event.data as ConvergenceData);
                break;

            case 'ITERATION_START':
                store.setIteration(
                    (event.data as Record<string, any>).iteration,
                    (event.data as Record<string, any>).max_iterations
                );
                break;

            case 'SIMULATION_END':
                store.setSimulating(false);
                if (event.data.attack_effectiveness !== undefined) {
                    store.updateAttackEffectiveness(event.data.attack_effectiveness as AttackEffectivenessSeries);
                }
                if (event.data.defense_quality !== undefined) {
                    store.updateDefenseQuality(event.data.defense_quality as DefenseQualityData);
                }
                if (event.data.convergence_metrics !== undefined) {
                    store.updateConvergenceData(event.data.convergence_metrics as ConvergenceData);
                }
                store.addRunToHistory({
                    id: event.data.run_id || `run-${Date.now()}`,
                    prompt: event.data.prompt || 'Unknown',
                    status: 'completed',
                    score: event.data.score || 0,
                    grade: event.data.grade || 'N/A',
                    duration: event.data.duration || '00:00:00',
                    timestamp: new Date().toISOString(),
                    vulnerabilities: store.vulnerabilities.length,
                });
                console.log('🏁 Simulation complete:', event.data);
                break;

            case 'ERROR':
                console.error('Server error:', event.data.message);
                break;
        }
    };

    const sendMessage = useCallback((message: any) => {
        if (ws.current?.readyState === WebSocket.OPEN) {
            ws.current.send(JSON.stringify(message));
        } else {
            console.warn('WebSocket not connected, queuing message');
            messageQueue.current.push(message);
        }
    }, []);

    const disconnect = useCallback(() => {
        clearTimeouts();
        reconnectAttempts.current = maxReconnectAttempts; // Prevent reconnection
        ws.current?.close();
    }, [maxReconnectAttempts]);

    const reconnect = useCallback(() => {
        disconnect();
        reconnectAttempts.current = 0;
        setTimeout(() => connect(), 100);
    }, [connect, disconnect]);

    return {
        status,
        sendMessage,
        disconnect,
        reconnect,
        isConnected: status === 'connected',
        reconnectAttempts: reconnectAttempts.current,
    };
}
