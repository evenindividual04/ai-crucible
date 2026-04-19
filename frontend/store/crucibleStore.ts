import { create } from 'zustand';
import { Node, Edge } from 'reactflow';
import {
    Component,
    Vulnerability,
    Agent,
    ScoreData,
    AttackEffectivenessSeries,
    DefenseQualityData,
    ConvergenceData,
} from '@/types/events';

export interface RunHistory {
    id: string;
    prompt: string;
    status: 'completed' | 'running' | 'failed';
    score: number;
    grade: string;
    duration: string;
    timestamp: string;
    vulnerabilities: number;
}

export interface Checkpoint {
    id: string;
    timestamp: string;
    iteration: number;
    score: number;
    components: Component[];
    vulnerabilities: Vulnerability[];
    agents: Agent[];
    nodes: Node[];
    edges: Edge[];
}

interface CrucibleState {
    // Connection
    isConnected: boolean;
    isSimulating: boolean;

    // Data
    components: Component[];
    vulnerabilities: Vulnerability[];
    agents: Agent[];

    // Graph
    nodes: Node[];
    edges: Edge[];

    // Score
    scoreData: ScoreData | null;
    attackEffectiveness: AttackEffectivenessSeries | null;
    defenseQuality: DefenseQualityData | null;
    convergenceData: ConvergenceData | null;

    // Iteration
    currentIteration: number;
    maxIterations: number;

    // Metrics
    patchCount: number;
    simulationStartTime: number | null;

    // Run History
    runHistory: RunHistory[];
    currentRunId: string | null;

    // Checkpoints
    checkpoints: Checkpoint[];

    // Actions
    setConnected: (connected: boolean) => void;
    setSimulating: (simulating: boolean) => void;
    addComponent: (component: Component) => void;
    addVulnerability: (vuln: Vulnerability) => void;
    addAgent: (agent: Agent) => void;
    updateComponentRisk: (id: number, risk: string, vulnCount: number) => void;
    updateScore: (scoreData: ScoreData) => void;
    updateAttackEffectiveness: (data: AttackEffectivenessSeries) => void;
    updateDefenseQuality: (data: DefenseQualityData) => void;
    updateConvergenceData: (data: ConvergenceData) => void;
    setIteration: (current: number, max: number) => void;
    incrementPatchCount: () => void;
    setSimulationStartTime: (time: number | null) => void;
    reset: () => void;

    // Run History Actions
    addRunToHistory: (run: RunHistory) => void;
    setCurrentRunId: (id: string) => void;
    getRunById: (id: string) => RunHistory | undefined;

    // Checkpoint Actions
    createCheckpoint: (name?: string) => void;
    restoreCheckpoint: (id: string) => void;
    deleteCheckpoint: (id: string) => void;

    // Selectors
    getFilteredVulnerabilities: (severity?: string) => Vulnerability[];
    getFilteredRuns: (filters: { status?: string; searchTerm?: string }) => RunHistory[];
}

