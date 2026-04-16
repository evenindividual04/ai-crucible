'use client';

import { useCrucibleStore } from '@/store/crucibleStore';
import { motion } from 'framer-motion';
import { Target, Shield, Activity } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent, Badge, PulseDot } from '@/components/ui';

export default function AgentPanel() {
    const { agents } = useCrucibleStore();

    const redTeam = agents.filter(a => a.type === 'RED_TEAM');
    const defenders = agents.filter(a => a.type === 'DEFENDER');

    return (
        <Card variant="elevated" padding="md">
            <CardHeader>
                <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                        <Activity className="w-4 h-4 text-primary" />
                        Active Agents
                    </CardTitle>
                    <Badge variant="active" pulse>
                        {agents.length} LIVE
                    </Badge>
                </div>
            </CardHeader>

            <CardContent>
                <div className="space-y-6 mt-4">
                    {/* Red Team */}
                    {redTeam.length > 0 && (
                        <div>
                            <div className="flex items-center gap-2 text-high mb-3">
                                <Target className="w-3.5 h-3.5" />
                                <span className="text-[11px] font-bold uppercase tracking-wider">
                                    Red Team ({redTeam.length})
                                </span>
                            </div>
                            <div className="space-y-2">
                                {redTeam.map((agent) => (
                                    <motion.div
                                        key={agent.id}
                                        initial={{ opacity: 0, y: 8 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ duration: 0.2, ease: "easeOut" }}
                                        className="flex items-center justify-between bg-surface p-3 rounded-lg border border-border hover:border-border-hover transition-all duration-200 cursor-pointer group"
                                    >
                                        <div className="flex items-center gap-3">
                                            <PulseDot color="error" size="sm" />
                                            <span className="text-sm font-medium text-text font-mono">
                                                {agent.name}
                                            </span>
                                        </div>
                                        <Badge variant="attacking">
                                            Active
                                        </Badge>
                                    </motion.div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Defenders */}
                    {defenders.length > 0 && (
                        <div>
                            <div className="flex items-center gap-2 text-primary mb-3">
                                <Shield className="w-3.5 h-3.5" />
                                <span className="text-[11px] font-bold uppercase tracking-wider">
                                    Defenders ({defenders.length})
                                </span>
                            </div>
                            <div className="space-y-2">
                                {defenders.map((agent) => (
                                    <motion.div
                                        key={agent.id}
                                        initial={{ opacity: 0, y: 8 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ duration: 0.2, ease: "easeOut" }}
                                        className="flex items-center justify-between bg-surface p-3 rounded-lg border border-border hover:border-border-hover transition-all duration-200 cursor-pointer group"
                                    >
                                        <div className="flex items-center gap-3">
                                            <PulseDot color="success" size="sm" />
                                            <span className="text-sm font-medium text-text font-mono">
                                                {agent.name}
                                            </span>
                                        </div>
                                        {/* Activity indicator */}
                                        <div className="flex items-center gap-1">
                                            <div className="h-2 w-1 bg-primary rounded-full opacity-60" />
                                            <div className="h-3 w-1 bg-primary rounded-full" />
                                            <div className="h-2 w-1 bg-primary rounded-full opacity-30" />
                                        </div>
                                    </motion.div>
                                ))}
                            </div>
                        </div>
                    )}

                    {agents.length === 0 && (
                        <div className="text-text-muted text-center py-8 text-sm">
                            No agents active
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}
