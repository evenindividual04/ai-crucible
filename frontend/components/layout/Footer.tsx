'use client';

import React from 'react';
import { cn } from '@/lib/cn';

/**
 * Footer status bar component
 * Following .agent/skills/frontend-design guidelines
 */

interface FooterProps {
    syncPercentage?: number;
    avgLatency?: number;
    sessionId?: string;
    systemStatus?: 'nominal' | 'warning' | 'error';
}

export const Footer: React.FC<FooterProps> = ({
    syncPercentage = 100,
    avgLatency = 0,
    sessionId,
    systemStatus = 'nominal'
}) => {
    const statusConfig = {
        nominal: { text: 'System Nominal', color: 'text-success' },
        warning: { text: 'System Warning', color: 'text-warning' },
        error: { text: 'System Error', color: 'text-error' },
    };

    const currentStatus = statusConfig[systemStatus];

    return (
        <footer className="h-10 border-t border-border bg-background-elevated/80 backdrop-blur-md flex items-center px-6 justify-between text-[10px] uppercase font-bold tracking-widest font-mono">
            {/* Left Section - Metrics */}
            <div className="flex items-center gap-6 text-text-muted">
                <span>Synced: {syncPercentage}%</span>
                <span>Avg Latency: {avgLatency}ms</span>
            </div>

            {/* Right Section - Session \u0026 Status */}
            <div className="flex items-center gap-4">
                {sessionId && (
                    <>
                        <span className="text-text-muted">
                            Session ID: <span className="text-primary">{sessionId}</span>
                        </span>
                        <div className="h-3 w-px bg-border" />
                    </>
                )}
                <span className={cn(currentStatus.color)}>
                    {currentStatus.text}
                </span>
            </div>
        </footer>
    );
};