export const useCrucibleStore = create<CrucibleState>((set, get) => ({
    isConnected: false,
    isSimulating: false,
    components: [],
    vulnerabilities: [],
    agents: [],
    nodes: [],
    edges: [],
    scoreData: null,
    attackEffectiveness: null,
    defenseQuality: null,
    convergenceData: null,
    currentIteration: 0,
    maxIterations: 3,
    patchCount: 0,
    simulationStartTime: null,
    runHistory: [],
    currentRunId: null,
    checkpoints: [],

    setConnected: (connected) => set({ isConnected: connected }),
    setSimulating: (simulating) => set({ isSimulating: simulating }),

    addComponent: (component) => set((state) => {
        const COLS = 3;
        const CELL_W = 230;
        const CELL_H = 170;
        const idx = state.components.length;
        const col = idx % COLS;
        const row = Math.floor(idx / COLS);
        const newNode: Node = {
            id: `comp-${component.id}`,
            type: 'component',
            position: { x: 80 + col * CELL_W, y: 260 + row * CELL_H },
            data: component
        };

        // Create edges for dependencies
        const newEdges: Edge[] = component.dependencies?.map(depId => ({
            id: `edge-${depId}-${component.id}`,
            source: `comp-${depId}`,
            target: `comp-${component.id}`,
            animated: false,
        })) || [];

        return {
            components: [...state.components, component],
            nodes: [...state.nodes, newNode],
            edges: [...state.edges, ...newEdges]
        };
    }),

    addVulnerability: (vuln) => set((state) => ({
        vulnerabilities: [...state.vulnerabilities, vuln]
    })),

    addAgent: (agent) => set((state) => {
        // Deduplicate by name — same logical agent can spawn each iteration
        const existingIdx = state.agents.findIndex(a => a.name === agent.name && a.type === agent.type);
        if (existingIdx !== -1) {
            // Update status on existing agent, don't add a duplicate
            const updatedAgents = [...state.agents];
            updatedAgents[existingIdx] = { ...updatedAgents[existingIdx], status: agent.status };
            return { agents: updatedAgents };
        }

        const redCount = state.agents.filter(a => a.type === 'RED_TEAM').length;
        const defCount = state.agents.filter(a => a.type === 'DEFENDER').length;
        const position = agent.type === 'DEFENDER'
            ? { x: 80 + defCount * 220, y: 170 }
            : { x: 80 + redCount * 190, y: 50 };
        const newNode: Node = {
            id: agent.id,
            type: 'agent',
            position,
            data: agent
        };

        return {
            agents: [...state.agents, agent],
            nodes: [...state.nodes, newNode]
        };
    }),

    updateComponentRisk: (id, risk, vulnCount) => set((state) => ({
        components: state.components.map(c =>
            c.id === id ? { ...c, riskLevel: risk as any, vulnerabilityCount: vulnCount } : c
        ),
        nodes: state.nodes.map(n =>
            n.id === `comp-${id}` ? { ...n, data: { ...n.data, riskLevel: risk, vulnerabilityCount: vulnCount } } : n
        )
    })),

    updateScore: (scoreData) => set({ scoreData }),

    updateAttackEffectiveness: (data) => set({ attackEffectiveness: data }),

    updateDefenseQuality: (data) => set({ defenseQuality: data }),

    updateConvergenceData: (data) => set({ convergenceData: data }),

    setIteration: (current, max) => set({ currentIteration: current, maxIterations: max }),

    incrementPatchCount: () => set((state) => ({ patchCount: state.patchCount + 1 })),

    setSimulationStartTime: (time) => set({ simulationStartTime: time }),

    reset: () => set({
        components: [],
        vulnerabilities: [],
        agents: [],
        nodes: [],
        edges: [],
        scoreData: null,
        attackEffectiveness: null,
        defenseQuality: null,
        convergenceData: null,
        currentIteration: 0,
        patchCount: 0,
        simulationStartTime: null,
        isSimulating: false
    }),

    // Run History
    addRunToHistory: (run) => set((state) => ({
        runHistory: [run, ...state.runHistory],
        currentRunId: run.id
    })),

    setCurrentRunId: (id) => set({ currentRunId: id }),

    getRunById: (id) => {
        return get().runHistory.find(run => run.id === id);
    },

    // Checkpoints
    createCheckpoint: (name) => set((state) => {
        const checkpoint: Checkpoint = {
            id: `checkpoint-${Date.now()}`,
            timestamp: new Date().toISOString(),
            iteration: state.currentIteration,
            score: state.scoreData?.score || 0,
            components: [...state.components],
            vulnerabilities: [...state.vulnerabilities],
            agents: [...state.agents],
            nodes: [...state.nodes],
            edges: [...state.edges],
        };

        return {
            checkpoints: [...state.checkpoints, checkpoint]
        };
    }),

    restoreCheckpoint: (id) => set((state) => {
        const checkpoint = state.checkpoints.find(cp => cp.id === id);
        if (!checkpoint) return state;

        return {
            components: [...checkpoint.components],
            vulnerabilities: [...checkpoint.vulnerabilities],
            agents: [...checkpoint.agents],
            nodes: [...checkpoint.nodes],
            edges: [...checkpoint.edges],
            currentIteration: checkpoint.iteration,
            scoreData: { ...state.scoreData, score: checkpoint.score } as ScoreData,
        };
    }),

    deleteCheckpoint: (id) => set((state) => ({
        checkpoints: state.checkpoints.filter(cp => cp.id !== id)
    })),

    // Selectors
    getFilteredVulnerabilities: (severity) => {
        const state = get();
        if (!severity) return state.vulnerabilities;
        return state.vulnerabilities.filter(v => v.severity === severity);
    },

    getFilteredRuns: (filters) => {
        const state = get();
        let filtered = state.runHistory;

        if (filters.status) {
            filtered = filtered.filter(run => run.status === filters.status);
        }

        if (filters.searchTerm) {
            const term = filters.searchTerm.toLowerCase();
            filtered = filtered.filter(run =>
                run.prompt.toLowerCase().includes(term) ||
                run.id.toLowerCase().includes(term)
            );
        }

        return filtered;
    },
}));
