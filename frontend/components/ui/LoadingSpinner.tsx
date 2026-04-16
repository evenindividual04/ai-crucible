import React from 'react';
import { cn } from '@/lib/cn';

/**
 * Loading Spinner component
 * Following .agent/skills/frontend-design guidelines
 */

interface LoadingSpinnerProps {
    size?: 'sm' | 'md' | 'lg';
    className?: string;
}

const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-8 w-8',
    lg: 'h-12 w-12',
};

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
    size = 'md',
    className
}) => {
    return (
        <div
            className={cn(
                "animate-spin rounded-full border-2 border-border border-t-primary",
                sizeClasses[size],
                className
            )}
            role="status"
            aria-label="Loading"
        >
            <span className="sr-only">Loading...</span>
        </div>
    );
};

/**
 * Progress Bar component
 */

interface ProgressBarProps {
    value: number; // 0-100
    max?: number;
    className?: string;
    showLabel?: boolean;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
    value,
    max = 100,
    className,
    showLabel = false
}) => {
    const percentage = Math.min(Math.max((value / max) * 100, 0), 100);

    return (
        <div className={cn("w-full", className)}>
            <div className="h-2 w-full rounded-full bg-surface overflow-hidden">
                <div
                    className="h-full bg-primary transition-all duration-300 ease-out"
                    style={{ width: `${percentage}%` }}
                    role="progressbar"
                    aria-valuenow={value}
                    aria-valuemin={0}
                    aria-valuemax={max}
                />
            </div>
            {showLabel && (
                <div className="mt-1 text-xs text-text-muted text-right">
                    {Math.round(percentage)}%
                </div>
            )}
        </div>
    );
};

/**
 * Pulse Dot component (for status indicators)
 */

interface PulseDotProps {
    color?: 'primary' | 'success' | 'warning' | 'error';
    size?: 'sm' | 'md';
    className?: string;
}

const colorClasses = {
    primary: 'bg-primary',
    success: 'bg-success',
    warning: 'bg-warning',
    error: 'bg-error',
};

const dotSizeClasses = {
    sm: 'h-2 w-2',
    md: 'h-3 w-3',
};

export const PulseDot: React.FC<PulseDotProps> = ({
    color = 'primary',
    size = 'md',
    className
}) => {
    return (
        <span className={cn("relative flex", dotSizeClasses[size], className)}>
            <span className={cn(
                "animate-ping absolute inline-flex h-full w-full rounded-full opacity-75",
                colorClasses[color]
            )} />
            <span className={cn(
                "relative inline-flex rounded-full",
                dotSizeClasses[size],
                colorClasses[color]
            )} />
        </span>
    );
};
