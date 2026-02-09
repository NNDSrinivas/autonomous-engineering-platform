import { buildHeaders } from '../api/navi/client';

export type ChatSessionTag = {
  label: string;
  color?: string; // CSS color or preset name like 'blue', 'green', 'purple', 'orange', 'red'
};

export type ChatSessionSummary = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
  lastMessagePreview?: string;
  repoName?: string;
  workspaceRoot?: string;
  backendConversationId?: string;
  isStarred?: boolean;
  isArchived?: boolean;
  isPinned?: boolean;
  tags?: ChatSessionTag[];
};

const SESSIONS_KEY = "aep.navi.chatSessions.v1";
const ACTIVE_SESSION_KEY = "aep.navi.activeSessionId";
const HISTORY_PREFIX = "aep.navi.chatHistory.v1.";
const DRAFT_PREFIX = "aep.navi.chatDraft.v1.";
const LEGACY_HISTORY_KEY = "aep.navi.chatHistory";
const LEGACY_DRAFT_KEY = "aep.navi.chatDraft";
const DEFAULT_TITLE = "New chat";
const MAX_SESSIONS = 50;

const isBrowser = typeof window !== "undefined";

const nowIso = () => new Date().toISOString();

const readStorage = (key: string): string | null => {
  if (!isBrowser) return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
};

const writeStorage = (key: string, value: string) => {
  if (!isBrowser) return;
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // ignore storage errors
  }
};

const removeStorage = (key: string) => {
  if (!isBrowser) return;
  try {
    window.localStorage.removeItem(key);
  } catch {
    // ignore storage errors
  }
};

const safeJsonParse = <T>(raw: string | null, fallback: T): T => {
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
};

const normalizeSession = (entry: any): ChatSessionSummary | null => {
  if (!entry || typeof entry.id !== "string") return null;
  return {
    id: entry.id,
    title: typeof entry.title === "string" && entry.title.trim() ? entry.title : DEFAULT_TITLE,
    createdAt: typeof entry.createdAt === "string" ? entry.createdAt : nowIso(),
    updatedAt: typeof entry.updatedAt === "string" ? entry.updatedAt : nowIso(),
    messageCount: typeof entry.messageCount === "number" ? entry.messageCount : 0,
    lastMessagePreview:
      typeof entry.lastMessagePreview === "string" ? entry.lastMessagePreview : undefined,
    repoName: typeof entry.repoName === "string" ? entry.repoName : undefined,
    workspaceRoot: typeof entry.workspaceRoot === "string" ? entry.workspaceRoot : undefined,
    backendConversationId:
      typeof entry.backendConversationId === "string" ? entry.backendConversationId : undefined,
    isStarred: typeof entry.isStarred === "boolean" ? entry.isStarred : false,
    isArchived: typeof entry.isArchived === "boolean" ? entry.isArchived : false,
    isPinned: typeof entry.isPinned === "boolean" ? entry.isPinned : false,
    tags: Array.isArray(entry.tags) ? entry.tags : undefined,
  };
};

const readSessionsRaw = (): ChatSessionSummary[] => {
  const parsed = safeJsonParse<any[]>(readStorage(SESSIONS_KEY), []);
  return parsed
    .map(normalizeSession)
    .filter((entry): entry is ChatSessionSummary => Boolean(entry));
};

