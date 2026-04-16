'use client';

import { useCallback, useEffect } from 'react';
import ReactFlow, {
    Background,
    Controls,
    MiniMap,
    useNodesState,
    useEdgesState,
    addEdge,
    Connection,
    BackgroundVariant,
} from 'reactflow';
import 'reactflow/dist/style.css';

import ComponentNode from './ComponentNode';
import AgentNode from './AgentNode';
import { useCrucibleStore } from '@/store/crucibleStore';
import { Card } from '@/components/ui';

const nodeTypes = {
    component: ComponentNode,
    agent: AgentNode,
};

export default function NetworkGraph() {
    const { nodes: storeNodes, edges: storeEdges } = useCrucibleStore();
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);

    useEffect(() => {
        setNodes(storeNodes);
        setEdges(storeEdges);
    }, [storeNodes, storeEdges, setNodes, setEdges]);

    const onConnect = useCallback(
        (params: Connection) => setEdges((eds) => addEdge(params, eds)),
        [setEdges]
    );

    return (
        <Card variant="elevated" padding="none" className="h-full overflow-hidden">
            <div className="w-full h-full relative">
                {/* Legend */}
                <div className="absolute top-4 right-4 z-10">
                    <div className="glass px-4 py-2 rounded-lg">
                        <div className="flex items-center gap-4 text-[10px] font-bold tracking-widest uppercase text-text-muted">
                            <div className="flex items-center gap-1.5">
                                <div className="size-2 rounded-full bg-success" />
                                Safe
                            </div>
                            <div className="flex items-center gap-1.5">
                                <div className="size-2 rounded-full bg-warning" />
                                Warning
                            </div>
                            <div className="flex items-center gap-1.5">
                                <div className="size-2 rounded-full bg-critical shadow-[0_0_10px_rgba(239,68,68,0.6)]" />
                                Breach
                            </div>
                        </div>
                    </div>
                </div>

                {/* React Flow */}
                <div className="w-full h-full">
                    <ReactFlow
                        nodes={nodes}
                        edges={edges}
                        onNodesChange={onNodesChange}
                        onEdgesChange={onEdgesChange}
                        onConnect={onConnect}
                        nodeTypes={nodeTypes}
                        fitView
                        minZoom={0.5}
                        maxZoom={2}
                        defaultEdgeOptions={{
                            animated: true,
                            style: {
                                stroke: '#00D9A3',
                                strokeWidth: 2,
                            },
                        }}
                        className="bg-background reactflow-dark"
                    >
                        <Background
                            color="var(--color-border)"
                            gap={30}
                            size={1}
                            variant={BackgroundVariant.Dots}
                        />
                        <Controls
                            className="bg-surface border-border [&>button]:bg-surface [&>button]:border-border [&>button]:text-text-muted [&>button:hover]:bg-surface-hover [&>button:hover]:text-text"
                            showInteractive={false}
                        />
                        <MiniMap
                            nodeColor={(node) => {
                                if (node.type === 'agent') {
                                    return node.data.type === 'RED_TEAM' ? '#F97316' : '#00D9A3';
                                }
                                const risk = node.data.riskLevel;
                                if (risk === 'CRITICAL') return '#EF4444';
                                if (risk === 'HIGH') return '#F97316';
                                if (risk === 'MEDIUM') return '#FACC15';
                                return '#10B981';
                            }}
                            style={{ background: '#0a0f1a', border: '1px solid #1e2a3a' }}
                            maskColor="rgba(0, 0, 0, 0.8)"
                        />
                    </ReactFlow>
                </div>
            </div>
        </Card>
    );
}
