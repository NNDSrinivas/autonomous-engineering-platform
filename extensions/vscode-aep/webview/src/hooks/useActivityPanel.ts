import { useState, useCallback, useEffect, useRef } from 'react';
import type { ActivityStep, FileChange, CommandPreview } from '../components/ActivityPanel';

interface AgentRunMetadata {
  mode?: string;
  task_id?: string;
  status?: string;
  current_step?: number;
  total_steps?: number;
}

type ActivityPanelSnapshot = {
  steps: ActivityStep[];
  currentStep?: number;
  isVisible: boolean;
};

const STORAGE_KEY = "aep.navi.activityPanel.v1";

// NOTE: VS Code webview localStorage may not persist across reloads in all scenarios.
// For production-grade persistence, consider using VS Code webview state
// (acquireVsCodeApi().setState/getState) or backend persistence.
// Current implementation provides best-effort local caching.
const readSnapshot = (): ActivityPanelSnapshot | null => {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<ActivityPanelSnapshot>;
    return {
      steps: Array.isArray(parsed.steps) ? parsed.steps : [],
      currentStep: typeof parsed.currentStep === "number" ? parsed.currentStep : undefined,
      isVisible: Boolean(parsed.isVisible),
    };
  } catch {
    return null;
  }
};

const writeSnapshot = (snapshot: ActivityPanelSnapshot) => {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
  } catch {
    // ignore storage errors
  }
};

