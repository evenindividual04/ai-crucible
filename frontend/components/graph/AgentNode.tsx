'use client';

import { memo } from 'react';
import { NodeProps } from 'reactflow';
import { motion } from 'framer-motion';
import { Shield, Zap } from 'lucide-react';

const AgentNode = ({ data }: NodeProps) => {
    const isRedTeam = data.type === 'RED_TEAM';

    return (
        <motion.div
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: 'spring', stiffness: 260, damping: 20 }}
            className="group"
        >
            <div className={`
        size-14 bg-surface rounded-xl flex items-center justify-center
        ${isRedTeam
                    ? 'border-2 border-high shadow-[0_0_15px_rgba(249,115,22,0.2)]'
                    : 'border-2 border-primary shadow-[0_0_15px_rgba(0,217,163,0.2)]'
                }
        group-hover:scale-110 transition-transform cursor-pointer
      `}>
                {isRedTeam ? (
                    <Zap className="w-5 h-5 text-high" strokeWidth={2.5} />
                ) : (
                    <Shield className="w-5 h-5 text-primary" strokeWidth={2.5} />
                )}
            </div>

            <div className="mt-2 text-center">
                <p className="text-[10px] font-bold font-mono text-text">{data.name}</p>
                <p className={`text-[9px] ${isRedTeam ? 'text-high' : 'text-primary'}`}>
                    {isRedTeam ? 'Attacker' : 'Defender'}
                </p>
            </div>
        </motion.div>
    );
};

AgentNode.displayName = 'AgentNode';

export default memo(AgentNode);
