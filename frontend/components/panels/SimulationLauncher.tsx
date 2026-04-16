'use client';

import React, { useState } from 'react';
import { Play, Zap } from 'lucide-react';

interface SimulationLauncherProps {
    onStart: (prompt: string, useMock: boolean) => void;
    isConnected: boolean;
    isSimulating: boolean;
}

export function SimulationLauncher({ onStart, isConnected, isSimulating }: SimulationLauncherProps) {
    const [prompt, setPrompt] = useState('');
    const [useMock, setUseMock] = useState(true);

    const handleStart = () => {
        const text = prompt.trim();
        if (!text || !isConnected || isSimulating) return;
        onStart(text, useMock);
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
            handleStart();
        }
    };

    if (isSimulating) return null;

    return (
        <div className="w-full border-b border-border bg-background-elevated px-6 py-4">
            <div className="max-w-[1800px] mx-auto flex items-start gap-4">
                <div className="flex-1">
                    <textarea
                        value={prompt}
                        onChange={e => setPrompt(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Describe the system you want to stress-test… (e.g. 'Design a secure multi-tenant SaaS auth system')"
                        rows={2}
                        className="w-full bg-surface border border-border rounded-lg px-4 py-2.5 text-sm text-text placeholder:text-text-muted resize-none focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-colors"
                    />
                    <p className="text-[11px] text-text-muted mt-1">
                        ⌘ + Enter to launch
                    </p>
                </div>

                <div className="flex items-center gap-4 pt-1">
                    <label className="flex items-center gap-2 text-xs text-text-muted cursor-pointer select-none">
                        <input
                            type="checkbox"
                            checked={useMock}
                            onChange={e => setUseMock(e.target.checked)}
                            className="w-3.5 h-3.5 rounded border-border bg-surface accent-primary cursor-pointer"
                        />
                        Mock
                    </label>

                    <button
                        onClick={handleStart}
                        disabled={!isConnected || !prompt.trim()}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all
                            bg-primary text-black hover:brightness-110
                            disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:brightness-100"
                    >
                        {isConnected ? (
                            <Play className="w-4 h-4" />
                        ) : (
                            <Zap className="w-4 h-4 animate-pulse" />
                        )}
                        {isConnected ? 'Launch' : 'Waiting…'}
                    </button>
                </div>
            </div>
        </div>
    );
}
