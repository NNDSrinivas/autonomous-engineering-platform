import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

export interface ProgressStep {
    id: string;
    title: string;
    status: 'pending' | 'active' | 'completed' | 'error';
    progress: number;
    timestamp: number;
    details?: string;
}

interface LiveProgressState {
    // State
    steps: ProgressStep[];
    currentStepId: string | null;
    isActive: boolean;
    globalProgress: number;

    // Actions
    startStep: (title: string, details?: string) => string;
    updateStep: (stepId: string, progress: number, details?: string) => void;
    completeStep: (stepId: string, details?: string) => void;
    errorStep: (stepId: string, error: string) => void;
    clearSteps: () => void;
    setGlobalProgress: (progress: number) => void;

    // Computed
    getActiveStep: () => ProgressStep | null;
    getCompletedSteps: () => ProgressStep[];
    getTotalProgress: () => number;
}

export const useLiveProgress = create<LiveProgressState>()(
    devtools(
        (set, get) => ({
            // Initial state
            steps: [],
            currentStepId: null,
            isActive: false,
            globalProgress: 0,

            // Start a new progress step
            startStep: (title: string, details?: string) => {
                const stepId = `step_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
                const newStep: ProgressStep = {
                    id: stepId,
                    title,
                    status: 'active',
                    progress: 0,
                    timestamp: Date.now(),
                    details
                };

                set((state) => ({
                    steps: [...state.steps, newStep],
                    currentStepId: stepId,
                    isActive: true
                }));

                return stepId;
            },

            // Update progress for a specific step
            updateStep: (stepId: string, progress: number, details?: string) => {
                set((state) => ({
                    steps: state.steps.map(step =>
                        step.id === stepId
                            ? { ...step, progress: Math.min(100, Math.max(0, progress)), details: details || step.details }
                            : step
                    )
                }));
            },

            // Mark a step as completed
            completeStep: (stepId: string, details?: string) => {
                set((state) => {
                    const updatedSteps = state.steps.map(step =>
                        step.id === stepId
                            ? { ...step, status: 'completed' as const, progress: 100, details: details || step.details }
                            : step
                    );

                    // Check if this was the current step
                    const isCurrentStep = state.currentStepId === stepId;
                    const hasActiveSteps = updatedSteps.some(step => step.status === 'active');

                    return {
                        steps: updatedSteps,
                        currentStepId: isCurrentStep && !hasActiveSteps ? null : state.currentStepId,
                        isActive: hasActiveSteps
                    };
                });
            },

            // Mark a step as error
            errorStep: (stepId: string, error: string) => {
                set((state) => ({
                    steps: state.steps.map(step =>
                        step.id === stepId
                            ? { ...step, status: 'error' as const, details: error }
                            : step
                    ),
                    currentStepId: state.currentStepId === stepId ? null : state.currentStepId,
                    isActive: state.steps.some(s => s.status === 'active' && s.id !== stepId)
                }));
            },

            // Clear all steps
            clearSteps: () => {
                set({
                    steps: [],
                    currentStepId: null,
                    isActive: false,
                    globalProgress: 0
                });
            },

            // Set global progress (0-100)
            setGlobalProgress: (progress: number) => {
                set({ globalProgress: Math.min(100, Math.max(0, progress)) });
            },

            // Get currently active step
            getActiveStep: () => {
                const { steps, currentStepId } = get();
                return steps.find(step => step.id === currentStepId) || null;
            },

            // Get all completed steps
            getCompletedSteps: () => {
                return get().steps.filter(step => step.status === 'completed');
            },

            // Calculate total progress across all steps
            getTotalProgress: () => {
                const { steps, globalProgress } = get();

                if (globalProgress > 0) {
                    return globalProgress;
                }

                if (steps.length === 0) return 0;

                const totalProgress = steps.reduce((sum, step) => sum + step.progress, 0);
                return Math.round(totalProgress / steps.length);
            }
        }),
        {
            name: 'live-progress-store'
        }
    )
);

// Hook for convenient usage in components
export const useLiveProgressState = () => {
    const {
        steps,
        currentStepId,
        isActive,
        globalProgress,
        getActiveStep,
        getCompletedSteps,
        getTotalProgress
    } = useLiveProgress();

    return {
        steps,
        currentStepId,
        isActive,
        globalProgress,
        activeStep: getActiveStep(),
        completedSteps: getCompletedSteps(),
        totalProgress: getTotalProgress()
    };
};

// Helper hook for step management
export const useLiveProgressActions = () => {
    const {
        startStep,
        updateStep,
        completeStep,
        errorStep,
        clearSteps,
        setGlobalProgress
    } = useLiveProgress();

    return {
        startStep,
        updateStep,
        completeStep,
        errorStep,
        clearSteps,
        setGlobalProgress
    };
};

// SSE integration helper
export const useSSEProgress = () => {
    const { startStep, updateStep, completeStep, errorStep, setGlobalProgress } = useLiveProgressActions();

    const connectToSSE = (url: string, onComplete?: (data: any) => void) => {
        let currentStepId: string | null = null;

        const eventSource = new EventSource(url);

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                switch (data.type) {
                    case 'progress':
                        if (!currentStepId || data.step !== getCurrentStepTitle()) {
                            if (currentStepId) {
                                completeStep(currentStepId);
                            }
                            currentStepId = startStep(data.step);
                        }

                        if (currentStepId && data.progress !== undefined) {
                            updateStep(currentStepId, data.progress);
                            setGlobalProgress(data.progress);
                        }
                        break;

                    case 'complete':
                        if (currentStepId) {
                            completeStep(currentStepId, data.step || 'Complete');
                        }
                        setGlobalProgress(100);
                        eventSource.close();
                        onComplete?.(data);
                        break;

                    case 'error':
                        if (currentStepId) {
                            errorStep(currentStepId, data.message || 'Error occurred');
                        }
                        eventSource.close();
                        break;
                }
            } catch (parseError) {
                console.warn('Failed to parse SSE data:', event.data);
            }
        };

        eventSource.onerror = (error) => {
            console.error('SSE connection error:', error);
            if (currentStepId) {
                errorStep(currentStepId, 'Connection error');
            }
            eventSource.close();
        };

        // Return cleanup function
        return () => {
            eventSource.close();
            if (currentStepId) {
                errorStep(currentStepId, 'Connection closed');
            }
        };
    };

    const getCurrentStepTitle = () => {
        const activeStep = useLiveProgress.getState().getActiveStep();
        return activeStep?.title || '';
    };

    return { connectToSSE };
};

export default useLiveProgress;