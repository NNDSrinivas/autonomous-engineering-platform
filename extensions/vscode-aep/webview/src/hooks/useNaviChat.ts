import { useState, useCallback, useEffect } from 'react';
import type { ChatMessage, JiraTask } from '@/types';
import { supabase } from '@/integrations/supabase/client';
import { getRecommendedModel, type TaskType } from '@/lib/llmRouter';
import { resolveBackendBase, buildHeaders } from '@/api/navi/client';

// Use local backend API endpoints
const BACKEND_BASE = resolveBackendBase();
const CHAT_URL = `${BACKEND_BASE}/api/navi/chat`;
const CHAT_STREAM_URL = `${BACKEND_BASE}/api/navi/chat/stream`;
const AUTONOMOUS_URL = `${BACKEND_BASE}/api/navi/chat/autonomous`;
// Enable streaming for autonomous mode (agent), disable for other modes
const USE_STREAMING = true;

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
      { id: 'openai/gpt-4o', name: 'GPT-4o', description: 'Optimized multimodal model' },
      { id: 'openai/gpt-4o-mini', name: 'GPT-4o Mini', description: 'Fast and affordable' },
      { id: 'openai/gpt-4-turbo', name: 'GPT-4 Turbo', description: 'Fast GPT-4' },
      { id: 'openai/o3-mini', name: 'o3-mini', description: 'Reasoning model' },
    ],
  },
  {
    id: 'anthropic',
    name: 'Anthropic',
    models: [
      { id: 'anthropic/claude-sonnet-4', name: 'Claude Sonnet 4', description: 'Latest balanced model' },
      { id: 'anthropic/claude-opus-4', name: 'Claude Opus 4', description: 'Most capable Claude' },
      { id: 'anthropic/claude-3.5-sonnet', name: 'Claude 3.5 Sonnet', description: 'Previous generation' },
      { id: 'anthropic/claude-3.5-haiku', name: 'Claude 3.5 Haiku', description: 'Fast and affordable' },
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
  workspaceRoot?: string | null;
}

export function useNaviChat({ selectedTask, userName, workspaceRoot }: UseNaviChatProps) {
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
          .single() as { data: { preference_value: unknown } | null; error: unknown };

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
    onDone: (modelUsed: { id: string; name: string }, metadata?: Record<string, unknown>) => void,
    onError: (error: string) => void,
    overrideModel?: string
  ) => {
    const conversationMessages = [
      ...messages.map(m => ({ role: m.role, content: m.content })),
      { role: 'user' as const, content: userMessage }
    ];

    try {
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

      // Get the last bot message state for autonomous coding continuity
      const lastBotMessage = messages.slice().reverse().find(m => m.role === 'assistant');
      const previousState = lastBotMessage?.metadata?.state;

      console.log('[NAVI STATE] Last bot message:', lastBotMessage?.content?.substring(0, 50));
      console.log('[NAVI STATE] Last bot metadata:', lastBotMessage?.metadata);
      console.log('[NAVI STATE] Previous state:', previousState);

      // Build request body for backend
      const requestBody: any = {
        message: userMessage,
        model: modelToUse,
      };

      // Add fields based on endpoint type
      if (chatMode === 'agent') {
        // Autonomous endpoint expects: message, model, workspace_root, run_verification, max_iterations
        if (workspaceRoot) {
          requestBody.workspace_root = workspaceRoot;
        }
        requestBody.run_verification = true;
        requestBody.max_iterations = 5;
      } else {
        // Regular chat endpoints expect: message, conversationHistory, currentTask, teamContext, model, mode, state
        requestBody.conversationHistory = messages.map(m => ({
          id: m.id,
          type: m.role,
          content: m.content,
          timestamp: m.timestamp,
        }));
        requestBody.currentTask = selectedTask ? selectedTask.key : null;
        requestBody.teamContext = selectedTask ? {
          task: {
            key: selectedTask.key,
            title: selectedTask.title,
            description: selectedTask.description,
            status: selectedTask.status,
            acceptanceCriteria: selectedTask.acceptanceCriteria,
          }
        } : null;
        requestBody.mode = chatMode;
        // Include previous state for autonomous coding continuity
        requestBody.state = previousState || undefined;
      }

      // Select endpoint based on mode - autonomous mode has its own streaming endpoint
      const endpoint = chatMode === 'agent'
        ? AUTONOMOUS_URL
        : (USE_STREAMING ? CHAT_STREAM_URL : CHAT_URL);
      const useStreaming = chatMode === 'agent' || USE_STREAMING;

      console.log('[NAVI] Sending request to:', endpoint);
      console.log('[NAVI] Mode:', chatMode, 'Streaming:', useStreaming);
      console.log('[NAVI] Request body:', requestBody);

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: buildHeaders(),
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Request failed: ${response.status}`);
      }

      if (useStreaming) {
        // Handle SSE streaming
        if (!response.body) {
          throw new Error('No response body for streaming');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Process complete lines
          let newlineIndex: number;
          while ((newlineIndex = buffer.indexOf('\n')) !== -1) {
            const line = buffer.slice(0, newlineIndex);
            buffer = buffer.slice(newlineIndex + 1);

            if (!line.trim() || line.startsWith(':')) continue;
            if (!line.startsWith('data: ')) continue;

            const data = line.slice(6).trim();
            if (data === '[DONE]') {
              onDone({ id: modelToUse, name: modelName });
              return;
            }

            try {
              const parsed = JSON.parse(data);

              // Handle different event types from autonomous endpoint
              if (parsed.type === 'status') {
                // Status updates: planning, executing, verifying, etc.
                onDelta(`\n**${parsed.status}**${parsed.message ? ': ' + parsed.message : ''}\n`);
              } else if (parsed.type === 'text' || parsed.type === 'content') {
                // Narrative text from agent
                onDelta(parsed.text || parsed.content || '');
              } else if (parsed.type === 'tool_call') {
                // Tool invocations
                onDelta(`\n🔧 ${parsed.tool || 'Tool'}: ${parsed.description || parsed.input || ''}\n`);
              } else if (parsed.type === 'tool_result') {
                // Tool results (show summary, not full output)
                const summary = parsed.summary || (parsed.output ? parsed.output.substring(0, 100) + '...' : '');
                if (summary) onDelta(`✓ ${summary}\n`);
              } else if (parsed.type === 'verification') {
                // Test results
                onDelta(`\n✅ Verification: ${parsed.message || parsed.status || ''}\n`);
              } else if (parsed.type === 'complete') {
                // Final summary
                if (parsed.summary) onDelta(`\n${parsed.summary}\n`);
              } else if (parsed.type === 'error') {
                // Error events
                throw new Error(parsed.message || parsed.error || 'Unknown error');
              } else if (parsed.type === 'heartbeat') {
                // Ignore heartbeat events (just keep-alive)
                console.debug('[NAVI] Heartbeat received');
              } else if (parsed.content) {
                // Fallback for regular content field
                onDelta(parsed.content);
              } else if (parsed.error) {
                throw new Error(parsed.error);
              }
            } catch (e) {
              console.warn('[NAVI] Failed to parse SSE data:', data, e);
            }
          }
        }

        onDone({ id: modelToUse, name: modelName });
      } else {
        // Handle non-streaming JSON response
        const data = await response.json();
        console.log('[NAVI] Response:', data);

        if (data.content || data.reply) {
          const content = data.content || data.reply;
          onDelta(content);
        } else {
          throw new Error('No content in response');
        }

        // Pass along state and agentRun metadata for autonomous coding
        const metadata: any = {};
        if (data.state) metadata.state = data.state;
        if (data.agentRun) metadata.agentRun = data.agentRun;
        if (data.suggestions) metadata.suggestions = data.suggestions;

        // 🚀 Execute VS Code commands from aggressive NAVI actions
        if (data.actions && Array.isArray(data.actions)) {
          for (const action of data.actions) {
            if (action.type === 'vscode_command' && window.vscode) {
              console.log('[NAVI] Executing VS Code command:', action.command, action.args);
              window.vscode.postMessage({
                type: 'executeCommand',
                command: action.command,
                args: action.args
              });
            }
          }
        }

        onDone({ id: modelToUse, name: modelName }, metadata);
      }
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
      timestamp: new Date().toISOString(),
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
          timestamp: new Date().toISOString(),
        }];
      });
    };

    await streamChat(
      input,
      updateAssistant,
      (model, metadata?: any) => {
        modelInfo = model;
        // Update the last assistant message with model info and metadata (state, agentRun, suggestions)
        setMessages(prev => {
          const last = prev[prev.length - 1];
          if (last?.role === 'assistant') {
            return prev.map((m, i) => i === prev.length - 1
              ? {
                ...m,
                modelId: model.id,
                modelName: model.name,
                metadata: metadata || m.metadata  // Store state/agentRun/suggestions
              }
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
          timestamp: new Date().toISOString(),
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
      await (supabase
        .from('user_preferences')
        .delete() as unknown as { eq: (col: string, val: string) => { eq: (col: string, val: string) => Promise<void> } })
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
  };
}
