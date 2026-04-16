'use client';

import { useCrucibleStore } from '@/store/crucibleStore';
import { motion } from 'framer-motion';
import { Card, CardHeader, CardTitle, CardContent, Badge, ProgressBar } from '@/components/ui';
import { Shield, TrendingUp } from 'lucide-react';

export default function ScorePanel() {
    const { scoreData, currentIteration, maxIterations } = useCrucibleStore();

    const score = scoreData?.score || 0;
    const grade = scoreData?.grade || 'N/A';
    const riskLevel = scoreData?.risk_level || 'UNKNOWN';

    // Map risk levels to badge variants
    const riskVariantMap: Record<string, 'critical' | 'high' | 'medium' | 'low' | 'secure'> = {
        CRITICAL: 'critical',
        HIGH: 'high',
        MEDIUM: 'medium',
        LOW: 'low',
        SECURE: 'secure',
    };

    const riskVariant = riskVariantMap[riskLevel] || 'low';

    return (
        <Card variant="elevated" padding="lg">
            <CardHeader>
                <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                        <Shield className="w-4 h-4 text-primary" />
                        Security Health
                    </CardTitle>
                    <Badge variant={riskVariant}>
                        {riskLevel}
                    </Badge>
                </div>
            </CardHeader>

            <CardContent>
                <div className="flex items-center justify-between mt-4">
                    {/* Radial Progress */}
                    <div className="relative size-24 flex items-center justify-center">
                        <svg className="absolute inset-0 -rotate-90" viewBox="0 0 100 100">
                            {/* Background circle */}
                            <circle
                                cx="50"
                                cy="50"
                                r="45"
                                fill="none"
                                stroke="var(--color-surface)"
                                strokeWidth="8"
                            />
                            {/* Progress circle */}
                            <circle
                                cx="50"
                                cy="50"
                                r="45"
                                fill="none"
                                stroke="var(--color-primary)"
                                strokeWidth="8"
                                strokeDasharray={`${(score / 100) * 283} 283`}
                                strokeLinecap="round"
                                className="transition-all duration-500"
                            />
                        </svg>
                        <div className="text-center z-10">
                            <motion.span
                                key={score}
                                initial={{ scale: 0.8, opacity: 0 }}
                                animate={{ scale: 1, opacity: 1 }}
                                className="text-2xl font-bold text-text block font-mono"
                            >
                                {Math.round(score)}
                            </motion.span>
                            <span className="text-[10px] text-text-muted uppercase tracking-wider">Score</span>
                        </div>
                    </div>

                    {/* Grade & Trend */}
                    <div className="space-y-2">
                        <div className="text-4xl font-black text-primary font-mono terminal-glow">
                            {grade}
                        </div>
                        <div className="flex items-center gap-1 text-xs text-success">
                            <TrendingUp className="w-3 h-3" />
                            <span>Improving</span>
                        </div>
                    </div>
                </div>

                {/* Iteration Progress */}
                <div className="mt-6 pt-4 border-t border-border space-y-3">
                    <div className="flex justify-between text-xs">
                        <span className="text-text-muted">Iteration Progress</span>
                        <span className="text-text font-mono">{currentIteration}/{maxIterations}</span>
                    </div>
                    <ProgressBar
                        value={currentIteration}
                        max={maxIterations}
                    />
                </div>
            </CardContent>
        </Card>
    );
}
