import React from 'react';
import { cn } from '@/lib/cn';

/**
 * Input component with focus glow and error states
 * Following .agent/skills/frontend-design guidelines
 */

export interface InputProps
    extends React.InputHTMLAttributes<HTMLInputElement> {
    error?: boolean;
    icon?: React.ReactNode;
    iconPosition?: 'left' | 'right';
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
    ({ className, type, error, icon, iconPosition = 'left', ...props }, ref) => {
        const hasIcon = !!icon;

        return (
            <div className="relative w-full">
                {hasIcon && iconPosition === 'left' && (
                    <div className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted">
                        {icon}
                    </div>
                )}

                <input
                    type={type}
                    className={cn(
                        "flex h-10 w-full rounded-lg border bg-surface px-3 py-2 text-sm text-text transition-all duration-200",
                        "placeholder:text-text-dim",
                        "focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background",
                        "disabled:cursor-not-allowed disabled:opacity-50",
                        error
                            ? "border-error focus:ring-error"
                            : "border-border focus:border-primary",
                        hasIcon && iconPosition === 'left' && "pl-10",
                        hasIcon && iconPosition === 'right' && "pr-10",
                        className
                    )}
                    ref={ref}
                    {...props}
                />

                {hasIcon && iconPosition === 'right' && (
                    <div className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted">
                        {icon}
                    </div>
                )}
            </div>
        );
    }
);

Input.displayName = "Input";

export { Input };
