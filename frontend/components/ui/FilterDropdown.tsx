'use client';

import React, { useState } from 'react';
import { Filter, X } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Badge } from './Badge';

interface FilterOption {
    value: string;
    label: string;
}

interface FilterDropdownProps {
    label: string;
    options: FilterOption[];
    selected: string[];
    onChange: (selected: string[]) => void;
    className?: string;
}

export const FilterDropdown: React.FC<FilterDropdownProps> = ({
    label,
    options,
    selected,
    onChange,
    className,
}) => {
    const [isOpen, setIsOpen] = useState(false);

    const toggleOption = (value: string) => {
        if (selected.includes(value)) {
            onChange(selected.filter(v => v !== value));
        } else {
            onChange([...selected, value]);
        }
    };

    const clearAll = () => {
        onChange([]);
        setIsOpen(false);
    };

    return (
        <div className={cn('relative', className)}>
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center gap-2 px-4 py-2 bg-surface border border-border rounded-lg text-text hover:border-border-hover transition-all"
            >
                <Filter className="w-4 h-4" />
                <span className="text-sm">{label}</span>
                {selected.length > 0 && (
                    <span className="ml-1 px-1.5 py-0.5 text-xs bg-primary/20 text-primary rounded">
                        {selected.length}
                    </span>
                )}
            </button>

            {isOpen && (
                <>
                    {/* Backdrop */}
                    <div
                        className="fixed inset-0 z-10"
                        onClick={() => setIsOpen(false)}
                    />

                    {/* Dropdown */}
                    <div className="absolute top-full left-0 mt-2 w-64 bg-surface border border-border rounded-lg shadow-lg z-20 p-2">
                        <div className="flex items-center justify-between mb-2 px-2">
                            <span className="text-xs font-semibold text-text-muted uppercase">
                                {label}
                            </span>
                            {selected.length > 0 && (
                                <button
                                    onClick={clearAll}
                                    className="text-xs text-primary hover:text-primary-hover"
                                >
                                    Clear all
                                </button>
                            )}
                        </div>

                        <div className="space-y-1">
                            {options.map(option => (
                                <label
                                    key={option.value}
                                    className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-surface-hover cursor-pointer"
                                >
                                    <input
                                        type="checkbox"
                                        checked={selected.includes(option.value)}
                                        onChange={() => toggleOption(option.value)}
                                        className="w-4 h-4 rounded border-border bg-surface text-primary focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background cursor-pointer"
                                    />
                                    <span className="text-sm text-text">{option.label}</span>
                                </label>
                            ))}
                        </div>
                    </div>
                </>
            )}
        </div>
    );
};
