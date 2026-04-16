'use client';

import React from 'react';
import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';
import { Card, CardHeader, CardTitle, CardContent, Input, Button } from '@/components/ui';
import { Settings as SettingsIcon, Save, RotateCcw } from 'lucide-react';

/**
 * Settings page - configuration for AI Crucible
 * Following .agent/skills/nextjs-best-practices guidelines
 */

export default function SettingsPage() {
    return (
        <div className="h-screen bg-background flex flex-col overflow-hidden">
            <Header
                connectionStatus="disconnected"
                sessionId="sim-2024-001"
            />

            <main className="flex-1 overflow-auto custom-scrollbar topology-grid">
                <div className="container mx-auto px-6 py-6 max-w-[1000px]">
                    {/* Page Header */}
                    <div className="mb-6">
                        <h1 className="text-2xl font-bold text-text mb-2">Settings</h1>
                        <p className="text-text-muted">Configure AI Crucible simulation parameters</p>
                    </div>

                    <div className="space-y-6">
                        {/* Simulation Settings */}
                        <Card variant="elevated" padding="lg">
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2">
                                    <SettingsIcon className="w-4 h-4 text-primary" />
                                    Simulation Settings
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-4 mt-4">
                                    <div>
                                        <label className="block text-sm font-medium text-text mb-2">
                                            Max Iterations
                                        </label>
                                        <Input
                                            type="number"
                                            defaultValue={10}
                                            className="max-w-xs"
                                        />
                                        <p className="text-xs text-text-muted mt-1">
                                            Maximum number of attack-defense iterations
                                        </p>
                                    </div>

                                    <div>
                                        <label className="block text-sm font-medium text-text mb-2">
                                            WebSocket URL
                                        </label>
                                        <Input
                                            type="text"
                                            defaultValue="ws://localhost:8000/ws/simulate"
                                            className="max-w-md"
                                        />
                                        <p className="text-xs text-text-muted mt-1">
                                            Backend WebSocket endpoint
                                        </p>
                                    </div>

                                    <div>
                                        <label className="block text-sm font-medium text-text mb-2">
                                            Use Mock Data
                                        </label>
                                        <div className="flex items-center gap-2">
                                            <input
                                                type="checkbox"
                                                defaultChecked
                                                className="w-4 h-4 rounded border-border bg-surface text-primary focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background cursor-pointer"
                                            />
                                            <span className="text-sm text-text-muted">
                                                Enable mock data for testing
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>

                        {/* Display Settings */}
                        <Card variant="elevated" padding="lg">
                            <CardHeader>
                                <CardTitle>Display Settings</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-4 mt-4">
                                    <div>
                                        <label className="block text-sm font-medium text-text mb-2">
                                            Graph Animation Speed
                                        </label>
                                        <Input
                                            type="range"
                                            min="1"
                                            max="10"
                                            defaultValue={5}
                                            className="max-w-xs"
                                        />
                                        <p className="text-xs text-text-muted mt-1">
                                            Animation speed for graph transitions
                                        </p>
                                    </div>

                                    <div>
                                        <label className="block text-sm font-medium text-text mb-2">
                                            Show Minimap
                                        </label>
                                        <div className="flex items-center gap-2">
                                            <input
                                                type="checkbox"
                                                defaultChecked
                                                className="w-4 h-4 rounded border-border bg-surface text-primary focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background cursor-pointer"
                                            />
                                            <span className="text-sm text-text-muted">
                                                Display minimap in graph view
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>

                        {/* Actions */}
                        <div className="flex items-center gap-3">
                            <Button variant="primary" icon={<Save className="w-4 h-4" />}>
                                Save Changes
                            </Button>
                            <Button variant="ghost" icon={<RotateCcw className="w-4 h-4" />}>
                                Reset to Defaults
                            </Button>
                        </div>
                    </div>
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
