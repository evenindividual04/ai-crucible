'use client';

import React from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';
import { Card, CardHeader, CardTitle, CardContent, Badge, Button } from '@/components/ui';
import { RunTimeline } from '@/components/runs/RunTimeline';
import { ArrowLeft, Download, Share2, Clock, Target } from 'lucide-react';
import { useCrucibleStore } from '@/store/crucibleStore';

export default function RunDetailPage() {
    const params = useParams();
    const router = useRouter();
    const runId = params.id as string;

    const getRunById = useCrucibleStore(state => state.getRunById);
    const run = getRunById(runId);

    if (!run) {
        return (
            <div className="h-screen bg-background flex flex-col overflow-hidden">
                <Header connectionStatus="disconnected" sessionId="N/A" />
                <main className="flex-1 flex items-center justify-center">
                    <Card variant="elevated" padding="lg">
                        <CardContent>
                            <p className="text-text-muted">Run not found</p>
                            <Button variant="ghost" onClick={() => router.push('/runs')} className="mt-4">
                                Back to Runs
                            </Button>
                        </CardContent>
                    </Card>
                </main>
                <Footer syncPercentage={100} avgLatency={45} sessionId="N/A" systemStatus="nominal" />
            </div>
        );
    }

    // Mock timeline events
    const timelineEvents = [
        {
            id: '1',
            type: 'iteration' as const,
            title: 'Iteration 1 Started',
            timestamp: '14:30:05',
        },
        {
            id: '2',
            type: 'vulnerability' as const,
            title: 'SQL Injection Detected',
            description: 'User input not sanitized in login endpoint',
            severity: 'CRITICAL' as const,
            timestamp: '14:30:12',
        },
        {
            id: '3',
            type: 'checkpoint' as const,
            title: 'Checkpoint Created',
            description: 'Auto-checkpoint after critical vulnerability',
            timestamp: '14:30:15',
        },
    ];

    return (
        <div className="h-screen bg-background flex flex-col overflow-hidden">
            <Header connectionStatus="disconnected" sessionId={run.id} />

            <main className="flex-1 overflow-auto custom-scrollbar topology-grid">
                <div className="container mx-auto px-6 py-6 max-w-[1400px]">
                    {/* Header */}
                    <div className="mb-6">
                        <Button
                            variant="ghost"
                            size="sm"
                            icon={<ArrowLeft className="w-4 h-4" />}
                            onClick={() => router.push('/runs')}
                            className="mb-4"
                        >
                            Back to Runs
                        </Button>

                        <div className="flex items-start justify-between">
                            <div className="flex-1">
                                <div className="flex items-center gap-3 mb-2">
                                    <Badge variant={run.status === 'completed' ? 'secure' : run.status === 'running' ? 'active' : 'critical'}>
                                        {run.status.toUpperCase()}
                                    </Badge>
                                    <span className="text-xs text-text-muted font-mono">{run.id}</span>
                                </div>
                                <h1 className="text-2xl font-bold text-text mb-2">{run.prompt}</h1>
                                <div className="flex items-center gap-4 text-sm text-text-muted">
                                    <div className="flex items-center gap-1">
                                        <Clock className="w-4 h-4" />
                                        {run.timestamp}
                                    </div>
                                    <span>Duration: {run.duration}</span>
                                    {run.vulnerabilities > 0 && (
                                        <span className="text-high">
                                            {run.vulnerabilities} vulnerabilities
                                        </span>
                                    )}
                                </div>
                            </div>

                            <div className="flex items-center gap-3">
                                {run.status === 'completed' && (
                                    <div className="text-center px-6">
                                        <div className="text-4xl font-black text-primary font-mono">
                                            {run.grade}
                                        </div>
                                        <div className="text-xs text-text-muted">
                                            Score: {run.score}
                                        </div>
                                    </div>
                                )}
                                <Button variant="ghost" size="sm" icon={<Download className="w-4 h-4" />}>
                                    Export
                                </Button>
                                <Button variant="ghost" size="sm" icon={<Share2 className="w-4 h-4" />}>
                                    Share
                                </Button>
                            </div>
                        </div>
                    </div>

                    {/* Content Grid */}
                    <div className="grid grid-cols-12 gap-6">
                        {/* Timeline */}
                        <div className="col-span-12 lg:col-span-4">
                            <Card variant="elevated" padding="lg">
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2">
                                        <Target className="w-4 h-4 text-primary" />
                                        Run Timeline
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="mt-4">
                                        <RunTimeline events={timelineEvents} />
                                    </div>
                                </CardContent>
                            </Card>
                        </div>

                        {/* Details */}
                        <div className="col-span-12 lg:col-span-8">
                            <div className="space-y-6">
                                {/* Vulnerabilities */}
                                <Card variant="elevated" padding="lg">
                                    <CardHeader>
                                        <CardTitle>Vulnerabilities Found</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="mt-4 text-text-muted text-sm">
                                            {run.vulnerabilities === 0 ? (
                                                <p>No vulnerabilities detected in this run.</p>
                                            ) : (
                                                <p>{run.vulnerabilities} vulnerabilities detected. Full list would appear here.</p>
                                            )}
                                        </div>
                                    </CardContent>
                                </Card>

                                {/* Metrics */}
                                <Card variant="elevated" padding="lg">
                                    <CardHeader>
                                        <CardTitle>Run Metrics</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="grid grid-cols-3 gap-4 mt-4">
                                            <div className="bg-surface p-4 rounded-lg border border-border">
                                                <div className="text-xs text-text-muted mb-1">Duration</div>
                                                <div className="text-xl font-bold text-primary font-mono">{run.duration}</div>
                                            </div>
                                            <div className="bg-surface p-4 rounded-lg border border-border">
                                                <div className="text-xs text-text-muted mb-1">Score</div>
                                                <div className="text-xl font-bold text-primary font-mono">{run.score}</div>
                                            </div>
                                            <div className="bg-surface p-4 rounded-lg border border-border">
                                                <div className="text-xs text-text-muted mb-1">Grade</div>
                                                <div className="text-xl font-bold text-primary font-mono">{run.grade}</div>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            </div>
                        </div>
                    </div>
                </div>
            </main>

            <Footer syncPercentage={100} avgLatency={45} sessionId={run.id} systemStatus="nominal" />
        </div>
    );
}
