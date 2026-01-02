import { useState, useEffect, useMemo, useCallback } from 'react';
import type { ChatMessage, JiraTask } from '@/types';

// Rotating placeholder messages showcasing NAVI capabilities
const PLACEHOLDER_MESSAGES = [
  "Ask NAVI anything about your projects, tasks, or codebase...",
  "Try: 'Explain my highest priority task and suggest implementation steps'",
  "Try: 'Review my latest PR and summarize the feedback'",
  "Try: 'Search Confluence for our authentication design docs'",
  "Try: 'What's the status of the current sprint?'",
  "Try: 'Generate unit tests for the user service module'",
  "Try: 'Debug this error: TypeError: Cannot read property'",
  "Try: 'Summarize yesterday's standup meeting'",
  "Try: 'Create a new feature branch and start working on JIRA-123'",
  "Try: 'What files would I need to modify for this task?'",
  "Try: 'Check CI/CD pipeline status for main branch'",
  "Try: 'Find all Slack mentions about the API migration'",
  "Try: 'Generate a code review checklist for my changes'",
  "Try: 'Explain the architecture of our payment system'",
  "Try: 'What are the acceptance criteria for this story?'",
  "Try: 'Draft a PR description for my current changes'",
  "Try: 'Find related tasks that might conflict with mine'",
  "Try: 'Show me examples of error handling in our codebase'",
];

// Context-aware prompt categories
interface PromptCategory {
  id: string;
  condition: (context: PromptContext) => boolean;
  prompts: string[];
  priority: number;
}

interface PromptContext {
  selectedTask: JiraTask | null;
  messages: ChatMessage[];
  hasGitHubConnected: boolean;
  hasSlackConnected: boolean;
  hasConfluenceConnected: boolean;
  hasPendingPR: boolean;
  hasFailingBuild: boolean;
  timeOfDay: 'morning' | 'afternoon' | 'evening';
  lastMessageContent: string;
  conversationTopics: string[];
}

// Define prompt categories with conditions
const PROMPT_CATEGORIES: PromptCategory[] = [
  {
    id: 'task_selected',
    condition: (ctx) => !!ctx.selectedTask,
    priority: 10,
    prompts: [
      'Explain this task',
      'How should I implement this?',
      'What files need changes?',
      'Generate the code',
      'Write unit tests',
    ],
  },
  {
    id: 'task_in_progress',
    condition: (ctx) => ctx.selectedTask?.status === 'in_progress',
    priority: 15,
    prompts: [
      'Create a PR for this task',
      'Commit my changes',
      'Run the tests',
      'Check for blockers',
      'Update task status',
    ],
  },
  {
    id: 'morning',
    condition: (ctx) => ctx.timeOfDay === 'morning' && ctx.messages.length <= 2,
    priority: 5,
    prompts: [
      'Show my daily briefing',
      'What are my priorities today?',
      "Summarize yesterday's activity",
      'Show my tasks',
      'Any urgent items?',
    ],
  },
  {
    id: 'code_discussion',
    condition: (ctx) => {
      const codeKeywords = ['code', 'function', 'component', 'error', 'bug', 'test', 'implement'];
      return codeKeywords.some(kw => ctx.lastMessageContent.toLowerCase().includes(kw));
    },
    priority: 8,
    prompts: [
      'Show me the code',
      'Explain this further',
      'Write tests for this',
      'Refactor this code',
      'Fix this issue',
    ],
  },
  {
    id: 'pr_workflow',
    condition: (ctx) => ctx.hasPendingPR || ctx.lastMessageContent.toLowerCase().includes('pr'),
    priority: 9,
    prompts: [
      'Review my PR',
      'Address PR comments',
      'Check CI status',
      'Merge the PR',
      'Close the PR',
    ],
  },
  {
    id: 'build_failure',
    condition: (ctx) => ctx.hasFailingBuild,
    priority: 12,
    prompts: [
      'Why is the build failing?',
      'Show build logs',
      'Fix the failing tests',
      'Re-run the pipeline',
      'Debug CI issues',
    ],
  },
  {
    id: 'documentation',
    condition: (ctx) => {
      const docKeywords = ['doc', 'confluence', 'wiki', 'readme', 'adr', 'design'];
      return docKeywords.some(kw => ctx.lastMessageContent.toLowerCase().includes(kw));
    },
    priority: 7,
    prompts: [
      'Search Confluence docs',
      'Find design docs',
      'Update documentation',
      'Generate README',
      'Create ADR',
    ],
  },
  {
    id: 'default',
    condition: () => true,
    priority: 0,
    prompts: [
      'Show my tasks',
      'Generate code',
      'Explain this task',
      'Review my PR',
      'Debug help',
    ],
  },
];