export function useActivityPanel() {
  const [steps, setSteps] = useState<ActivityStep[]>([]);
  const [currentStep, setCurrentStep] = useState<number | undefined>();
  const [isVisible, setIsVisible] = useState(false);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const MAX_COMMAND_PREVIEW = 800;

  // Restore persisted activity panel state
  useEffect(() => {
    const snapshot = readSnapshot();
    if (!snapshot) return;
    setSteps(snapshot.steps || []);
    setCurrentStep(snapshot.currentStep);
    setIsVisible(snapshot.isVisible);
  }, []);

  // Persist activity panel state (debounced)
  useEffect(() => {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    saveTimerRef.current = setTimeout(() => {
      writeSnapshot({ steps, currentStep, isVisible });
      saveTimerRef.current = null;
    }, 400);

    // Cleanup: clear timeout on unmount or dependency change
    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
        saveTimerRef.current = null;
      }
    };
  }, [steps, currentStep, isVisible]);

  const appendPreviewText = useCallback((current: string, addition: string) => {
    const next = `${current}${addition}`;
    if (next.length <= MAX_COMMAND_PREVIEW) {
      return { text: next, truncated: false };
    }
    return { text: next.slice(-MAX_COMMAND_PREVIEW), truncated: true };
  }, []);

  // Initialize steps from agentRun metadata
  const initializeSteps = useCallback((agentRun: AgentRunMetadata, planSteps?: any[]) => {
    if (agentRun.mode === 'autonomous_coding' && agentRun.total_steps) {
      const initialSteps: ActivityStep[] = [];

      // Use plan steps if available, otherwise create placeholders
      if (planSteps && planSteps.length > 0) {
        initialSteps.push(...planSteps.map((step, index) => ({
          id: `step-${index}`,
          description: step.description || `Step ${index + 1}`,
          status: 'pending' as const,
          fileChanges: step.file_path ? [{
            path: step.file_path,
            operation: step.operation || 'modify',
            status: 'pending' as const,
          }] : [],
          commands: [],
        })));
      } else {
        // Create placeholders
        for (let i = 0; i < agentRun.total_steps; i++) {
          initialSteps.push({
            id: `step-${i}`,
            description: `Step ${i + 1}`,
            status: 'pending',
            fileChanges: [],
            commands: [],
          });
        }
      }

      setSteps(initialSteps);
      setCurrentStep(agentRun.current_step || 0);
      setIsVisible(true);
    }
  }, []);

  // Update step status
  const updateStepStatus = useCallback((stepIndex: number, status: ActivityStep['status']) => {
    setSteps(prev => prev.map((step, idx) =>
      idx === stepIndex ? { ...step, status } : step
    ));
  }, []);

  // Mark a step as in progress and set it as current
  const updateStep = useCallback((stepIndex: number) => {
    setSteps(prev => prev.map((step, idx) => {
      if (idx !== stepIndex) return step;
      return {
        ...step,
        status: 'in_progress',
        startTime: step.startTime ?? Date.now(),
      };
    }));
    setCurrentStep(stepIndex);
  }, []);

  // Mark a step as completed and advance current step if possible
  const completeStep = useCallback((stepIndex: number) => {
    setSteps(prev => prev.map((step, idx) => {
      if (idx !== stepIndex) return step;
      return {
        ...step,
        status: 'completed',
        endTime: Date.now(),
      };
    }));
    setCurrentStep(prev => {
      const nextIndex = stepIndex + 1;
      if (nextIndex < steps.length) return nextIndex;
      return prev === stepIndex ? undefined : prev;
    });
  }, [steps.length]);

  // Update file change
  const updateFileChange = useCallback((
    stepIndex: number,
    filePath: string,
    update: Partial<FileChange>
  ) => {
    setSteps(prev => prev.map((step, idx) => {
      if (idx !== stepIndex) return step;

      const fileChanges = step.fileChanges.map(change =>
        change.path === filePath ? { ...change, ...update } : change
      );

      return { ...step, fileChanges };
    }));
  }, []);

  // Add file change to step
  const addFileChange = useCallback((stepIndex: number, fileChange: FileChange) => {
    setSteps(prev => prev.map((step, idx) => {
      if (idx !== stepIndex) return step;

      // Check if file already exists
      const existingIndex = step.fileChanges.findIndex(c => c.path === fileChange.path);
      if (existingIndex >= 0) {
        // Update existing
        const fileChanges = [...step.fileChanges];
        fileChanges[existingIndex] = { ...fileChanges[existingIndex], ...fileChange };
        return { ...step, fileChanges };
      } else {
        // Add new
        return { ...step, fileChanges: [...step.fileChanges, fileChange] };
      }
    }));
  }, []);

  const upsertCommand = useCallback((
    stepIndex: number,
    commandId: string,
    update: Partial<CommandPreview>
  ) => {
    setSteps(prev => prev.map((step, idx) => {
      if (idx !== stepIndex) return step;

      const commands = step.commands || [];
      const existingIndex = commands.findIndex(cmd => cmd.id === commandId);
      if (existingIndex >= 0) {
        const updated = {
          ...commands[existingIndex],
          ...update,
          id: commandId,
          updatedAt: Date.now(),
        };
        const next = [...commands];
        next[existingIndex] = updated;
        return { ...step, commands: next };
      }

      if (!update.command) return step;

      return {
        ...step,
        commands: [
          ...commands,
          {
            id: commandId,
            command: update.command,
            status: update.status || 'running',
            stdout: update.stdout,
            stderr: update.stderr,
            truncated: update.truncated,
            exitCode: update.exitCode,
            updatedAt: Date.now(),
          },
        ],
      };
    }));
  }, []);

  const appendCommandOutput = useCallback((
    stepIndex: number,
    commandId: string,
    text: string,
    stream: 'stdout' | 'stderr'
  ) => {
    setSteps(prev => prev.map((step, idx) => {
      if (idx !== stepIndex) return step;

      const commands = step.commands || [];
      const existingIndex = commands.findIndex(cmd => cmd.id === commandId);
      if (existingIndex < 0) return step;

      const command = commands[existingIndex];
      const current = stream === 'stderr' ? (command.stderr || '') : (command.stdout || '');
      const next = appendPreviewText(current, text);
      const updated = {
        ...command,
        stdout: stream === 'stdout' ? next.text : command.stdout,
        stderr: stream === 'stderr' ? next.text : command.stderr,
        truncated: command.truncated || next.truncated,
        updatedAt: Date.now(),
      };
      const nextCommands = [...commands];
      nextCommands[existingIndex] = updated;
      return { ...step, commands: nextCommands };
    }));
  }, [appendPreviewText]);

  const updateCommandStatus = useCallback((
    stepIndex: number,
    commandId: string,
    status: CommandPreview['status'],
    exitCode?: number
  ) => {
    setSteps(prev => prev.map((step, idx) => {
      if (idx !== stepIndex) return step;
      const commands = step.commands || [];
      const existingIndex = commands.findIndex(cmd => cmd.id === commandId);
      if (existingIndex < 0) return step;

      const updated = {
        ...commands[existingIndex],
        status,
        exitCode: exitCode ?? commands[existingIndex].exitCode,
        updatedAt: Date.now(),
      };
      const nextCommands = [...commands];
      nextCommands[existingIndex] = updated;
      return { ...step, commands: nextCommands };
    }));
  }, []);

  // Parse progress updates from backend
  const parseProgressUpdate = useCallback((content: string, agentRun?: AgentRunMetadata) => {
    // Look for step execution markers
    const stepMatch = content.match(/⏳ \*\*Step (\d+)\/(\d+):\*\* (.+)/);
    if (stepMatch) {
      const stepNum = parseInt(stepMatch[1]) - 1; // 0-indexed
      const description = stepMatch[3];

      setSteps(prev => prev.map((step, idx) => {
        if (idx === stepNum) {
          return { ...step, description, status: 'in_progress', startTime: Date.now() };
        } else if (idx < stepNum) {
          return { ...step, status: 'completed', endTime: Date.now() };
        }
        return step;
      }));
      setCurrentStep(stepNum);
    }

    // Look for file operations
    const fileMatch = content.match(/📝 Working on: `([^`]+)`/);
    if (fileMatch && currentStep !== undefined) {
      const filePath = fileMatch[1];
      addFileChange(currentStep, {
        path: filePath,
        operation: 'modify', // Default, will be updated
        status: 'in_progress',
      });
    }

    // Look for completion
    if (content.includes('✅ **All steps execution completed!**') ||
        content.includes('🎉 **All steps completed!**')) {
      setSteps(prev => prev.map(step => ({
        ...step,
        status: 'completed',
        endTime: Date.now(),
      })));
      setCurrentStep(undefined);
    }

    // Parse git diff stats
    const diffMatches = content.matchAll(/`([^`]+)`.*?<span style='color:#22c55e'>\+(\d+)<\/span>.*?<span style='color:#ef4444'>-(\d+)<\/span>/g);
    for (const match of diffMatches) {
      const [, filePath, additions, deletions] = match;
      // Find which step this file belongs to
      const stepIdx = steps.findIndex(s =>
        s.fileChanges.some(c => c.path === filePath)
      );
      if (stepIdx >= 0) {
        updateFileChange(stepIdx, filePath, {
          additions: parseInt(additions),
          deletions: parseInt(deletions),
          status: 'completed',
        });
      }
    }
  }, [currentStep, steps, addFileChange, updateFileChange]);

  // Clear activity panel
  const clearActivity = useCallback(() => {
    setSteps([]);
    setCurrentStep(undefined);
    setIsVisible(false);
  }, []);

  // Toggle visibility
  const toggleVisibility = useCallback(() => {
    setIsVisible(prev => !prev);
  }, []);

  return {
    steps,
    currentStep,
    isVisible,
    initializeSteps,
    updateStep,
    completeStep,
    updateStepStatus,
    updateFileChange,
    addFileChange,
    upsertCommand,
    appendCommandOutput,
    updateCommandStatus,
    parseProgressUpdate,
    clearActivity,
    toggleVisibility,
    setIsVisible,
  };
}
