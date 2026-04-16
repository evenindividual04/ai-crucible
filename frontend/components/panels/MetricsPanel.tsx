'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui';
import { BarChart3, Zap, CheckCircle2, Clock } from 'lucide-react';
import { useCrucibleStore } from '@/store/crucibleStore';

function formatElapsed(startTime: number | null): string {
    if (!startTime) return '--:--:--';
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const h = Math.floor(elapsed / 3600).toString().padStart(2, '0');
    const m = Math.floor((elapsed % 3600) / 60).toString().padStart(2, '0');
    const s = (elapsed % 60).toString().padStart(2, '0');
    return `${h}:${m}:${s}`;
}

export const MetricsPanel: React.FC = () => {
    const currentIteration = useCrucibleStore(state => state.currentIteration);
    const maxIterations = useCrucibleStore(state => state.maxIterations);
    const patchCount = useCrucibleStore(state => state.patchCount);
    const vulnerabilities = useCrucibleStore(state => state.vulnerabilities);
    const simulationStartTime = useCrucibleStore(state => state.simulationStartTime);
    const isSimulating = useCrucibleStore(state => state.isSimulating);

    const [elapsed, setElapsed] = useState('--:--:--');

    useEffect(() => {
        if (!simulationStartTime) {
            setElapsed('--:--:--');
            return;
        }
        setElapsed(formatElapsed(simulationStartTime));
        if (!isSimulating) return;
        const timer = setInterval(() => {
            setElapsed(formatElapsed(simulationStartTime));
        }, 1000);
        return () => clearInterval(timer);
    }, [simulationStartTime, isSimulating]);

    const vulnCount = vulnerabilities.length;
    const patchSuccessRate = vulnCount > 0 ? Math.round((patchCount / vulnCount) * 100) : 0;
    const iterLabel = maxIterations > 0 ? `${currentIteration}/${maxIterations}` : currentIteration.toString();

    const metrics = [
        {
            label: 'Vulnerabilities',
            value: vulnCount.toString(),
            icon: BarChart3,
            color: 'text-info',
        },
        {
            label: 'Iterations',
            value: iterLabel,
            icon: Zap,
            color: 'text-warning',
        },
        {
            label: 'Patch Success',
            value: vulnCount > 0 ? `${patchSuccessRate}%` : '--',
            icon: CheckCircle2,
            color: 'text-success',
        },
        {
            label: 'Time Elapsed',
            value: elapsed,
            icon: Clock,
            color: 'text-primary',
        },
    ];

    return (
        <Card variant="elevated" padding="md">
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-primary" />
                    System Metrics
                </CardTitle>
            </CardHeader>

            <CardContent>
                <div className="grid grid-cols-2 gap-3 mt-4">
                    {metrics.map((metric) => {
                        const Icon = metric.icon;
                        return (
                            <div
                                key={metric.label}
                                className="bg-surface p-3 rounded-lg border border-border"
                            >
                                <div className="flex items-center gap-2 mb-1">
                                    <Icon className={`w-3.5 h-3.5 ${metric.color}`} />
                                    <span className="text-[10px] text-text-muted uppercase tracking-wider">
                                        {metric.label}
                                    </span>
                                </div>
                                <div className={`text-xl font-bold font-mono ${metric.color}`}>
                                    {metric.value}
                                </div>
                            </div>
                        );
                    })}
                </div>
            </CardContent>
        </Card>
    );
};
