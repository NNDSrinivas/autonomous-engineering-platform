/**
 * NAVI Activity Stream Hook
 *
 * Handles ordered streaming events from the NAVI backend.
 * Events are processed in sequence order to ensure correct display.
 *
 * Event types:
 * - activity: File reads, tool executions, status updates
 * - narrative: LLM-generated explanations (Claude Code-style)
 * - thinking: Real-time thinking/reasoning display
 * - intent: Detected user intent with confidence
 */

import { useState, useCallback, useRef, useEffect } from 'react';

// Event types matching backend StreamEventType
export type StreamEventType =
  | 'thinking_start'
  | 'thinking_delta'
  | 'thinking_complete'
  | 'tool_start'
  | 'tool_delta'
  | 'tool_complete'
  | 'file_read'
  | 'file_write'
  | 'file_edit'
  | 'navi.narrative'
  | 'intent.detected'
  | 'activity'
  | 'context'
  | 'detection'
  | 'rag'
  | 'response'
  | 'result'
  | 'error'
  // NEW: Unified agent event types
  | 'thinking'
  | 'text'
  | 'tool_call'
  | 'tool_result'
  | 'verification'
  | 'fixing'
  | 'phase_change'
  | 'done';

// Activity status
export type ActivityStatus = 'running' | 'done' | 'error';

// Activity kind
export type ActivityKind =
  | 'read'
  | 'create'
  | 'edit'
  | 'delete'
  | 'thinking'
  | 'context'
  | 'detection'
  | 'rag'
  | 'llm_call'
  | 'prompt'
  | 'parsing'
  | 'validation'
  | 'response'
  | 'intent'
  | 'tool'
  | 'info'
  | 'error'
  | 'recovery'
  | 'command'       // Running shell commands
  | 'search'        // Searching files
  | 'tool_result'   // Tool execution result
  | 'verification'  // NEW: Running verification (typecheck, tests, build)
  | 'fixing';       // NEW: Agent is fixing verification errors

// Single activity event
export interface ActivityEvent {
  id: string;
  kind: ActivityKind;
  label: string;
  detail: string;
  filePath?: string;
  toolId?: string;
  status: ActivityStatus;
  timestamp: string;
  sequence?: number;
}

// Tool activity with lifecycle
export interface ToolActivity {
  id: string;
  name: string;
  description: string;
  status: ActivityStatus;
  startTime: number;
  endTime?: number;
  result?: Record<string, unknown>;
}

// Detected intent
export interface DetectedIntent {
  family: string;
  kind: string;
  confidence: number;
}

// Narrative entry
export interface NarrativeEntry {
  id: string;
  content: string;
  phase: string;
  timestamp: string;
}

// Tool output from unified agent
export interface ToolOutput {
  type: 'stdout' | 'stderr' | 'file_content';
  content: string;
  path?: string;
}

// Done event summary
export interface DoneSummary {
  task_id: string;
  iterations: number;
  files_read: string[];
  files_modified: string[];
  files_created: string[];
  commands_run: string[];
  verification_passed?: boolean;
  verification_attempts?: number;
  max_iterations_reached?: boolean;
}

// Verification result
export interface VerificationResultItem {
  type: string;
  success: boolean;
  errors: string[];
  output?: string;
}

// Verification event data
export interface VerificationEvent {
  status: 'running' | 'complete';
  success?: boolean;
  commands?: Record<string, string>;
  results?: VerificationResultItem[];
}

// Stream event from backend
export interface StreamEvent {
  type?: StreamEventType;
  data?: Record<string, unknown>;
  sequence?: number;
  timestamp?: string;
  // Direct event fields (alternative format)
  activity?: {
    kind: ActivityKind;
    label: string;
    detail: string;
    filePath?: string;
    toolId?: string;
    tool_id?: string;  // Alternative naming from unified agent
    status: ActivityStatus;
    sequence?: number;
  };
  narrative?: string;
  thinking?: string;
  intent?: {
    family: string;
    kind: string;
    confidence: number;
  };
  // NEW: Unified agent event types
  content?: string;           // Text content from LLM
  tool_output?: ToolOutput;   // Tool execution output
  done?: DoneSummary;         // Execution complete summary
  router_info?: {             // LLM routing info
    provider: string;
    model: string;
    mode: string;
  };
}

