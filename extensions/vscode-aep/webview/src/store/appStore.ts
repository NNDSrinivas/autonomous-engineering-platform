import { create } from 'zustand';
import { devtools, persist, subscribeWithSelector, combine } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';
import { useRef } from 'react';

// Types for the application state
interface User {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  preferences: {
    theme: 'light' | 'dark' | 'auto';
    language: string;
    notifications: boolean;
    autoSave: boolean;
    keyboardShortcuts: Record<string, string>;
  };
}

interface Project {
  id: string;
  name: string;
  path: string;
  language: string;
  framework: string;
  lastOpened: Date;
  settings: {
    autoFix: boolean;
    enablePreview: boolean;
    maxFileSize: number;
    excludePatterns: string[];
  };
}

interface ChatMessage {
  id: string;
  type: 'user' | 'assistant' | 'system' | 'error';
  content: string;
  timestamp: Date;
  metadata?: {
    tokens?: number;
    model?: string;
    cost?: number;
    files?: string[];
    suggestions?: string[];
  };
}

interface ReviewSession {
  id: string;
  projectId: string;
  status: 'active' | 'completed' | 'cancelled';
  startTime: Date;
  endTime?: Date;
  messages: ChatMessage[];
  files: string[];
  changes: Array<{
    filePath: string;
    type: 'added' | 'modified' | 'deleted';
    hunks: number;
  }>;
  metrics: {
    filesReviewed: number;
    issuesFound: number;
    fixesApplied: number;
    timeSaved: number; // in minutes
  };
}

interface FixOperation {
  id: string;
  type: 'remove-console-logs' | 'fix-linting' | 'format-code' | 'optimize-imports' | 'fix-security';
  status: 'pending' | 'in-progress' | 'completed' | 'failed' | 'cancelled';
  filePaths: string[];
  progress: number;
  startTime: Date;
  endTime?: Date;
  results?: Array<{
    filePath: string;
    linesChanged: number;
    success: boolean;
    error?: string;
  }>;
}

interface UIState {
  sidebarOpen: boolean;
  activePanel: 'chat' | 'diff' | 'files' | 'settings';
  modalStack: Array<{
    id: string;
    type: string;
    props: any;
  }>;
  notifications: Array<{
    id: string;
    type: 'info' | 'success' | 'warning' | 'error';
    title: string;
    message: string;
    timestamp: Date;
    read: boolean;
    actions?: Array<{
      label: string;
      action: string;
    }>;
  }>;
  loading: Set<string>; // Track loading states by key
  connectionStatus: 'connected' | 'connecting' | 'disconnected' | 'error';
}

interface AppState {
  // Core application state
  user: User | null;
  currentProject: Project | null;
  projects: Project[];
  
  // Review and chat state
  currentReviewSession: ReviewSession | null;
  reviewHistory: ReviewSession[];
  chatMessages: ChatMessage[];
  
  // Fix operations
  activeFixOperations: FixOperation[];
  fixHistory: FixOperation[];
  
  // UI state
  ui: UIState;
  
  // Cache
  cache: Map<string, { data: any; timestamp: Date; ttl: number }>;
  
  // Metrics and analytics
  metrics: {
    sessionsStarted: number;
    fixesApplied: number;
    timeSaved: number;
    errorsEncountered: number;
    lastActive: Date;
  };
}

// Actions interface
interface AppActions {
  // User actions
  setUser: (user: User | null) => void;
  updateUserPreferences: (preferences: Partial<User['preferences']>) => void;
  
  // Project actions
  setCurrentProject: (project: Project | null) => void;
  addProject: (project: Project) => void;
  updateProject: (projectId: string, updates: Partial<Project>) => void;
  removeProject: (projectId: string) => void;
  
  // Review session actions
  startReviewSession: (projectId: string) => string;
  endReviewSession: (sessionId: string) => void;
  addMessageToSession: (message: Omit<ChatMessage, 'id' | 'timestamp'>) => void;
  
  // Fix operation actions
  startFixOperation: (operation: Omit<FixOperation, 'id' | 'status' | 'progress' | 'startTime'>) => string;
  updateFixOperation: (operationId: string, updates: Partial<FixOperation>) => void;
  cancelFixOperation: (operationId: string) => void;
  
