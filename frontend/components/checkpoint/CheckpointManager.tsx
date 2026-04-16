'use client';

import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent, Button, Badge } from '@/components/ui';
import { Save, RotateCcw, Trash2, Clock } from 'lucide-react';
import { useCrucibleStore } from '@/store/crucibleStore';
import { motion } from 'framer-motion';

export const CheckpointManager: React.FC = () => {
    const { checkpoints, createCheckpoint, restoreCheckpoint, deleteCheckpoint } = useCrucibleStore();
    const [selectedCheckpoint, setSelectedCheckpoint] = useState<string | null>(null);

    const handleCreate = () => {
        createCheckpoint();
    };

    const handleRestore = (id: string) => {
        restoreCheckpoint(id);
        setSelectedCheckpoint(id);
    };

    const handleDelete = (id: string) => {
        deleteCheckpoint(id);
        if (selectedCheckpoint === id) {
            setSelectedCheckpoint(null);
        }
    };

    return (
        <Card variant="elevated" padding="lg">
            <CardHeader>
                <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                        <Save className="w-4 h-4 text-primary" />
                        Checkpoints
                    </CardTitle>
                    <Button
                        variant="primary"
                        size="sm"
                        icon={<Save className="w-4 h-4" />}
                        onClick={handleCreate}
                    >
                        Create
                    </Button>
                </div>
            </CardHeader>

            <CardContent>
                <div className="space-y-3 mt-4">
                    {checkpoints.length === 0 ? (
                        <div className="text-center py-8 text-text-muted text-sm">
                            No checkpoints yet. Create one to save the current state.
                        </div>
                    ) : (
                        checkpoints.map((checkpoint, index) => (
                            <motion.div
                                key={checkpoint.id}
                                initial={{ opacity: 0, y: -10 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: index * 0.05 }}
                                className={`bg-surface p-3 rounded-lg border ${selectedCheckpoint === checkpoint.id ? 'border-primary' : 'border-border'
                                    } hover:border-border-hover transition-all cursor-pointer`}
                                onClick={() => setSelectedCheckpoint(checkpoint.id)}
                            >
                                <div className="flex items-start justify-between">
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2 mb-1">
                                            <Badge variant="default">
                                                Iteration {checkpoint.iteration}
                                            </Badge>
                                            <span className="text-xs text-text-muted">
                                                Score: {checkpoint.score}
                                            </span>
                                        </div>
                                        <div className="flex items-center gap-1 text-xs text-text-dim">
                                            <Clock className="w-3 h-3" />
                                            {new Date(checkpoint.timestamp).toLocaleString()}
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-2">
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            icon={<RotateCcw className="w-3 h-3" />}
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleRestore(checkpoint.id);
                                            }}
                                        >
                                            Restore
                                        </Button>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            icon={<Trash2 className="w-3 h-3" />}
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleDelete(checkpoint.id);
                                            }}
                                            className="text-critical hover:text-critical"
                                        >
                                            Delete
                                        </Button>
                                    </div>
                                </div>
                            </motion.div>
                        ))
                    )}
                </div>
            </CardContent>
        </Card>
    );
};
