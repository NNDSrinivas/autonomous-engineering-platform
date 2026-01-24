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