// State shape
export interface NaviActivityState {
  isThinking: boolean;
  currentPhase: 'idle' | 'thinking' | 'reading' | 'executing' | 'verifying' | 'fixing' | 'complete';
  activities: ActivityEvent[];
  tools: ToolActivity[];
  narratives: NarrativeEntry[];
  detectedIntent: DetectedIntent | null;
  filesRead: string[];
  filesModified: string[];
  filesCreated: string[];       // Track created files
  commandsRun: string[];
  toolOutputs: ToolOutput[];
  doneSummary: DoneSummary | null;
  lastError: string | null;
  // Verification tracking
  verificationResults: VerificationResultItem[];
  verificationPassed: boolean | null;
  verificationAttempts: number;
}

// Initial state
const initialState: NaviActivityState = {
  isThinking: false,
  currentPhase: 'idle',
  activities: [],
  tools: [],
  narratives: [],
  detectedIntent: null,
  filesRead: [],
  filesModified: [],
  filesCreated: [],
  commandsRun: [],
  toolOutputs: [],
  doneSummary: null,
  lastError: null,
  verificationResults: [],
  verificationPassed: null,
  verificationAttempts: 0,
};

// Generate unique ID
let idCounter = 0;
const generateId = (): string => {
  idCounter += 1;
  return `activity-${Date.now()}-${idCounter}`;
};

/**
 * Hook for managing NAVI activity stream state
 */
