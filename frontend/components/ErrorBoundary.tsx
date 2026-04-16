'use client';

import React, { Component, ErrorInfo, ReactNode } from 'react';
import { Card, CardHeader, CardTitle, CardContent, Button } from '@/components/ui';
import { AlertTriangle, RotateCcw } from 'lucide-react';

interface Props {
    children: ReactNode;
    fallback?: ReactNode;
}

interface State {
    hasError: boolean;
    error?: Error;
}

/**
 * ErrorBoundary component - catches and displays errors gracefully
 * Following React error boundary best practices
 */
export class ErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false };
    }

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error('ErrorBoundary caught an error:', error, errorInfo);
    }

    handleReset = () => {
        this.setState({ hasError: false, error: undefined });
    };

    render() {
        if (this.state.hasError) {
            if (this.props.fallback) {
                return this.props.fallback;
            }

            return (
                <div className="min-h-screen bg-background flex items-center justify-center p-6">
                    <Card variant="elevated" padding="lg" className="max-w-md w-full">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2 text-critical">
                                <AlertTriangle className="w-5 h-5" />
                                Something went wrong
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-4 mt-4">
                                <p className="text-text-muted text-sm">
                                    An unexpected error occurred. Please try refreshing the page or contact support if the problem persists.
                                </p>

                                {this.state.error && (
                                    <div className="bg-surface p-3 rounded-lg border border-border">
                                        <p className="text-xs font-mono text-text-dim break-all">
                                            {this.state.error.message}
                                        </p>
                                    </div>
                                )}

                                <div className="flex gap-3">
                                    <Button
                                        variant="primary"
                                        onClick={this.handleReset}
                                        icon={<RotateCcw className="w-4 h-4" />}
                                    >
                                        Try Again
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        onClick={() => window.location.href = '/'}
                                    >
                                        Go Home
                                    </Button>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            );
        }

        return this.props.children;
    }
}
