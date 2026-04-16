'use client';

import { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { motion } from 'framer-motion';
import { Server, Database, Cloud, Shield, Cpu, HardDrive } from 'lucide-react';

const iconMap: Record<string, any> = {
    service: Server,
    storage: Database,
    infrastructure: Cloud,
    security: Shield,
    cache: Cpu,
    default: HardDrive,
};

const riskStyles = {
    SECURE: {
        border: 'border-2 border-emerald-500',
        shadow: 'shadow-[0_0_15px_rgba(16,185,129,0.2)]',
        icon: 'text-emerald-500',
    },
    LOW: {
        border: 'border-2 border-emerald-500',
        shadow: 'shadow-[0_0_15px_rgba(16,185,129,0.2)]',
        icon: 'text-emerald-500',
    },
    MEDIUM: {
        border: 'border border-yellow-400',
        shadow: 'shadow-[0_0_15px_rgba(250,204,21,0.1)]',
        icon: 'text-yellow-400',
    },
    HIGH: {
        border: 'border-2 border-alert-orange',
        shadow: 'shadow-[0_0_20px_rgba(249,115,22,0.3)]',
        icon: 'text-alert-orange',
    },
    CRITICAL: {
        border: 'border-2 border-red-500',
        shadow: 'shadow-[0_0_20px_rgba(239,68,68,0.4)]',
        icon: 'text-red-500',
    },
};

const ComponentNode = ({ data }: NodeProps) => {
    const risk = data.riskLevel || 'SECURE';
    const styles = riskStyles[risk as keyof typeof riskStyles] || riskStyles.SECURE;
    const Icon = iconMap[data.type] || iconMap.default;

    return (
        <motion.div
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: 'spring', stiffness: 260, damping: 20 }}
            className="group"
        >
            <Handle
                type="target"
                position={Position.Top}
                className="w-2 h-2 bg-primary border-primary"
            />

            <div className={`
        size-16 bg-surface-dark rounded-xl flex items-center justify-center
        ${styles.border} ${styles.shadow}
        group-hover:scale-110 transition-transform cursor-pointer
      `}>
                <Icon className={`w-6 h-6 ${styles.icon}`} />
            </div>

            <div className="mt-2 text-center">
                <p className="text-[10px] font-bold font-mono text-white">{data.name}</p>
                <p className="text-[9px] text-slate-500">{data.type}</p>
            </div>

            {data.vulnerabilityCount > 0 && (
                <div className="absolute -top-2 -right-2 bg-red-600 text-white text-[9px] font-black px-1.5 py-0.5 rounded-full border-2 border-background-dark">
                    {data.vulnerabilityCount}
                </div>
            )}

            <Handle
                type="source"
                position={Position.Bottom}
                className="w-2 h-2 bg-primary border-primary"
            />
        </motion.div>
    );
};

ComponentNode.displayName = 'ComponentNode';

export default memo(ComponentNode);
