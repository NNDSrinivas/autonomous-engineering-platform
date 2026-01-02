import { useState, useCallback } from 'react';
import { supabase } from '@/integrations/supabase/client';

export type MemoryType = 
  | 'user_preference'
  | 'task_context'
  | 'code_snippet'
  | 'meeting_note'
  | 'conversation'
  | 'documentation'
  | 'slack_message'
  | 'jira_ticket';

export type MemorySource = 
  | 'jira'
  | 'confluence'
  | 'slack'
  | 'teams'
  | 'zoom'
  | 'github'
  | 'manual'
  | 'conversation';

export interface Memory {
  id: string;
  memory_type: MemoryType;
  source: MemorySource;
  title?: string;
  content: string;
  metadata?: Record<string, any>;
  source_url?: string;
  similarity?: number;
  created_at: string;
}

export interface UserPreferences {
  coding_style?: {
    language?: string;
    framework?: string;
    indentation?: string;
    naming_convention?: string;
  };
  ui_preferences?: {
    theme?: string;
    sidebar_collapsed?: boolean;
    terminal_expanded?: boolean;
  };
  llm_preferences?: {
    default_model?: string;
    default_provider?: string;
    chat_mode?: string;
  };
  notification_preferences?: {
    daily_digest?: boolean;
    task_reminders?: boolean;
  };
  recent_projects?: string[];
  recent_tasks?: string[];
}

export interface TaskMemory {
  id: string;
  task_id: string;
  task_key?: string;
  title?: string;
  description?: string;
  related_content?: any[];
  status?: string;
  priority?: string;
  assignee?: string;
  updated_at: string;
}

export interface ConversationMemory {
  id: string;
  conversation_id: string;
  summary?: string;
  message_count: number;
  key_topics?: string[];
  last_message_at: string;
}

const MEMORY_URL = `${import.meta.env.VITE_SUPABASE_URL}/functions/v1/memory`;

export function useMemory() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const callMemoryAPI = useCallback(async (action: string, params: Record<string, any> = {}) => {
    setIsLoading(true);
    setError(null);

    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        throw new Error('Not authenticated');
      }

      const response = await fetch(MEMORY_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({ action, ...params }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Request failed: ${response.status}`);
      }

      return await response.json();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Store a new memory
  const storeMemory = useCallback(async (params: {
    memory_type: MemoryType;
    source: MemorySource;
    title?: string;
    content: string;
    metadata?: Record<string, any>;
    source_url?: string;
    source_id?: string;
    organization_id?: string;
  }) => {
    const result = await callMemoryAPI('store', params);
    return result.memory as Memory;
  }, [callMemoryAPI]);

  // Search memories by semantic similarity
  const searchMemories = useCallback(async (
    query: string, 
    options?: { match_count?: number; memory_type?: MemoryType }
  ) => {
    const result = await callMemoryAPI('search', { query, ...options });
    return result.results as Memory[];
  }, [callMemoryAPI]);

  // Get user preferences
  const getPreferences = useCallback(async () => {
    const result = await callMemoryAPI('get_preferences');
    return result.preferences as UserPreferences;
  }, [callMemoryAPI]);

  // Set a user preference
  const setPreference = useCallback(async (key: string, value: any) => {
    await callMemoryAPI('set_preference', { key, value });
  }, [callMemoryAPI]);

  // Save conversation summary
  const saveConversation = useCallback(async (params: {
    conversation_id: string;
    summary: string;
    message_count: number;
    key_topics?: string[];
    metadata?: Record<string, any>;
  }) => {
    const result = await callMemoryAPI('save_conversation', params);
    return result.conversation as ConversationMemory;
  }, [callMemoryAPI]);

  // Get recent conversations
  const getRecentConversations = useCallback(async (limit = 10) => {
    const result = await callMemoryAPI('get_recent_conversations', { limit });
    return result.conversations as ConversationMemory[];
  }, [callMemoryAPI]);

  // Store task memory
  const storeTask = useCallback(async (params: {
    task_id: string;
    task_key?: string;
    title?: string;
    description?: string;
    related_content?: any[];
    status?: string;
    priority?: string;
    assignee?: string;
  }) => {
    const result = await callMemoryAPI('store_task', params);
    return result.task as TaskMemory;
  }, [callMemoryAPI]);

  // Get user's tasks
  const getTasks = useCallback(async (options?: { status?: string; limit?: number }) => {
    const result = await callMemoryAPI('get_tasks', options || {});
    return result.tasks as TaskMemory[];
  }, [callMemoryAPI]);

  // Get memories with optional filtering
  const getMemories = useCallback(async (options?: { 
    memory_type?: MemoryType; 
    source?: MemorySource; 
    limit?: number 
  }) => {
    const result = await callMemoryAPI('get_memories', options || {});
    return result.memories as Memory[];
  }, [callMemoryAPI]);

  // Delete a memory
  const deleteMemory = useCallback(async (memoryId: string) => {
    await callMemoryAPI('delete_memory', { memory_id: memoryId });
  }, [callMemoryAPI]);

  return {
    isLoading,
    error,
    storeMemory,
    searchMemories,
    getPreferences,
    setPreference,
    saveConversation,
    getRecentConversations,
    storeTask,
    getTasks,
    getMemories,
    deleteMemory,
  };
}