export function useNaviActivityStream() {
  const [state, setState] = useState<NaviActivityState>(initialState);
  const eventBufferRef = useRef<StreamEvent[]>([]);
  const lastSequenceRef = useRef<number>(0);

  /**
   * Process events from the buffer in sequence order
   */
  const flushEventBuffer = useCallback(() => {
    if (eventBufferRef.current.length === 0) return;

    // Sort by sequence number if available
    eventBufferRef.current.sort((a, b) => {
      const seqA = a.sequence ?? a.activity?.sequence ?? 0;
      const seqB = b.sequence ?? b.activity?.sequence ?? 0;
      return seqA - seqB;
    });

    // Process all buffered events
    const events = [...eventBufferRef.current];
    eventBufferRef.current = [];

    for (const event of events) {
      processEventInternal(event);
    }
  }, []);

  /**
   * Internal event processor
   */
  const processEventInternal = useCallback((event: StreamEvent) => {
    setState((prev) => {
      const now = new Date().toISOString();

      // Handle activity events (most common)
      if (event.activity) {
        const activity = event.activity;
        // Support both toolId and tool_id (unified agent uses tool_id)
        const toolId = activity.toolId || activity.tool_id;
        const activityEvent: ActivityEvent = {
          id: toolId || generateId(),
          kind: activity.kind,
          label: activity.label,
          detail: activity.detail,
          filePath: activity.filePath,
          toolId: toolId,
          status: activity.status,
          timestamp: now,
          sequence: activity.sequence,
        };

        // Check if we should update an existing activity or add new
        const existingIdx = prev.activities.findIndex(
          (a) =>
            (a.toolId && a.toolId === activity.toolId) ||
            (a.kind === activity.kind &&
              a.detail === activity.detail &&
              a.status === 'running')
        );

        let newActivities: ActivityEvent[];
        if (existingIdx >= 0) {
          // Update existing activity (e.g., running -> done)
          newActivities = [...prev.activities];
          newActivities[existingIdx] = {
            ...newActivities[existingIdx],
            ...activityEvent,
          };
        } else {
          newActivities = [...prev.activities, activityEvent];
        }

        // Track files read
        let newFilesRead = prev.filesRead;
        if (
          activity.kind === 'read' &&
          activity.status === 'done' &&
          activity.filePath
        ) {
          if (!prev.filesRead.includes(activity.filePath)) {
            newFilesRead = [...prev.filesRead, activity.filePath];
          }
        }

        // Update phase based on activity kind
        let newPhase = prev.currentPhase;
        if (activity.kind === 'thinking' && activity.status === 'running') {
          newPhase = 'thinking';
        } else if (activity.kind === 'read' && activity.status === 'running') {
          newPhase = 'reading';
        } else if (
          activity.kind === 'llm_call' ||
          activity.kind === 'tool'
        ) {
          newPhase = 'executing';
        } else if (
          activity.kind === 'response' &&
          activity.status === 'done'
        ) {
          newPhase = 'complete';
        }

        return {
          ...prev,
          activities: newActivities,
          filesRead: newFilesRead,
          currentPhase: newPhase,
          isThinking:
            activity.kind === 'thinking' && activity.status === 'running',
        };
      }

      // Handle narrative events
      if (event.narrative) {
        const narrativeEntry: NarrativeEntry = {
          id: generateId(),
          content: event.narrative,
          phase: (event as any).phase || 'explaining',
          timestamp: now,
        };
        return {
          ...prev,
          narratives: [...prev.narratives, narrativeEntry],
        };
      }

      // Handle thinking events
      if (event.thinking) {
        // Find or create thinking activity
        const thinkingIdx = prev.activities.findIndex(
          (a) => a.kind === 'thinking' && a.status === 'running'
        );

        if (thinkingIdx >= 0) {
          const newActivities = [...prev.activities];
          newActivities[thinkingIdx] = {
            ...newActivities[thinkingIdx],
            detail: (
              (newActivities[thinkingIdx].detail || '') + event.thinking
            ).slice(-500),
          };
          return {
            ...prev,
            activities: newActivities,
            isThinking: true,
            currentPhase: 'thinking',
          };
        }

        // Create new thinking activity
        return {
          ...prev,
          activities: [
            ...prev.activities,
            {
              id: generateId(),
              kind: 'thinking' as ActivityKind,
              label: 'Thinking',
              detail: event.thinking.slice(-500),
              status: 'running' as ActivityStatus,
              timestamp: now,
            },
          ],
          isThinking: true,
          currentPhase: 'thinking',
        };
      }

      // Handle intent detection
      if (event.intent) {
        return {
          ...prev,
          detectedIntent: {
            family: event.intent.family,
            kind: event.intent.kind,
            confidence: event.intent.confidence,
          },
        };
      }

      // Handle tool_output events (from unified agent)
      if (event.tool_output) {
        return {
          ...prev,
          toolOutputs: [...prev.toolOutputs, event.tool_output],
        };
      }

      // Handle done events (from unified agent)
      if (event.done) {
        return {
          ...prev,
          doneSummary: event.done,
          filesRead: event.done.files_read || prev.filesRead,
          filesModified: event.done.files_modified || prev.filesModified,
          filesCreated: event.done.files_created || prev.filesCreated,
          commandsRun: event.done.commands_run || prev.commandsRun,
          verificationPassed: event.done.verification_passed ?? prev.verificationPassed,
          verificationAttempts: event.done.verification_attempts ?? prev.verificationAttempts,
          isThinking: false,
          currentPhase: 'complete',
          // Mark all running activities as complete
          activities: prev.activities.map((a) =>
            a.status === 'running' ? { ...a, status: 'done' as ActivityStatus } : a
          ),
        };
      }

      // Handle verification events (from unified agent)
      if ((event as any).verification) {
        const verificationData = (event as any).verification as VerificationEvent;
        const isRunning = verificationData.status === 'running';

        const activityEvent: ActivityEvent = {
          id: generateId(),
          kind: 'verification' as ActivityKind,
          label: isRunning ? 'Running verification' : 'Verification complete',
          detail: isRunning
            ? `Checking: ${Object.keys(verificationData.commands || {}).join(', ')}`
            : verificationData.success ? '✅ All checks passed' : '❌ Some checks failed',
          status: isRunning ? 'running' : (verificationData.success ? 'done' : 'error') as ActivityStatus,
          timestamp: now,
        };

        return {
          ...prev,
          currentPhase: isRunning ? 'verifying' : (verificationData.success ? 'complete' : 'fixing'),
          verificationResults: verificationData.results || prev.verificationResults,
          verificationPassed: verificationData.success ?? prev.verificationPassed,
          activities: [...prev.activities, activityEvent],
        };
      }

      // Handle fixing events (from unified agent)
      if ((event as any).fixing) {
        const fixingData = (event as any).fixing;

        const activityEvent: ActivityEvent = {
          id: generateId(),
          kind: 'fixing' as ActivityKind,
          label: 'Fixing errors',
          detail: `Attempt ${fixingData.attempt}/${fixingData.max_attempts}`,
          status: 'running' as ActivityStatus,
          timestamp: now,
        };

        return {
          ...prev,
          currentPhase: 'fixing',
          verificationAttempts: fixingData.attempt,
          activities: [...prev.activities, activityEvent],
        };
      }

      // Handle phase_change events (from unified agent)
      if ((event as any).phase_change) {
        const phaseData = (event as any).phase_change;
        return {
          ...prev,
          currentPhase: phaseData.phase as NaviActivityState['currentPhase'],
        };
      }

      // Handle content events (streamed text from unified agent)
      if (event.content) {
        const narrativeEntry: NarrativeEntry = {
          id: generateId(),
          content: event.content,
          phase: 'response',
          timestamp: now,
        };
        return {
          ...prev,
          narratives: [...prev.narratives, narrativeEntry],
        };
      }

      // Handle error events
      if ((event as any).error) {
        return {
          ...prev,
          lastError: (event as any).error,
          activities: [
            ...prev.activities,
            {
              id: generateId(),
              kind: 'error' as ActivityKind,
              label: 'Error',
              detail: (event as any).error,
              status: 'error' as ActivityStatus,
              timestamp: now,
            },
          ],
        };
      }

      return prev;
    });
  }, []);

  /**
   * Process an incoming stream event
   * Events are buffered and processed in sequence order
   */
  const processEvent = useCallback(
    (event: StreamEvent) => {
      const seq = event.sequence ?? event.activity?.sequence ?? 0;

      // If event has a sequence and it's the next expected one, process immediately
      if (seq > 0 && seq === lastSequenceRef.current + 1) {
        lastSequenceRef.current = seq;
        processEventInternal(event);
        flushEventBuffer();
      } else if (seq > lastSequenceRef.current + 1) {
        // Out of order - buffer it
        eventBufferRef.current.push(event);
      } else {
        // No sequence or in order - process immediately
        processEventInternal(event);
      }
    },
    [processEventInternal, flushEventBuffer]
  );

  /**
   * Mark a specific activity as complete
   */
  const completeActivity = useCallback((id: string) => {
    setState((prev) => ({
      ...prev,
      activities: prev.activities.map((a) =>
        a.id === id ? { ...a, status: 'done' as ActivityStatus } : a
      ),
    }));
  }, []);

  /**
   * Mark all running activities as complete
   */
  const completeAllActivities = useCallback(() => {
    setState((prev) => ({
      ...prev,
      activities: prev.activities.map((a) =>
        a.status === 'running' ? { ...a, status: 'done' as ActivityStatus } : a
      ),
      isThinking: false,
      currentPhase: 'complete',
    }));
  }, []);

  /**
   * Reset state for a new request
   */
  const reset = useCallback(() => {
    setState(initialState);
    eventBufferRef.current = [];
    lastSequenceRef.current = 0;
  }, []);

  /**
   * Clear just the activities (keep narratives for context)
   */
  const clearActivities = useCallback(() => {
    setState((prev) => ({
      ...prev,
      activities: [],
      filesRead: [],
      filesModified: [],
      filesCreated: [],
      commandsRun: [],
      toolOutputs: [],
      doneSummary: null,
      verificationResults: [],
      verificationPassed: null,
      verificationAttempts: 0,
      isThinking: false,
      currentPhase: 'idle',
    }));
  }, []);

  return {
    // State
    ...state,
    // Derived state
    isProcessing: state.currentPhase !== 'idle' && state.currentPhase !== 'complete',
    hasActivities: state.activities.length > 0,
    runningCount: state.activities.filter((a) => a.status === 'running').length,
    isVerifying: state.currentPhase === 'verifying',
    isFixing: state.currentPhase === 'fixing',
    hasVerificationErrors: state.verificationResults.some((r) => !r.success),
    // Actions
    processEvent,
    completeActivity,
    completeAllActivities,
    reset,
    clearActivities,
  };
}

export default useNaviActivityStream;