const writeSessions = (sessions: ChatSessionSummary[]) => {
  const deduped: ChatSessionSummary[] = [];
  const seen = new Set<string>();
  for (const session of sessions) {
    if (seen.has(session.id)) continue;
    seen.add(session.id);
    deduped.push(session);
  }
  deduped.sort(
    (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
  );
  const trimmed = deduped.slice(0, MAX_SESSIONS);
  writeStorage(SESSIONS_KEY, JSON.stringify(trimmed));
};

export const listSessions = (): ChatSessionSummary[] => {
  return readSessionsRaw().sort(
    (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
  );
};

export const getSession = (id: string): ChatSessionSummary | null => {
  return readSessionsRaw().find((session) => session.id === id) || null;
};

export const getActiveSessionId = (): string | null => {
  return readStorage(ACTIVE_SESSION_KEY);
};

export const setActiveSessionId = (id: string) => {
  writeStorage(ACTIVE_SESSION_KEY, id);
};

const makeSessionId = (): string => {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return (crypto as any).randomUUID() as string;
  }
  return `session-${Date.now()}-${Math.random().toString(36).slice(2)}`;
};

export const createSession = (
  seed: Partial<ChatSessionSummary> = {}
): ChatSessionSummary => {
  const now = nowIso();
  const session: ChatSessionSummary = {
    id: seed.id || makeSessionId(),
    title: seed.title && seed.title.trim() ? seed.title : DEFAULT_TITLE,
    createdAt: seed.createdAt || now,
    updatedAt: seed.updatedAt || now,
    messageCount: seed.messageCount ?? 0,
    lastMessagePreview: seed.lastMessagePreview,
    repoName: seed.repoName,
    workspaceRoot: seed.workspaceRoot,
    backendConversationId: seed.backendConversationId,
  };
  const sessions = readSessionsRaw();
  sessions.unshift(session);
  writeSessions(sessions);
  setActiveSessionId(session.id);
  return session;
};

export const updateSession = (
  id: string,
  updates: Partial<ChatSessionSummary>
): ChatSessionSummary | null => {
  const sessions = readSessionsRaw();
  const index = sessions.findIndex((session) => session.id === id);
  if (index === -1) return null;
  const next: ChatSessionSummary = {
    ...sessions[index],
    ...updates,
    updatedAt: updates.updatedAt || nowIso(),
  };
  sessions[index] = next;
  writeSessions(sessions);
  return next;
};

export const deleteSession = (id: string) => {
  const sessions = readSessionsRaw().filter((session) => session.id !== id);
  writeSessions(sessions);
  removeStorage(`${HISTORY_PREFIX}${id}`);
  removeStorage(`${DRAFT_PREFIX}${id}`);
  if (getActiveSessionId() === id) {
    const next = sessions[0];
    if (next) {
      setActiveSessionId(next.id);
    } else {
      removeStorage(ACTIVE_SESSION_KEY);
    }
  }
};

export const toggleSessionStar = (id: string): boolean => {
  const session = getSession(id);
  if (!session) return false;
  const newValue = !session.isStarred;
  updateSession(id, { isStarred: newValue });
  return newValue;
};

export const toggleSessionArchive = (id: string): boolean => {
  const session = getSession(id);
  if (!session) return false;
  const newValue = !session.isArchived;
  updateSession(id, { isArchived: newValue });
  return newValue;
};

export const listActiveSessions = (): ChatSessionSummary[] => {
  return listSessions().filter((session) => !session.isArchived);
};

export const listArchivedSessions = (): ChatSessionSummary[] => {
  return listSessions().filter((session) => session.isArchived);
};

export const listStarredSessions = (): ChatSessionSummary[] => {
  return listSessions().filter((session) => session.isStarred && !session.isArchived);
};

export const listPinnedSessions = (): ChatSessionSummary[] => {
  return listSessions().filter((session) => session.isPinned && !session.isArchived);
};

export const toggleSessionPin = (id: string): boolean => {
  const session = getSession(id);
  if (!session) return false;
  const newValue = !session.isPinned;
  updateSession(id, { isPinned: newValue });
  return newValue;
};

export const addSessionTag = (id: string, tag: ChatSessionTag): boolean => {
  const session = getSession(id);
  if (!session) return false;
  const currentTags = session.tags || [];
  // Don't add duplicate tags
  if (currentTags.some(t => t.label.toLowerCase() === tag.label.toLowerCase())) return false;
  updateSession(id, { tags: [...currentTags, tag] });
  return true;
};

export const removeSessionTag = (id: string, tagLabel: string): boolean => {
  const session = getSession(id);
  if (!session || !session.tags) return false;
  const newTags = session.tags.filter(t => t.label.toLowerCase() !== tagLabel.toLowerCase());
  updateSession(id, { tags: newTags.length > 0 ? newTags : undefined });
  return true;
};

// Helper to format relative time
export const formatRelativeTime = (dateString: string): string => {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
  return date.toLocaleDateString();
};

export const loadSessionMessages = <T = unknown>(id: string): T[] => {
  return safeJsonParse<T[]>(readStorage(`${HISTORY_PREFIX}${id}`), []);
};

export const saveSessionMessages = <T = unknown>(id: string, messages: T[]) => {
  writeStorage(`${HISTORY_PREFIX}${id}`, JSON.stringify(messages));
};

export const clearSessionMessages = (id: string) => {
  removeStorage(`${HISTORY_PREFIX}${id}`);
};

export const loadSessionDraft = (id: string): string => {
  return readStorage(`${DRAFT_PREFIX}${id}`) || "";
};

export const saveSessionDraft = (id: string, draft: string) => {
  writeStorage(`${DRAFT_PREFIX}${id}`, draft);
};

export const clearSessionDraft = (id: string) => {
  removeStorage(`${DRAFT_PREFIX}${id}`);
};

const migrateLegacySessionIfNeeded = (
  seed: Partial<ChatSessionSummary>
): ChatSessionSummary | null => {
  const existingSessions = readSessionsRaw();
  if (existingSessions.length > 0) return null;
  const legacyRaw = readStorage(LEGACY_HISTORY_KEY);
  if (!legacyRaw) return null;
  const messages = safeJsonParse<unknown[]>(legacyRaw, []);
  const session = createSession({
    title: seed.title || "Previous chat",
    repoName: seed.repoName,
    workspaceRoot: seed.workspaceRoot,
  });
  if (messages.length > 0) {
    saveSessionMessages(session.id, messages);
    updateSession(session.id, { messageCount: messages.length });
  }
  const legacyDraft = readStorage(LEGACY_DRAFT_KEY);
  if (legacyDraft) {
    saveSessionDraft(session.id, legacyDraft);
  }
  removeStorage(LEGACY_HISTORY_KEY);
  removeStorage(LEGACY_DRAFT_KEY);
  return session;
};

export const ensureActiveSession = (
  seed: Partial<ChatSessionSummary> = {}
): ChatSessionSummary => {
  const migrated = migrateLegacySessionIfNeeded(seed);
  if (migrated) return migrated;

  const sessions = readSessionsRaw();
  const activeId = getActiveSessionId();
  const active = activeId
    ? sessions.find((session) => session.id === activeId) || null
    : null;
  if (active) {
    return active;
  }
  if (sessions.length > 0) {
    setActiveSessionId(sessions[0].id);
    return sessions[0];
  }
  return createSession(seed);
};

// ============================================================================
// TASK CHECKPOINT & RECOVERY SYSTEM
// ============================================================================

const CHECKPOINT_PREFIX = "aep.navi.checkpoint.v1.";
const STREAMING_STATE_PREFIX = "aep.navi.streaming.v1.";

/**
 * Represents a file that was modified during a task
 */
export type ModifiedFile = {
  path: string;
  operation: 'create' | 'edit' | 'delete';
  timestamp: string;
  success: boolean;
};

/**
 * Represents an executed command during a task
 */
export type ExecutedCommand = {
  command: string;
  exitCode?: number;
  timestamp: string;
  success: boolean;
};

/**
 * Plan step status for checkpoint
 */
export type CheckpointStepStatus = 'pending' | 'running' | 'completed' | 'failed';

/**
 * A plan step in the checkpoint
 */
export type CheckpointStep = {
  id: number;
  title: string;
  status: CheckpointStepStatus;
  completedAt?: string;
};

/**
 * Task checkpoint - stores state for resuming interrupted tasks
 */
export type TaskCheckpoint = {
  id: string;
  sessionId: string;
  messageId: string;
  createdAt: string;
  updatedAt: string;

  // Original request
  userMessage: string;

  // Task progress
  status: 'running' | 'interrupted' | 'completed' | 'failed';
  currentStepIndex: number;
  totalSteps: number;
  steps: CheckpointStep[];

  // What was done
  modifiedFiles: ModifiedFile[];
  executedCommands: ExecutedCommand[];

  // Partial response content
  partialContent: string;

  // Error info if interrupted
  interruptedAt?: string;
  interruptReason?: string;

  // For retry logic
  retryCount: number;
  lastRetryAt?: string;
};

/**
 * Streaming state - for incremental message saving
 */
export type StreamingState = {
  sessionId: string;
  messageId: string;
  content: string;
  activities: any[];
  narratives: string[];
  thinking: string;
  startedAt: string;
  lastUpdatedAt: string;
  isComplete: boolean;
};

// --- Checkpoint Functions ---

export const saveCheckpoint = (checkpoint: TaskCheckpoint): void => {
  checkpoint.updatedAt = nowIso();
  writeStorage(`${CHECKPOINT_PREFIX}${checkpoint.sessionId}`, JSON.stringify(checkpoint));
};

export const loadCheckpoint = (sessionId: string): TaskCheckpoint | null => {
  const raw = readStorage(`${CHECKPOINT_PREFIX}${sessionId}`);
  if (!raw) return null;
  return safeJsonParse<TaskCheckpoint | null>(raw, null);
};

export const clearCheckpoint = (sessionId: string): void => {
  removeStorage(`${CHECKPOINT_PREFIX}${sessionId}`);
};

export const hasActiveCheckpoint = (sessionId: string): boolean => {
  const checkpoint = loadCheckpoint(sessionId);
  return checkpoint !== null && checkpoint.status === 'interrupted';
};

export const createCheckpoint = (
  sessionId: string,
  messageId: string,
  userMessage: string,
  steps: CheckpointStep[] = []
): TaskCheckpoint => {
  const now = nowIso();
  const checkpoint: TaskCheckpoint = {
    id: `checkpoint-${Date.now()}`,
    sessionId,
    messageId,
    createdAt: now,
    updatedAt: now,
    userMessage,
    status: 'running',
    currentStepIndex: 0,
    totalSteps: steps.length,
    steps,
    modifiedFiles: [],
    executedCommands: [],
    partialContent: '',
    retryCount: 0,
  };
  saveCheckpoint(checkpoint);
  return checkpoint;
};

export const updateCheckpointProgress = (
  sessionId: string,
  updates: Partial<Pick<TaskCheckpoint,
    'currentStepIndex' | 'partialContent' | 'status' | 'modifiedFiles' | 'executedCommands' | 'steps'
  >>
): TaskCheckpoint | null => {
  const checkpoint = loadCheckpoint(sessionId);
  if (!checkpoint) return null;

  const updated = { ...checkpoint, ...updates, updatedAt: nowIso() };
  saveCheckpoint(updated);
  return updated;
};

export const markCheckpointInterrupted = (
  sessionId: string,
  reason: string
): TaskCheckpoint | null => {
  const checkpoint = loadCheckpoint(sessionId);
  if (!checkpoint) return null;

  checkpoint.status = 'interrupted';
  checkpoint.interruptedAt = nowIso();
  checkpoint.interruptReason = reason;
  saveCheckpoint(checkpoint);
  return checkpoint;
};

export const markCheckpointCompleted = (sessionId: string): void => {
  const checkpoint = loadCheckpoint(sessionId);
  if (checkpoint) {
    checkpoint.status = 'completed';
    saveCheckpoint(checkpoint);
  }
  // Don't clear immediately - keep for a short time for debugging
  setTimeout(() => clearCheckpoint(sessionId), 60000);
};

export const incrementCheckpointRetry = (sessionId: string): number => {
  const checkpoint = loadCheckpoint(sessionId);
  if (!checkpoint) return 0;

  checkpoint.retryCount += 1;
  checkpoint.lastRetryAt = nowIso();
  checkpoint.status = 'running';
  saveCheckpoint(checkpoint);
  return checkpoint.retryCount;
};

// --- Streaming State Functions (for incremental saving) ---

export const saveStreamingState = (state: StreamingState): void => {
  state.lastUpdatedAt = nowIso();
  writeStorage(`${STREAMING_STATE_PREFIX}${state.sessionId}`, JSON.stringify(state));
};

export const loadStreamingState = (sessionId: string): StreamingState | null => {
  const raw = readStorage(`${STREAMING_STATE_PREFIX}${sessionId}`);
  if (!raw) return null;
  return safeJsonParse<StreamingState | null>(raw, null);
};

export const clearStreamingState = (sessionId: string): void => {
  removeStorage(`${STREAMING_STATE_PREFIX}${sessionId}`);
};

export const createStreamingState = (
  sessionId: string,
  messageId: string
): StreamingState => {
  const state: StreamingState = {
    sessionId,
    messageId,
    content: '',
    activities: [],
    narratives: [],
    thinking: '',
    startedAt: nowIso(),
    lastUpdatedAt: nowIso(),
    isComplete: false,
  };
  saveStreamingState(state);
  return state;
};

export const updateStreamingContent = (
  sessionId: string,
  content: string
): void => {
  const state = loadStreamingState(sessionId);
  if (state) {
    state.content = content;
    saveStreamingState(state);
  }
};

export const appendStreamingActivity = (
  sessionId: string,
  activity: any
): void => {
  const state = loadStreamingState(sessionId);
  if (state) {
    state.activities.push(activity);
    saveStreamingState(state);
  }
};

export const markStreamingComplete = (sessionId: string): void => {
  const state = loadStreamingState(sessionId);
  if (state) {
    state.isComplete = true;
    saveStreamingState(state);
  }
  // Clear after a delay
  setTimeout(() => clearStreamingState(sessionId), 5000);
};

/**
 * Debounced save function factory for streaming content
 * Saves at most once per interval to avoid excessive writes
 */
export const createDebouncedSave = (
  sessionId: string,
  intervalMs: number = 500
): ((content: string) => void) => {
  let lastSaveTime = 0;
  let pendingContent: string | null = null;
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  return (content: string) => {
    const now = Date.now();
    pendingContent = content;

    if (now - lastSaveTime >= intervalMs) {
      // Enough time has passed, save immediately
      updateStreamingContent(sessionId, content);
      lastSaveTime = now;
      pendingContent = null;
      if (timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = null;
      }
    } else if (!timeoutId) {
      // Schedule a save for later
      timeoutId = setTimeout(() => {
        if (pendingContent !== null) {
          updateStreamingContent(sessionId, pendingContent);
          lastSaveTime = Date.now();
          pendingContent = null;
        }
        timeoutId = null;
      }, intervalMs - (now - lastSaveTime));
    }
  };
};

// ============================================================================
// BACKEND CHECKPOINT SYNC
// ============================================================================

/**
 * Configuration for backend checkpoint sync
 */
export type CheckpointSyncConfig = {
  apiBaseUrl: string;
  userId: number;
  onError?: (error: Error) => void;
};

let syncConfig: CheckpointSyncConfig | null = null;

/**
 * Initialize checkpoint sync with backend
 */
export const initCheckpointSync = (config: CheckpointSyncConfig): void => {
  syncConfig = config;
};

/**
 * Sync a checkpoint to the backend
 */
export const syncCheckpointToBackend = async (
  checkpoint: TaskCheckpoint
): Promise<boolean> => {
  if (!syncConfig) return false;

  try {
    const response = await fetch(
      `${syncConfig.apiBaseUrl}/api/navi/checkpoint/sync?user_id=${syncConfig.userId}&session_id=${checkpoint.sessionId}`,
      {
        method: 'POST',
        headers: buildHeaders(),
        body: JSON.stringify({
          messageId: checkpoint.messageId,
          userMessage: checkpoint.userMessage,
          status: checkpoint.status,
          currentStepIndex: checkpoint.currentStepIndex,
          totalSteps: checkpoint.totalSteps,
          steps: checkpoint.steps,
          modifiedFiles: checkpoint.modifiedFiles,
          executedCommands: checkpoint.executedCommands,
          partialContent: checkpoint.partialContent,
          streamingState: {},
          retryCount: checkpoint.retryCount,
          interruptedAt: checkpoint.interruptedAt,
        }),
      }
    );

    return response.ok;
  } catch (error) {
    if (syncConfig.onError) {
      syncConfig.onError(error instanceof Error ? error : new Error(String(error)));
    }
    return false;
  }
};

/**
 * Load checkpoint from backend
 */
export const loadCheckpointFromBackend = async (
  sessionId: string
): Promise<TaskCheckpoint | null> => {
  if (!syncConfig) return null;

  try {
    const response = await fetch(
      `${syncConfig.apiBaseUrl}/api/navi/checkpoint?user_id=${syncConfig.userId}&session_id=${sessionId}`,
      { headers: buildHeaders() }
    );

    if (!response.ok) return null;

    const data = await response.json();
    if (!data) return null;

    // Convert backend format to frontend format
    return {
      id: data.id,
      sessionId: data.session_id,
      messageId: data.message_id,
      createdAt: data.created_at,
      updatedAt: data.updated_at,
      userMessage: data.user_message,
      status: data.status,
      currentStepIndex: data.current_step_index,
      totalSteps: data.total_steps,
      steps: data.steps || [],
      modifiedFiles: data.modified_files || [],
      executedCommands: data.executed_commands || [],
      partialContent: data.partial_content || '',
      interruptedAt: data.interrupted_at,
      interruptReason: data.interrupt_reason,
      retryCount: data.retry_count || 0,
      lastRetryAt: data.last_retry_at,
    };
  } catch (error) {
    if (syncConfig.onError) {
      syncConfig.onError(error instanceof Error ? error : new Error(String(error)));
    }
    return null;
  }
};

/**
 * Mark checkpoint as interrupted on backend
 */
export const markInterruptedOnBackend = async (
  sessionId: string,
  reason: string
): Promise<boolean> => {
  if (!syncConfig) return false;

  try {
    const response = await fetch(
      `${syncConfig.apiBaseUrl}/api/navi/checkpoint/interrupt?user_id=${syncConfig.userId}&session_id=${sessionId}`,
      {
        method: 'POST',
        headers: buildHeaders(),
        body: JSON.stringify({ reason }),
      }
    );

    return response.ok;
  } catch (error) {
    if (syncConfig.onError) {
      syncConfig.onError(error instanceof Error ? error : new Error(String(error)));
    }
    return false;
  }
};

/**
 * Mark checkpoint as completed on backend
 */
export const markCompletedOnBackend = async (
  sessionId: string
): Promise<boolean> => {
  if (!syncConfig) return false;

  try {
    const response = await fetch(
      `${syncConfig.apiBaseUrl}/api/navi/checkpoint/complete?user_id=${syncConfig.userId}&session_id=${sessionId}`,
      { method: 'POST', headers: buildHeaders() }
    );

    return response.ok;
  } catch (error) {
    if (syncConfig.onError) {
      syncConfig.onError(error instanceof Error ? error : new Error(String(error)));
    }
    return false;
  }
};

/**
 * Get interrupted checkpoints from backend
 */
export const getInterruptedCheckpointsFromBackend = async (): Promise<TaskCheckpoint[]> => {
  if (!syncConfig) return [];

  try {
    const response = await fetch(
      `${syncConfig.apiBaseUrl}/api/navi/checkpoint/interrupted/list?user_id=${syncConfig.userId}`,
      { headers: buildHeaders() }
    );

    if (!response.ok) return [];

    const data = await response.json();
    if (!Array.isArray(data)) return [];

    return data.map((item: any) => ({
      id: item.id,
      sessionId: item.session_id,
      messageId: item.message_id,
      createdAt: item.created_at,
      updatedAt: item.updated_at,
      userMessage: item.user_message,
      status: item.status,
      currentStepIndex: item.current_step_index,
      totalSteps: item.total_steps,
      steps: item.steps || [],
      modifiedFiles: item.modified_files || [],
      executedCommands: item.executed_commands || [],
      partialContent: item.partial_content || '',
      interruptedAt: item.interrupted_at,
      interruptReason: item.interrupt_reason,
      retryCount: item.retry_count || 0,
      lastRetryAt: item.last_retry_at,
    }));
  } catch (error) {
    if (syncConfig.onError) {
      syncConfig.onError(error instanceof Error ? error : new Error(String(error)));
    }
    return [];
  }
};

/**
 * Delete checkpoint from backend
 */
export const deleteCheckpointFromBackend = async (
  sessionId: string
): Promise<boolean> => {
  if (!syncConfig) return false;

  try {
    const response = await fetch(
      `${syncConfig.apiBaseUrl}/api/navi/checkpoint?user_id=${syncConfig.userId}&session_id=${sessionId}`,
      { method: 'DELETE', headers: buildHeaders() }
    );

    return response.ok;
  } catch (error) {
    if (syncConfig.onError) {
      syncConfig.onError(error instanceof Error ? error : new Error(String(error)));
    }
    return false;
  }
};

/**
 * Enhanced checkpoint creation that syncs to backend
 */
export const createCheckpointWithSync = async (
  sessionId: string,
  messageId: string,
  userMessage: string,
  steps: CheckpointStep[] = []
): Promise<TaskCheckpoint> => {
  // Create locally first
  const checkpoint = createCheckpoint(sessionId, messageId, userMessage, steps);

  // Sync to backend in background (don't await to avoid blocking)
  syncCheckpointToBackend(checkpoint).catch(() => {
    // Silently ignore sync errors - local storage is the primary
  });

  return checkpoint;
};

/**
 * Enhanced checkpoint update that syncs to backend
 */
export const updateCheckpointProgressWithSync = async (
  sessionId: string,
  updates: Partial<Pick<TaskCheckpoint,
    'currentStepIndex' | 'partialContent' | 'status' | 'modifiedFiles' | 'executedCommands' | 'steps'
  >>
): Promise<TaskCheckpoint | null> => {
  // Update locally first
  const checkpoint = updateCheckpointProgress(sessionId, updates);

  // Sync to backend in background if checkpoint exists
  if (checkpoint) {
    syncCheckpointToBackend(checkpoint).catch(() => {
      // Silently ignore sync errors
    });
  }

  return checkpoint;
};

/**
 * Enhanced mark interrupted that syncs to backend
 */
export const markCheckpointInterruptedWithSync = async (
  sessionId: string,
  reason: string
): Promise<TaskCheckpoint | null> => {
  // Update locally first
  const checkpoint = markCheckpointInterrupted(sessionId, reason);

  // Sync to backend
  if (checkpoint) {
    markInterruptedOnBackend(sessionId, reason).catch(() => {
      // Silently ignore sync errors
    });
  }

  return checkpoint;
};

/**
 * Enhanced mark completed that syncs to backend
 */
export const markCheckpointCompletedWithSync = async (
  sessionId: string
): Promise<void> => {
  // Update locally first
  markCheckpointCompleted(sessionId);

  // Sync to backend
  markCompletedOnBackend(sessionId).catch(() => {
    // Silently ignore sync errors
  });
};

/**
 * Try to load checkpoint from backend first, fall back to local
 */
export const loadCheckpointWithFallback = async (
  sessionId: string
): Promise<TaskCheckpoint | null> => {
  // Try backend first if sync is configured
  if (syncConfig) {
    const backendCheckpoint = await loadCheckpointFromBackend(sessionId);
    if (backendCheckpoint) {
      // Also save to local storage for offline access
      saveCheckpoint(backendCheckpoint);
      return backendCheckpoint;
    }
  }

  // Fall back to local storage
  return loadCheckpoint(sessionId);
};
