'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { Clock, CheckCircle2, AlertTriangle } from 'lucide-react';

interface TimelineEvent {
    id: string;
    type: 'checkpoint' | 'vulnerability' | 'iteration' | 'agent_action';
    title: string;
    description?: string;
    timestamp: string;
    severity?: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
}

interface RunTimelineProps {
    events: TimelineEvent[];
}

export const RunTimeline: React.FC<RunTimelineProps> = ({ events }) => {
    const getIcon = (type: string, severity?: string) => {
        if (type === 'checkpoint') return CheckCircle2;
        if (type === 'vulnerability') return AlertTriangle;
        return Clock;
    };

    const getColor = (type: string, severity?: string) => {
        if (type === 'checkpoint') return 'text-primary border-primary';
        if (type === 'vulnerability') {
            if (severity === 'CRITICAL') return 'text-critical border-critical';
            if (severity === 'HIGH') return 'text-high border-high';
            if (severity === 'MEDIUM') return 'text-warning border-warning';
            return 'text-low border-low';
        }
        return 'text-text-muted border-border';
    };

    return (
        <div className="relative">
            {/* Timeline line */}
            <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-border" />

            {/* Events */}
            <div className="space-y-6">
                {events.map((event, index) => {
                    const Icon = getIcon(event.type, event.severity);
                    const colorClass = getColor(event.type, event.severity);

                    return (
                        <motion.div
                            key={event.id}
                            initial={{ opacity: 0, x: -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: index * 0.05 }}
                            className="relative pl-12"
                        >
                            {/* Icon */}
                            <div className={`absolute left-0 w-8 h-8 rounded-full bg-surface border-2 ${colorClass} flex items-center justify-center`}>
                                <Icon className="w-4 h-4" />
                            </div>

                            {/* Content */}
                            <div className="bg-surface p-4 rounded-lg border border-border">
                                <div className="flex items-start justify-between mb-1">
                                    <h4 className="text-sm font-semibold text-text">{event.title}</h4>
                                    <span className="text-xs text-text-muted">{event.timestamp}</span>
                                </div>
                                {event.description && (
                                    <p className="text-xs text-text-muted mt-1">{event.description}</p>
                                )}
                            </div>
                        </motion.div>
                    );
                })}
            </div>
        </div>
    );
};