  // UI actions
  setSidebarOpen: (open: boolean) => void;
  setActivePanel: (panel: UIState['activePanel']) => void;
  showModal: (type: string, props: any) => string;
  hideModal: (modalId: string) => void;
  addNotification: (notification: Omit<UIState['notifications'][0], 'id' | 'timestamp' | 'read'>) => string;
  markNotificationRead: (notificationId: string) => void;
  removeNotification: (notificationId: string) => void;
  setLoading: (key: string, loading: boolean) => void;
  setConnectionStatus: (status: UIState['connectionStatus']) => void;
  
  // Cache actions
  setCache: (key: string, data: any, ttl?: number) => void;
  getCache: (key: string) => any | null;
  clearCache: (pattern?: string) => void;
  
  // Utility actions
  resetState: () => void;
  exportState: () => string;
  importState: (state: string) => boolean;
  
  // Optimistic update actions
  optimisticUpdate: <T>(key: keyof AppState, updater: (current: T) => T, rollback?: () => void) => void;
}

// Initial state
const initialState: AppState = {
  user: null,
  currentProject: null,
  projects: [],
  currentReviewSession: null,
  reviewHistory: [],
  chatMessages: [],
  activeFixOperations: [],
  fixHistory: [],
  ui: {
    sidebarOpen: true,
    activePanel: 'chat',
    modalStack: [],
    notifications: [],
    loading: new Set(),
    connectionStatus: 'disconnected'
  },
  cache: new Map(),
  metrics: {
    sessionsStarted: 0,
    fixesApplied: 0,
    timeSaved: 0,
    errorsEncountered: 0,
    lastActive: new Date()
  }
};

