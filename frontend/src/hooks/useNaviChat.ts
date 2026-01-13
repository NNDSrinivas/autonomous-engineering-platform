import { useState, useCallback, useEffect } from 'react';
import type { ChatMessage, JiraTask } from '@/types';
import { supabase } from '@/integrations/supabase/client';
import { getRecommendedModel, type TaskType } from '@/lib/llmRouter';

// Use RAG-enhanced endpoint when authenticated, otherwise fallback to basic chat
const CHAT_URL = `${import.meta.env.VITE_SUPABASE_URL}/functions/v1/navi-chat`;
const RAG_URL = `${import.meta.env.VITE_SUPABASE_URL}/functions/v1/rag-query`;

export interface LLMModel {
  id: string;
  name: string;
  description: string;
}

export interface LLMProvider {
  id: string;
  name: string;
  models: LLMModel[];
}

export type ChatMode = 'agent' | 'plan' | 'ask' | 'edit';

export const llmProviders: LLMProvider[] = [
  {
    id: 'auto',
    name: 'Auto',
    models: [
      { id: 'auto/recommended', name: 'Auto (Recommended)', description: 'Automatically selects the best model' },
    ],
  },
  {
    id: 'openai',
    name: 'OpenAI',
    models: [
      { id: 'openai/gpt-5', name: 'GPT-5', description: 'Most capable OpenAI model' },
      { id: 'openai/gpt-5-mini', name: 'GPT-5 Mini', description: 'Fast & efficient' },
      { id: 'openai/gpt-5-nano', name: 'GPT-5 Nano', description: 'Ultra-fast for simple tasks' },
      { id: 'openai/gpt-4.1', name: 'GPT-4.1', description: 'Previous generation flagship' },
      { id: 'openai/gpt-4o', name: 'GPT-4o', description: 'Optimized multimodal model' },
    ],
  },
  {
    id: 'anthropic',
    name: 'Anthropic',
    models: [
      { id: 'anthropic/claude-sonnet-4', name: 'Claude Sonnet 4', description: 'Balanced performance' },
      { id: 'anthropic/claude-opus-4', name: 'Claude Opus 4', description: 'Most capable Claude' },
      { id: 'anthropic/claude-3.5-sonnet', name: 'Claude 3.5 Sonnet', description: 'Previous generation' },
    ],
  },
  {
    id: 'google',
    name: 'Google',
    models: [
      { id: 'google/gemini-2.5-pro', name: 'Gemini 2.5 Pro', description: 'Top-tier multimodal' },
      { id: 'google/gemini-2.5-flash', name: 'Gemini 2.5 Flash', description: 'Fast & balanced' },
      { id: 'google/gemini-2.5-flash-lite', name: 'Gemini 2.5 Flash Lite', description: 'Fastest option' },
      { id: 'google/gemini-3-pro-preview', name: 'Gemini 3 Pro', description: 'Next-gen preview' },
    ],
  },
];

export const chatModes: { id: ChatMode; name: string; description: string }[] = [
  { id: 'agent', name: 'Agent', description: 'Autonomous task execution' },
  { id: 'plan', name: 'Plan', description: 'Create a step-by-step plan' },
  { id: 'ask', name: 'Ask', description: 'Get answers and explanations' },
  { id: 'edit', name: 'Edit', description: 'Make code changes' },
];

interface UseNaviChatProps {
  selectedTask: JiraTask | null;
  userName: string;
}

