import React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/cn';

/**
 * Badge component for severity levels, agent states, and status indicators
 * Following .agent/skills/frontend-design guidelines
 */

const badgeVariants = cva(
    "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider transition-colors duration-200",
    {
        variants: {
            variant: {
                // Severity levels
                critical: "bg-critical/10 border border-critical/20 text-critical",
                high: "bg-high/10 border border-high/20 text-high",
                medium: "bg-medium/10 border border-medium/20 text-medium",
                low: "bg-low/10 border border-low/20 text-low",
                secure: "bg-secure/10 border border-secure/20 text-secure",

                // Agent states
                active: "bg-success/10 border border-success/20 text-success",
                idle: "bg-text-dim/10 border border-text-dim/20 text-text-dim",
                attacking: "bg-critical/10 border border-critical/20 text-critical",
                defending: "bg-primary/10 border border-primary/20 text-primary",

                // Connection status
                connected: "bg-success/10 border border-success/20 text-success",
                connecting: "bg-warning/10 border border-warning/20 text-warning",
                disconnected: "bg-error/10 border border-error/20 text-error",

                // Generic
                default: "bg-surface border border-border text-text",
                outline: "border border-border text-text-muted",
            },
        },
        defaultVariants: {
            variant: "default",
        },
    }
);

export interface BadgeProps
    extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {
    pulse?: boolean;
    icon?: React.ReactNode;
}

const Badge = React.forwardRef<HTMLDivElement, BadgeProps>(
    ({ className, variant, pulse, icon, children, ...props }, ref) => {
        return (
            <div
                ref={ref}
                className={cn(badgeVariants({ variant, className }))}
                {...props}
            >
                {pulse && (
                    <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-current opacity-75" />
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-current" />
                    </span>
                )}
                {!pulse && icon && icon}
                {children}
            </div>
        );
    }
);

Badge.displayName = "Badge";

export { Badge, badgeVariants };