// Utility functions
const generateId = () => `id-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

const isValidCacheEntry = (entry: { timestamp: Date; ttl: number }) => {
  return Date.now() - entry.timestamp.getTime() < entry.ttl;
};

// Middleware configuration
const persistConfig = {
  name: 'aep-app-state',
  version: 1,
  partialize: (state: AppState & AppActions) => ({
    user: state.user,
    projects: state.projects,
    reviewHistory: state.reviewHistory.slice(-50), // Keep last 50 sessions
    fixHistory: state.fixHistory.slice(-100), // Keep last 100 operations
    metrics: state.metrics,
    ui: {
      sidebarOpen: state.ui.sidebarOpen,
      activePanel: state.ui.activePanel,
      connectionStatus: 'disconnected' // Reset connection on reload
    }
  }),
  migrate: (persistedState: any, version: number) => {
    // Handle state migrations between versions
    if (version === 0) {
      // Migration from version 0 to 1
      return {
        ...persistedState,
        metrics: initialState.metrics,
        cache: new Map()
      };
    }
    return persistedState;
  }
};

// Create the store with all middleware
export const useAppStore = create<AppState & AppActions>()(
  devtools(
    persist(
      subscribeWithSelector(
        immer(
          combine(initialState, (set, get) => ({
            // User actions
            setUser: (user: User | null) => {
              set((state) => {
                state.user = user;
                state.metrics.lastActive = new Date();
              });
            },

            updateUserPreferences: (preferences: Partial<User['preferences']>) => {
              set((state) => {
                if (state.user) {
                  Object.assign(state.user.preferences, preferences);
                  state.metrics.lastActive = new Date();
                }
              });
            },

            // Project actions
            setCurrentProject: (project: Project | null) => {
              set((state) => {
                state.currentProject = project;
                if (project) {
                  // Update last opened time
                  const existingProject = state.projects.find(p => p.id === project.id);
                  if (existingProject) {
                    existingProject.lastOpened = new Date();
                  }
                }
                state.metrics.lastActive = new Date();
              });
            },

            addProject: (project: Project) => {
              set((state) => {
                const existingIndex = state.projects.findIndex(p => p.id === project.id);
                if (existingIndex >= 0) {
                  state.projects[existingIndex] = project;
                } else {
                  state.projects.push(project);
                }
                state.metrics.lastActive = new Date();
              });
            },

            updateProject: (projectId: string, updates: Partial<Project>) => {
              set((state) => {
                const project = state.projects.find(p => p.id === projectId);
                if (project) {
                  Object.assign(project, updates);
                  if (state.currentProject?.id === projectId) {
                    Object.assign(state.currentProject, updates);
                  }
                }
                state.metrics.lastActive = new Date();
              });
            },

            removeProject: (projectId: string) => {
              set((state) => {
                state.projects = state.projects.filter(p => p.id !== projectId);
                if (state.currentProject?.id === projectId) {
                  state.currentProject = null;
                }
                // Clean up related sessions
                state.reviewHistory = state.reviewHistory.filter(s => s.projectId !== projectId);
                state.metrics.lastActive = new Date();
              });
            },

            // Review session actions
            startReviewSession: (projectId: string): string => {
              const sessionId = generateId();
              set((state) => {
                // End current session if exists
                if (state.currentReviewSession) {
                  state.currentReviewSession.status = 'completed';
                  state.currentReviewSession.endTime = new Date();
                  state.reviewHistory.push(state.currentReviewSession);
                }
                
                // Start new session
                state.currentReviewSession = {
                  id: sessionId,
                  projectId,
                  status: 'active',
                  startTime: new Date(),
                  messages: [],
                  files: [],
                  changes: [],
                  metrics: {
                    filesReviewed: 0,
                    issuesFound: 0,
                    fixesApplied: 0,
                    timeSaved: 0
                  }
                };
                
                state.chatMessages = []; // Clear chat for new session
                state.metrics.sessionsStarted++;
                state.metrics.lastActive = new Date();
              });
              return sessionId;
            },

            endReviewSession: (sessionId: string) => {
              set((state) => {
                if (state.currentReviewSession?.id === sessionId) {
                  state.currentReviewSession.status = 'completed';
                  state.currentReviewSession.endTime = new Date();
                  state.reviewHistory.push(state.currentReviewSession);
                  state.currentReviewSession = null;
                }
                state.metrics.lastActive = new Date();
              });
            },

            addMessageToSession: (message: Omit<ChatMessage, 'id' | 'timestamp'>) => {
              set((state) => {
                const fullMessage: ChatMessage = {
                  ...message,
                  id: generateId(),
                  timestamp: new Date()
                };
                
                state.chatMessages.push(fullMessage);
                
                if (state.currentReviewSession) {
                  state.currentReviewSession.messages.push(fullMessage);
                }
                
                // Limit chat history
                if (state.chatMessages.length > 1000) {
                  state.chatMessages = state.chatMessages.slice(-800);
                }
                
                state.metrics.lastActive = new Date();
              });
            },

            // Fix operation actions
            startFixOperation: (operation: Omit<FixOperation, 'id' | 'status' | 'progress' | 'startTime'>): string => {
              const operationId = generateId();
              set((state) => {
                const fullOperation: FixOperation = {
                  ...operation,
                  id: operationId,
                  status: 'pending',
                  progress: 0,
                  startTime: new Date()
                };
                
                state.activeFixOperations.push(fullOperation);
                state.metrics.lastActive = new Date();
              });
              return operationId;
            },

            updateFixOperation: (operationId: string, updates: Partial<FixOperation>) => {
              set((state) => {
                const operation = state.activeFixOperations.find(op => op.id === operationId);
                if (operation) {
                  Object.assign(operation, updates);
                  
                  // Move to history if completed or failed
                  if (updates.status === 'completed' || updates.status === 'failed') {
                    operation.endTime = new Date();
                    state.fixHistory.push(operation);
                    state.activeFixOperations = state.activeFixOperations.filter(op => op.id !== operationId);
                    
                    if (updates.status === 'completed') {
                      state.metrics.fixesApplied++;
                      // Estimate time saved (rough calculation)
                      const timeSaved = Math.max(1, Math.floor(operation.filePaths.length * 0.5));
                      state.metrics.timeSaved += timeSaved;
                    }
                  }
                  
                  // Update current session metrics
                  if (state.currentReviewSession && updates.status === 'completed') {
                    state.currentReviewSession.metrics.fixesApplied++;
                  }
                }
                state.metrics.lastActive = new Date();
              });
            },

            cancelFixOperation: (operationId: string) => {
              set((state) => {
                const operation = state.activeFixOperations.find(op => op.id === operationId);
                if (operation) {
                  operation.status = 'cancelled';
                  operation.endTime = new Date();
                  state.fixHistory.push(operation);
                  state.activeFixOperations = state.activeFixOperations.filter(op => op.id !== operationId);
                }
                state.metrics.lastActive = new Date();
              });
            },

            // UI actions
            setSidebarOpen: (open: boolean) => {
              set((state) => {
                state.ui.sidebarOpen = open;
              });
            },

            setActivePanel: (panel: UIState['activePanel']) => {
              set((state) => {
                state.ui.activePanel = panel;
                state.metrics.lastActive = new Date();
              });
            },

            showModal: (type: string, props: any): string => {
              const modalId = generateId();
              set((state) => {
                state.ui.modalStack.push({
                  id: modalId,
                  type,
                  props
                });
              });
              return modalId;
            },

            hideModal: (modalId: string) => {
              set((state) => {
                state.ui.modalStack = state.ui.modalStack.filter(modal => modal.id !== modalId);
              });
            },

            addNotification: (notification: Omit<UIState['notifications'][0], 'id' | 'timestamp' | 'read'>): string => {
              const notificationId = generateId();
              set((state) => {
                state.ui.notifications.push({
                  ...notification,
                  id: notificationId,
                  timestamp: new Date(),
                  read: false
                });
                
                // Limit notifications
                if (state.ui.notifications.length > 100) {
                  state.ui.notifications = state.ui.notifications.slice(-50);
                }
              });
              return notificationId;
            },

            markNotificationRead: (notificationId: string) => {
              set((state) => {
                const notification = state.ui.notifications.find(n => n.id === notificationId);
                if (notification) {
                  notification.read = true;
                }
              });
            },

            removeNotification: (notificationId: string) => {
              set((state) => {
                state.ui.notifications = state.ui.notifications.filter(n => n.id !== notificationId);
              });
            },

            setLoading: (key: string, loading: boolean) => {
              set((state) => {
                if (loading) {
                  state.ui.loading.add(key);
                } else {
                  state.ui.loading.delete(key);
                }
              });
            },

            setConnectionStatus: (status: UIState['connectionStatus']) => {
              set((state) => {
                state.ui.connectionStatus = status;
                if (status === 'error') {
                  state.metrics.errorsEncountered++;
                }
              });
            },

            // Cache actions
            setCache: (key: string, data: any, ttl: number = 300000) => { // 5 minutes default TTL
              set((state) => {
                state.cache.set(key, {
                  data,
                  timestamp: new Date(),
                  ttl
                });
              });
            },

            getCache: (key: string) => {
              const entry = get().cache.get(key);
              if (!entry) return null;
              
              if (!isValidCacheEntry(entry)) {
                // Clean up expired entry
                set((state) => {
                  state.cache.delete(key);
                });
                return null;
              }
              
              return entry.data;
            },

            clearCache: (pattern?: string) => {
              set((state) => {
                if (pattern) {
                  const regex = new RegExp(pattern);
                  Array.from(state.cache.keys()).forEach(key => {
                    if (regex.test(key)) {
                      state.cache.delete(key);
                    }
                  });
                } else {
                  state.cache.clear();
                }
              });
            },

            // Utility actions
            resetState: () => {
              set(() => ({ ...initialState }));
            },

            exportState: (): string => {
              const state = get();
              const exportData = {
                user: state.user,
                projects: state.projects,
                reviewHistory: state.reviewHistory,
                fixHistory: state.fixHistory,
                metrics: state.metrics,
                exportedAt: new Date().toISOString(),
                version: 1
              };
              return JSON.stringify(exportData, null, 2);
            },

            importState: (stateString: string): boolean => {
              try {
                const importedData = JSON.parse(stateString);
                
                if (importedData.version !== 1) {
                  console.warn('State version mismatch, import may fail');
                }
                
                set((state) => {
                  if (importedData.user) state.user = importedData.user;
                  if (importedData.projects) state.projects = importedData.projects;
                  if (importedData.reviewHistory) state.reviewHistory = importedData.reviewHistory;
                  if (importedData.fixHistory) state.fixHistory = importedData.fixHistory;
                  if (importedData.metrics) state.metrics = importedData.metrics;
                  state.metrics.lastActive = new Date();
                });
                
                return true;
              } catch (error) {
                console.error('Failed to import state:', error);
                return false;
              }
            },

            // Optimistic update implementation
            optimisticUpdate: <T>(key: keyof AppState, updater: (current: T) => T, rollback?: () => void) => {
              const currentValue = get()[key] as T;
              const originalValue = structuredClone ? structuredClone(currentValue) : JSON.parse(JSON.stringify(currentValue));
              
              try {
                set((state) => {
                  (state as any)[key] = updater(currentValue);
                  state.metrics.lastActive = new Date();
                });
              } catch (error) {
                console.error('Optimistic update failed:', error);
                
                // Rollback on error
                set((state) => {
                  (state as any)[key] = originalValue;
                });
                
                rollback?.();
              }
            }
          }))
        )
      ),
      persistConfig
    ),
    {
      name: 'AEP App Store',
      serialize: (state: any) => JSON.stringify(state, (key: string, value: any) => {
        // Handle Map serialization
        if (value instanceof Map) {
          return Object.fromEntries(value);
        }
        // Handle Set serialization
        if (value instanceof Set) {
          return Array.from(value);
        }
        return value;
      }),
      deserialize: (str: string) => JSON.parse(str, (key: string, value: any) => {
        // Handle Map deserialization
        if (key === 'cache' && typeof value === 'object' && value !== null) {
          return new Map(Object.entries(value));
        }
        // Handle Set deserialization
        if (key === 'loading' && Array.isArray(value)) {
          return new Set(value);
        }
        return value;
      })
    }
  )
);

// Selectors for commonly used data
export const useUser = () => useAppStore((state) => state.user);
export const useCurrentProject = () => useAppStore((state) => state.currentProject);
export const useProjects = () => useAppStore((state) => state.projects);
export const useCurrentReviewSession = () => useAppStore((state) => state.currentReviewSession);
export const useChatMessages = () => useAppStore((state) => state.chatMessages);
export const useActiveFixOperations = () => useAppStore((state) => state.activeFixOperations);
export const useUIState = () => useAppStore((state) => state.ui);
export const useConnectionStatus = () => useAppStore((state) => state.ui.connectionStatus);
export const useNotifications = () => useAppStore((state) => state.ui.notifications.filter(n => !n.read));
export const useMetrics = () => useAppStore((state) => state.metrics);

// Computed selectors
export const useUnreadNotificationCount = () => 
  useAppStore((state) => state.ui.notifications.filter(n => !n.read).length);

export const useIsLoading = (key?: string) => 
  useAppStore((state) => key ? state.ui.loading.has(key) : state.ui.loading.size > 0);

export const useRecentProjects = (limit: number = 5) => 
  useAppStore((state) => 
    [...state.projects]
      .sort((a, b) => b.lastOpened.getTime() - a.lastOpened.getTime())
      .slice(0, limit)
  );

export const useFixOperationStats = () => 
  useAppStore((state) => ({
    active: state.activeFixOperations.length,
    completed: state.fixHistory.filter(op => op.status === 'completed').length,
    failed: state.fixHistory.filter(op => op.status === 'failed').length,
    successRate: state.fixHistory.length > 0 
      ? (state.fixHistory.filter(op => op.status === 'completed').length / state.fixHistory.length) * 100 
      : 0
  }));

// Action hooks for convenience
export const useAppActions = () => {
  const actions = useAppStore((state) => ({
    setUser: state.setUser,
    updateUserPreferences: state.updateUserPreferences,
    setCurrentProject: state.setCurrentProject,
    addProject: state.addProject,
    updateProject: state.updateProject,
    removeProject: state.removeProject,
    startReviewSession: state.startReviewSession,
    endReviewSession: state.endReviewSession,
    addMessageToSession: state.addMessageToSession,
    startFixOperation: state.startFixOperation,
    updateFixOperation: state.updateFixOperation,
    cancelFixOperation: state.cancelFixOperation,
    setSidebarOpen: state.setSidebarOpen,
    setActivePanel: state.setActivePanel,
    showModal: state.showModal,
    hideModal: state.hideModal,
    addNotification: state.addNotification,
    markNotificationRead: state.markNotificationRead,
    removeNotification: state.removeNotification,
    setLoading: state.setLoading,
    setConnectionStatus: state.setConnectionStatus,
    setCache: state.setCache,
    getCache: state.getCache,
    clearCache: state.clearCache,
    resetState: state.resetState,
    exportState: state.exportState,
    importState: state.importState,
    optimisticUpdate: state.optimisticUpdate
  }));
  
  return actions;
};

// Subscription hooks for reactive updates
export const useStoreSubscription = (
  selector: (state: AppState & AppActions) => any,
  callback: (selectedState: any, previousSelectedState: any) => void
) => {
  useAppStore.subscribe(
    selector,
    callback,
    {
      equalityFn: (a, b) => a === b,
      fireImmediately: false
    }
  );
};

// Performance monitoring hook
export const useStorePerformance = () => {
  const startTime = useRef(Date.now());
  const renderCount = useRef(0);
  
  renderCount.current++;
  
  return {
    renderCount: renderCount.current,
    uptime: Date.now() - startTime.current,
    storeSize: JSON.stringify(useAppStore.getState()).length
  };
};
