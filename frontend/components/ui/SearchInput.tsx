'use client';

import React, { useState, useCallback } from 'react';
import { Search, X } from 'lucide-react';
import { cn } from '@/lib/cn';

interface SearchInputProps {
    placeholder?: string;
    value?: string;
    onChange?: (value: string) => void;
    debounceMs?: number;
    className?: string;
}

export const SearchInput: React.FC<SearchInputProps> = ({
    placeholder = 'Search...',
    value: controlledValue,
    onChange,
    debounceMs = 300,
    className,
}) => {
    const [internalValue, setInternalValue] = useState(controlledValue || '');
    const [isLoading, setIsLoading] = useState(false);
    const debounceTimeout = React.useRef<NodeJS.Timeout | undefined>(undefined);

    const handleChange = useCallback((newValue: string) => {
        setInternalValue(newValue);
        setIsLoading(true);

        if (debounceTimeout.current) {
            clearTimeout(debounceTimeout.current);
        }

        debounceTimeout.current = setTimeout(() => {
            onChange?.(newValue);
            setIsLoading(false);
        }, debounceMs);
    }, [onChange, debounceMs]);

    const handleClear = () => {
        setInternalValue('');
        onChange?.('');
        setIsLoading(false);
    };

    return (
        <div className={cn('relative', className)}>
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
            <input
                type="text"
                value={internalValue}
                onChange={(e) => handleChange(e.target.value)}
                placeholder={placeholder}
                className="w-full pl-10 pr-10 py-2 bg-surface border border-border rounded-lg text-text placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
            />
            {internalValue && (
                <button
                    onClick={handleClear}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text transition-colors"
                >
                    <X className="w-4 h-4" />
                </button>
            )}
            {isLoading && (
                <div className="absolute right-10 top-1/2 -translate-y-1/2">
                    <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                </div>
            )}
        </div>
    );
};
