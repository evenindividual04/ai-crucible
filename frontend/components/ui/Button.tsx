import React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/cn';
import { Loader2 } from 'lucide-react';

/**
 * Button component with variants following .agent/skills/frontend-design guidelines
 * - cursor-pointer on all clickable elements
 * - Smooth transitions (150-300ms)
 * - No layout-shifting hover effects
 */

const buttonVariants = cva(
    // Base styles
    "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 cursor-pointer",
    {
        variants: {
            variant: {
                primary: "bg-primary text-black hover:bg-primary-hover shadow-glow-sm hover:shadow-glow",
                secondary: "border-2 border-primary text-primary hover:bg-primary/10",
                ghost: "text-text-muted hover:text-text hover:bg-surface",
                danger: "bg-critical text-white hover:bg-critical/90",
                success: "bg-success text-white hover:bg-success/90",
            },
            size: {
                sm: "h-8 px-3 text-sm",
                md: "h-10 px-4 text-base",
                lg: "h-12 px-6 text-lg",
            },
        },
        defaultVariants: {
            variant: "primary",
            size: "md",
        },
    }
);

export interface ButtonProps
    extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
    loading?: boolean;
    icon?: React.ReactNode;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
    ({ className, variant, size, loading, icon, children, disabled, ...props }, ref) => {
        return (
            <button
                className={cn(buttonVariants({ variant, size, className }))}
                ref={ref}
                disabled={disabled || loading}
                {...props}
            >
                {loading && <Loader2 className="h-4 w-4 animate-spin" />}
                {!loading && icon && icon}
                {children}
            </button>
        );
    }
);

Button.displayName = "Button";

export { Button, buttonVariants };
