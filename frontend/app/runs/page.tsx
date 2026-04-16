'use client';

import React, { useState } from 'react';
import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';
import { Card, Button } from '@/components/ui';
import { SearchInput } from '@/components/ui/SearchInput';
import { FilterDropdown } from '@/components/ui/FilterDropdown';
import { Clock, Play, CheckCircle2, XCircle, ArrowRight, SlidersHorizontal } from 'lucide-react';
import Link from 'next/link';
import { useCrucibleStore } from '@/store/crucibleStore';
import { motion } from 'framer-motion';

export default function RunsPage() {
    const [searchTerm, setSearchTerm] = useState('');
    const [statusFilter, setStatusFilter] = useState<string[]>([]);
    const [sortBy, setSortBy] = useState<'date' | 'score' | 'duration'>('date');

    const getFilteredRuns = useCrucibleStore(state => state.getFilteredRuns);

    // Get filtered runs
    const filteredRuns = getFilteredRuns({
        searchTerm,
        status: statusFilter.length > 0 ? statusFilter[0] : undefined
    });

    // Sort runs
    const sortedRuns = [...filteredRuns].sort((a, b) => {
        if (sortBy === 'date') {
            return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
        }
        if (sortBy === 'score') {
            return b.score - a.score;
        }
        return 0; // duration sorting would need parsed duration
    });

    const statusConfig = {
        completed: { variant: 'secure' as const, icon: CheckCircle2, label: 'Completed' },
        running: { variant: 'active' as const, icon: Play, label: 'Running' },
        failed: { variant: 'critical' as const, icon: XCircle, label: 'Failed' },
    };

    const statusOptions = [
        { value: 'completed', label: 'Completed' },
        { value: 'running', label: 'Running' },
        { value: 'failed', label: 'Failed' },
    ];

    return (
        <div className="h-screen bg-background flex flex-col overflow-hidden">
            <Header
                connectionStatus="disconnected"
                sessionId="sim-2024-001"
            />

            <main className="flex-1 overflow-auto custom-scrollbar topology-grid">
                <div className="container mx-auto px-6 py-6 max-w-[1400px]">
                    {/* Page Header */}
                    <div className="mb-6">
                        <h1 className="text-2xl font-bold text-text mb-2">Simulation Runs</h1>
                        <p className="text-text-muted">View and manage all adversarial testing runs</p>
                    </div>

                    {/* Search and Filters */}
                    <div className="flex items-center gap-4 mb-6">
                        <SearchInput
                            placeholder="Search by prompt or ID..."
                            value={searchTerm}
                            onChange={setSearchTerm}
                            className="flex-1 max-w-md"
                        />

                        <FilterDropdown
                            label="Status"
                            options={statusOptions}
                            selected={statusFilter}
                            onChange={setStatusFilter}
                        />

                        <div className="flex items-center gap-2 ml-auto">
                            <SlidersHorizontal className="w-4 h-4 text-text-muted" />
                            <select
                                value={sortBy}
                                onChange={(e) => setSortBy(e.target.value as any)}
                                className="px-3 py-2 bg-surface border border-border rounded-lg text-text text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                            >
                                <option value="date">Sort by Date</option>
                                <option value="score">Sort by Score</option>
                                <option value="duration">Sort by Duration</option>
                            </select>
                        </div>
                    </div>

                    {/* Runs List */}
                    <div className="space-y-4">
                        {sortedRuns.map((run, index) => {
                            const status = statusConfig[run.status as keyof typeof statusConfig];
                            const StatusIcon = status.icon;

                            return (
                                <motion.div
                                    key={run.id}
                                    initial={{ opacity: 0, y: 20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: index * 0.05 }}
                                >
                                    <Card variant="interactive" padding="lg">
                                        <div className="flex items-center justify-between">
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-3 mb-2">
                                                    <div className={`flex items-center gap-1.5 px-2 py-1 rounded-md ${status.variant === 'secure' ? 'bg-success/10 text-success' :
                                                            status.variant === 'active' ? 'bg-primary/10 text-primary' :
                                                                'bg-critical/10 text-critical'
                                                        }`}>
                                                        <StatusIcon className="w-3 h-3" />
                                                        <span className="text-xs font-semibold">{status.label}</span>
                                                    </div>
                                                    <span className="text-xs text-text-muted font-mono">
                                                        {run.id}
                                                    </span>
                                                </div>
                                                <h3 className="text-lg font-semibold text-text mb-1 truncate">
                                                    {run.prompt}
                                                </h3>
                                                <div className="flex items-center gap-4 text-xs text-text-muted">
                                                    <div className="flex items-center gap-1">
                                                        <Clock className="w-3 h-3" />
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

                                            <div className="flex items-center gap-6 ml-6">
                                                {run.status === 'completed' && (
                                                    <div className="text-center">
                                                        <div className="text-3xl font-black text-primary font-mono">
                                                            {run.grade}
                                                        </div>
                                                        <div className="text-xs text-text-muted">
                                                            Score: {run.score}
                                                        </div>
                                                    </div>
                                                )}

                                                <Link href={`/runs/${run.id}`}>
                                                    <Button variant="ghost" size="sm" icon={<ArrowRight className="w-4 h-4" />}>
                                                        View Details
                                                    </Button>
                                                </Link>
                                            </div>
                                        </div>
                                    </Card>
                                </motion.div>
                            );
                        })}
                    </div>

                    {/* Empty State */}
                    {sortedRuns.length === 0 && (
                        <Card variant="elevated" padding="lg">
                            <div className="text-center py-12">
                                <p className="text-text-muted mb-4">
                                    {searchTerm || statusFilter.length > 0
                                        ? 'No runs match your filters'
                                        : 'No simulation runs yet'}
                                </p>
                                {!searchTerm && statusFilter.length === 0 && (
                                    <Link href="/dashboard">
                                        <Button variant="primary">
                                            Start New Run
                                        </Button>
                                    </Link>
                                )}
                            </div>
                        </Card>
                    )}
                </div>
            </main>

            <Footer
                syncPercentage={100}
                avgLatency={45}
                sessionId="sim-2024-001"
                systemStatus="nominal"
            />
        </div>
    );
}
