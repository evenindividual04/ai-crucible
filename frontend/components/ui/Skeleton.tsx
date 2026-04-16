import React from 'react';
import { cn } from '@/lib/cn';

/**
 * Skeleton loading components
 * Following .agent/skills/frontend-design guidelines
 */

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> { }

export const Skeleton: React.FC<SkeletonProps> = ({ className, ...props }) => {
    return (
        <div
            className={cn(
                "animate-pulse rounded-md bg-surface",
                className
            )}
            {...props}
        />
    );
};

// Preset skeleton components for common use cases

export const SkeletonCard: React.FC<{ className?: string }> = ({ className }) => {
    return (
        <div className={cn("rounded-lg border border-border p-4 space-y-3", className)}>
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-5/6" />
        </div>
    );
};

export const SkeletonText: React.FC<{ lines?: number; className?: string }> = ({
    lines = 3,
    className
}) => {
    return (
        <div className={cn("space-y-2", className)}>
            {Array.from({ length: lines }).map((_, i) => (
                <Skeleton
                    key={i}
                    className={cn(
                        "h-3",
                        i === lines - 1 ? "w-4/5" : "w-full"
                    )}
                />
            ))}
        </div>
    );
};

export const SkeletonNode: React.FC<{ className?: string }> = ({ className }) => {
    return (
        <div className={cn("rounded-lg border border-border p-3 space-y-2", className)}>
            <div className="flex items-center gap-2">
                <Skeleton className="h-8 w-8 rounded-full" />
                <Skeleton className="h-4 w-24" />
            </div>
            <Skeleton className="h-3 w-full" />
        </div>
    );
};

export const SkeletonPanel: React.FC<{ className?: string }> = ({ className }) => {
    return (
        <div className={cn("space-y-4", className)}>
            <Skeleton className="h-6 w-32" />
            <div className="space-y-2">
                <SkeletonCard />
                <SkeletonCard />
                <SkeletonCard />
            </div>
        </div>
    );
};
