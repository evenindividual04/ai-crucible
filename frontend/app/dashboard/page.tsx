'use client';

import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';
import { ScorePanel, AgentPanel, VulnerabilityFeed, MetricsPanel, SimulationLauncher } from '@/components/panels';
import NetworkGraph from '@/components/graph/NetworkGraph';
import { CheckpointManager } from '@/components/checkpoint/CheckpointManager';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useCrucibleStore } from '@/store/crucibleStore';

export default function DashboardPage() {
    const isConnected = useCrucibleStore(state => state.isConnected);
    const isSimulating = useCrucibleStore(state => state.isSimulating);

    // WebSocket connection with auto-reconnect
    const { status, sendMessage } = useWebSocket('ws://localhost:8000/ws/simulate', {
        reconnectInterval: 3000,
        maxReconnectAttempts: 5,
    });

    const handleStartSimulation = (prompt: string, useMock: boolean) => {
        sendMessage({
            type: 'START_SIMULATION',
            data: { prompt, use_mock: useMock },
        });
    };

    return (
        <div className="h-screen bg-background flex flex-col overflow-hidden">
            <Header
                connectionStatus={status}
                sessionId="sim-2024-001"
            />

            <SimulationLauncher
                onStart={handleStartSimulation}
                isConnected={isConnected}
                isSimulating={isSimulating}
            />

            <main className="flex-1 overflow-auto custom-scrollbar topology-grid">
                <div className="container mx-auto px-6 py-6 max-w-[1800px]">
                    <div className="grid grid-cols-12 gap-6 h-full">
                        {/* Left Column - Panels */}
                        <div className="col-span-12 lg:col-span-3 space-y-6">
                            <ScorePanel />
                            <AgentPanel />
                            <MetricsPanel />
                            <CheckpointManager />
                        </div>

                        {/* Center Column - Graph */}
                        <div className="col-span-12 lg:col-span-6 h-[800px]">
                            <NetworkGraph />
                        </div>

                        {/* Right Column - Vulnerability Feed */}
                        <div className="col-span-12 lg:col-span-3">
                            <VulnerabilityFeed />
                        </div>
                    </div>
                </div>
            </main>

            <Footer
                syncPercentage={isSimulating ? 75 : 100}
                avgLatency={45}
                sessionId="sim-2024-001"
                systemStatus={isConnected ? 'nominal' : 'warning'}
            />
        </div>
    );
}