export function useNaviChat({ selectedTask, userName }: UseNaviChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedModel, setSelectedModel] = useState('auto/recommended');
  const [selectedProvider, setSelectedProvider] = useState('auto');
  const [chatMode, setChatMode] = useState<ChatMode>('agent');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [lastRouterInfo, setLastRouterInfo] = useState<{ taskType: TaskType; modelName: string; reason: string } | null>(null);
  const [preferencesLoaded, setPreferencesLoaded] = useState(false);

  // Load saved model preference on mount
  useEffect(() => {
    const loadPreferences = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (session) {
        const { data } = await supabase
          .from('user_preferences')
          .select('preference_value')
          .eq('user_id', session.user.id)
          .eq('preference_key', 'default_model')
          .single();
        
        if (data?.preference_value) {
          const pref = data.preference_value as { modelId: string; providerId: string };
          setSelectedModel(pref.modelId);
          setSelectedProvider(pref.providerId);
        }
      }
      setPreferencesLoaded(true);
    };
    loadPreferences();
  }, []);

  // Check auth status for RAG features
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setIsAuthenticated(!!session);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_, session) => {
      setIsAuthenticated(!!session);
    });

    return () => subscription.unsubscribe();
  }, []);

  const streamChat = useCallback(async (
    userMessage: string,
    onDelta: (delta: string) => void,
    onDone: (modelUsed: { id: string; name: string }) => void,
    onError: (error: string) => void,
    overrideModel?: string
  ) => {
    const conversationMessages = [
      ...messages.map(m => ({ role: m.role, content: m.content })),
      { role: 'user' as const, content: userMessage }
    ];

    try {
      // Use RAG endpoint if authenticated for memory-enhanced responses
      const { data: { session } } = await supabase.auth.getSession();
      const useRag = !!session;
      const endpoint = useRag ? RAG_URL : CHAT_URL;
      const authHeader = useRag 
        ? session.access_token 
        : import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;

      // Use override model if provided, otherwise use selected model
      let modelToUse = overrideModel || selectedModel;
      let modelName = '';
      
      if (modelToUse === 'auto/recommended') {
        const recommendation = getRecommendedModel(userMessage);
        modelToUse = recommendation.modelId;
        modelName = recommendation.modelName;
        setLastRouterInfo({
          taskType: recommendation.taskType,
          modelName: recommendation.modelName,
          reason: recommendation.reason,
        });
        console.log(`[NAVI Router] Detected task: ${recommendation.taskType}, using: ${recommendation.modelName} (${recommendation.reason})`);
      } else {
        setLastRouterInfo(null);
        // Find model name from providers
        for (const provider of llmProviders) {
          const model = provider.models.find(m => m.id === modelToUse);
          if (model) {
            modelName = model.name;
            break;
          }
        }
        if (!modelName) {
          // Extract readable name from model ID
          modelName = modelToUse.split('/').pop()?.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) || modelToUse;
        }
      }

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authHeader}`,
        },
        body: JSON.stringify({
          query: userMessage,
          messages: conversationMessages,
          model: modelToUse,
          mode: chatMode,
          include_memories: useRag,
          memory_count: 5,
          task_context: selectedTask ? {
            key: selectedTask.key,
            title: selectedTask.title,
            description: selectedTask.description,
            status: selectedTask.status,
            acceptanceCriteria: selectedTask.acceptanceCriteria,
          } : undefined,
          stream: true,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Request failed: ${response.status}`);
      }

      if (!response.body) {
        throw new Error('No response body');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let streamDone = false;

      while (!streamDone) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });

        let newlineIndex: number;
        while ((newlineIndex = buffer.indexOf('\n')) !== -1) {
          let line = buffer.slice(0, newlineIndex);
          buffer = buffer.slice(newlineIndex + 1);

          if (line.endsWith('\r')) line = line.slice(0, -1);
          if (line.startsWith(':') || line.trim() === '') continue;
          if (!line.startsWith('data: ')) continue;

          const jsonStr = line.slice(6).trim();
          if (jsonStr === '[DONE]') {
            streamDone = true;
            break;
          }

          try {
            const parsed = JSON.parse(jsonStr);
            const content = parsed.choices?.[0]?.delta?.content as string | undefined;
            if (content) onDelta(content);
          } catch {
            buffer = line + '\n' + buffer;
            break;
          }
        }
      }

      if (buffer.trim()) {
        for (let raw of buffer.split('\n')) {
          if (!raw || raw.startsWith(':') || raw.trim() === '') continue;
          if (!raw.startsWith('data: ')) continue;
          const jsonStr = raw.slice(6).trim();
          if (jsonStr === '[DONE]') continue;
          try {
            const parsed = JSON.parse(jsonStr);
            const content = parsed.choices?.[0]?.delta?.content as string | undefined;
            if (content) onDelta(content);
          } catch { /* ignore */ }
        }
      }

      onDone({ id: modelToUse, name: modelName });
    } catch (error) {
      console.error('[NAVI] Stream error:', error);
      onError(error instanceof Error ? error.message : 'Unknown error');
    }
  }, [messages, selectedModel, selectedTask, chatMode]);

  const sendMessage = useCallback(async (input: string, overrideModel?: string) => {
    if (!input.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    let assistantContent = '';
    let modelInfo: { id: string; name: string } | null = null;
    
    const updateAssistant = (chunk: string) => {
      assistantContent += chunk;
      setMessages(prev => {
        const last = prev[prev.length - 1];
        if (last?.role === 'assistant') {
          return prev.map((m, i) => i === prev.length - 1 ? { ...m, content: assistantContent } : m);
        }
        return [...prev, {
          id: (Date.now() + 1).toString(),
          role: 'assistant' as const,
          content: assistantContent,
          timestamp: new Date(),
        }];
      });
    };

    await streamChat(
      input,
      updateAssistant,
      (model) => {
        modelInfo = model;
        // Update the last assistant message with model info
        setMessages(prev => {
          const last = prev[prev.length - 1];
          if (last?.role === 'assistant') {
            return prev.map((m, i) => i === prev.length - 1 
              ? { ...m, modelId: model.id, modelName: model.name } 
              : m
            );
          }
          return prev;
        });
        setIsLoading(false);
      },
      (error) => {
        setIsLoading(false);
        setMessages(prev => [...prev, {
          id: (Date.now() + 2).toString(),
          role: 'assistant',
          content: `Sorry, I encountered an error: ${error}. Please try again.`,
          timestamp: new Date(),
        }]);
      },
      overrideModel
    );
  }, [isLoading, streamChat]);

  const retryWithModel = useCallback(async (messageIndex: number, modelId: string) => {
    // Find the user message before this assistant message
    const userMessage = messages.slice(0, messageIndex).reverse().find(m => m.role === 'user');
    if (!userMessage) return;

    // Remove messages from this point
    setMessages(prev => prev.slice(0, messageIndex));
    
    // Resend with the specified model
    await sendMessage(userMessage.content, modelId);
  }, [messages, sendMessage]);

  const setModel = useCallback(async (providerId: string, modelId: string, showToast = true) => {
    setSelectedProvider(providerId);
    setSelectedModel(modelId);
    
    // Persist preference if authenticated
    const { data: { session } } = await supabase.auth.getSession();
    if (session) {
      const { error } = await supabase
        .from('user_preferences')
        .upsert({
          user_id: session.user.id,
          preference_key: 'default_model',
          preference_value: { modelId, providerId },
          updated_at: new Date().toISOString(),
        }, {
          onConflict: 'user_id,preference_key',
        });
      
      if (!error && showToast) {
        const modelName = llmProviders
          .flatMap(p => p.models)
          .find(m => m.id === modelId)?.name || modelId;
        return { success: true, modelName };
      }
    }
    return { success: false };
  }, []);

  const resetModelPreference = useCallback(async () => {
    const { data: { session } } = await supabase.auth.getSession();
    if (session) {
      await supabase
        .from('user_preferences')
        .delete()
        .eq('user_id', session.user.id)
        .eq('preference_key', 'default_model');
    }
    setSelectedProvider('auto');
    setSelectedModel('auto/recommended');
    return { success: true };
  }, []);

  const getDisplayModelName = () => {
    for (const provider of llmProviders) {
      const model = provider.models.find(m => m.id === selectedModel);
      if (model) return model.name;
    }
    return 'Auto';
  };

  // NAVI V2: Create plan with approval flow
  const createPlan = useCallback(async (userMessage: string, workspace: string) => {
    try {
      // For now, use localhost:8787 for the FastAPI backend
      // In production, this would be configured via environment variable
      const backendUrl = 'http://localhost:8787';

      const response = await fetch(`${backendUrl}/api/navi/plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage,
          workspace,
          llm_provider: 'anthropic',
          context: {
            current_file: undefined,
            selected_text: undefined,
          },
        }),
      });

      if (!response.ok) {
        throw new Error(`Plan creation failed: ${response.status}`);
      }

      const data = await response.json();
      return {
        planId: data.plan_id,
        requiresApproval: data.requires_approval,
        actionsWithRisk: data.actions_with_risk || [],
        thinkingSteps: data.thinking_steps || [],
        filesRead: data.files_read || [],
        content: data.message || data.content || '',
      };
    } catch (error) {
      console.error('[NAVI] Plan creation error:', error);
      throw error;
    }
  }, []);

  return {
    messages,
    setMessages,
    isLoading,
    sendMessage,
    retryWithModel,
    selectedModel,
    selectedProvider,
    setModel,
    resetModelPreference,
    llmProviders,
    chatMode,
    setChatMode,
    chatModes,
    getDisplayModelName,
    lastRouterInfo,
    preferencesLoaded,
    createPlan, // NAVI V2: New method
  };
}
