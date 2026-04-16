'use client';

import React from 'react';
import Link from 'next/link';
import { Badge, PulseDot } from '@/components/ui';
import { Bell, Settings, Activity } from 'lucide-react';
import { cn } from '@/lib/cn';

/**
 * Header component for the dashboard
 * Following .agent/skills/frontend-design guidelines
 */

interface HeaderProps {
    connectionStatus?: 'connected' | 'connecting' | 'disconnected';
    isSimulating?: boolean;
    sessionId?: string;
}

export const Header: React.FC<HeaderProps> = ({
    connectionStatus = 'disconnected',
    isSimulating = false,
    sessionId
}) => {
    return (
        <header className="flex items-center justify-between border-b border-border px-6 py-3 bg-background-elevated">
            {/* Logo and Title */}
            <div className="flex items-center gap-4">
                {/* Logo */}
                <Link href="/dashboard" className="flex items-center gap-3 cursor-pointer group">
                    <div className="bg-primary p-1.5 rounded-lg transition-all duration-200 group-hover:shadow-glow">
                        <svg
                            className="size-6 text-black"
                            fill="none"
                            viewBox="0 0 48 48"
                            xmlns="http://www.w3.org/2000/svg"
                        >
                            <path
                                d="M42.4379 44C42.4379 44 36.0744 33.9038 41.1692 24C46.8624 12.9336 42.2078 4 42.2078 4L7.01134 4C7.01134 4 11.6577 12.932 5.96912 23.9969C0.876273 33.9029 7.27094 44 7.27094 44L42.4379 44Z"
                                fill="currentColor"
                            />
                        </svg>
                    </div>
                    <div>
                        <h1 className="text-white text-lg font-bold leading-tight tracking-tight font-mono">
                            AI Crucible <span className="text-text-muted font-normal mx-2">/</span> War Room
                        </h1>
                    </div>
                </Link>
            </div>

            {/* Right Section */}
            <div className="flex items-center gap-6">
                {/* Connection Status */}
                <Badge
                    variant={connectionStatus}
                    pulse={connectionStatus === 'connected'}
                >
                    {connectionStatus}
                </Badge>

                {/* Simulating Badge */}
                {isSimulating && (
                    <Badge variant="active">
                        <Activity className="w-3 h-3" />
                        Simulating
                    </Badge>
                )}

                {/* Session ID */}
                {sessionId && (
                    <div className="hidden md:flex items-center gap-2 text-xs text-text-muted font-mono">
                        <span>Session:</span>
                        <span className="text-primary">{sessionId}</span>
                    </div>
                )}

                {/* Action Buttons */}
                <div className="flex items-center gap-3 ml-4 border-l border-border pl-6">
                    <button
                        className="p-2 text-text-muted hover:text-text hover:bg-surface rounded-lg transition-all duration-200 cursor-pointer"
                        aria-label="Notifications"
                    >
                        <Bell className="w-5 h-5" />
                    </button>
                    <Link
                        href="/settings"
                        className="p-2 text-text-muted hover:text-text hover:bg-surface rounded-lg transition-all duration-200 cursor-pointer"
                        aria-label="Settings"
                    >
                        <Settings className="w-5 h-5" />
                    </Link>
                </div>
            </div>
        </header>
    );
};