export function useSmartPrompts(
  selectedTask: JiraTask | null,
  messages: ChatMessage[],
  integrations: {
    github?: boolean;
    slack?: boolean;
    confluence?: boolean;
    hasPendingPR?: boolean;
    hasFailingBuild?: boolean;
  } = {}
) {
  const [placeholderIndex, setPlaceholderIndex] = useState(0);
  const [isTransitioning, setIsTransitioning] = useState(false);

  // Rotate placeholder every 5 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      setIsTransitioning(true);
      setTimeout(() => {
        setPlaceholderIndex((prev) => (prev + 1) % PLACEHOLDER_MESSAGES.length);
        setIsTransitioning(false);
      }, 200);
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  // Get time of day
  const getTimeOfDay = useCallback((): 'morning' | 'afternoon' | 'evening' => {
    const hour = new Date().getHours();
    if (hour < 12) return 'morning';
    if (hour < 17) return 'afternoon';
    return 'evening';
  }, []);

  // Extract conversation topics from recent messages
  const conversationTopics = useMemo(() => {
    const recentMessages = messages.slice(-5);
    const topics: string[] = [];
    const keywords = ['task', 'code', 'pr', 'bug', 'test', 'deploy', 'review', 'jira', 'slack', 'meeting'];
    
    recentMessages.forEach(msg => {
      keywords.forEach(kw => {
        if (msg.content.toLowerCase().includes(kw) && !topics.includes(kw)) {
          topics.push(kw);
        }
      });
    });
    
    return topics;
  }, [messages]);

  // Build context
  const context = useMemo((): PromptContext => ({
    selectedTask,
    messages,
    hasGitHubConnected: integrations.github ?? false,
    hasSlackConnected: integrations.slack ?? false,
    hasConfluenceConnected: integrations.confluence ?? false,
    hasPendingPR: integrations.hasPendingPR ?? false,
    hasFailingBuild: integrations.hasFailingBuild ?? false,
    timeOfDay: getTimeOfDay(),
    lastMessageContent: messages[messages.length - 1]?.content || '',
    conversationTopics,
  }), [selectedTask, messages, integrations, getTimeOfDay, conversationTopics]);

  // Get smart prompts based on context
  const smartPrompts = useMemo(() => {
    // Find matching categories sorted by priority
    const matchingCategories = PROMPT_CATEGORIES
      .filter(cat => cat.condition(context))
      .sort((a, b) => b.priority - a.priority);

    // Get prompts from top 2 matching categories
    const prompts = new Set<string>();
    for (const category of matchingCategories.slice(0, 2)) {
      category.prompts.forEach(p => prompts.add(p));
    }

    // Return top 5 unique prompts
    return Array.from(prompts).slice(0, 5);
  }, [context]);

  // Get current placeholder
  const currentPlaceholder = PLACEHOLDER_MESSAGES[placeholderIndex];

  return {
    smartPrompts,
    currentPlaceholder,
    isPlaceholderTransitioning: isTransitioning,
    conversationTopics,
    context,
  };
}
