/**
 * Code-Companion Integration Status Dashboard
 * Shows the progress of migrating features from code-companion to AEP
 */

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/Card';
import { Badge } from './ui/Badge';
import { Progress } from './ui/Progress';
import { 
  CheckCircle2, 
  Circle, 
  AlertTriangle,
  Sparkles,
  Zap,
  Database,
  Code,
  Puzzle,
  Bot
} from 'lucide-react';

interface MigrationItem {
  name: string;
  category: 'UI Components' | 'Backend APIs' | 'Hooks' | 'VS Code Extension' | 'Memory System';
  status: 'completed' | 'in-progress' | 'pending' | 'testing';
  description: string;
  source: string;
  target: string;
}

const migrationItems: MigrationItem[] = [
  {
    name: 'MorningBriefing Component',
    category: 'UI Components',
    status: 'completed',
    description: 'Enhanced morning briefing with task summaries and context',
    source: 'code-companion/src/components/navi/MorningBriefing.tsx',
    target: 'AEP/frontend/src/components/navi/MorningBriefing.tsx'
  },
  {
    name: 'UniversalSearch Component',
    category: 'UI Components', 
    status: 'completed',
    description: 'Advanced search across all platforms (Jira, Confluence, Slack)',
    source: 'code-companion/src/components/navi/UniversalSearch.tsx',
    target: 'AEP/frontend/src/components/navi/UniversalSearch.tsx'
  },
  {
    name: 'TaskCorrelationPanel',
    category: 'UI Components',
    status: 'completed',
    description: 'Intelligent task correlation and dependency analysis',
    source: 'code-companion/src/components/navi/TaskCorrelationPanel.tsx',
    target: 'AEP/frontend/src/components/navi/TaskCorrelationPanel.tsx'
  },
  {
    name: 'EndToEndWorkflowPanel',
    category: 'UI Components',
    status: 'completed',
    description: 'Complete workflow orchestration interface',
    source: 'code-companion/src/components/navi/EndToEndWorkflowPanel.tsx',
    target: 'AEP/frontend/src/components/navi/EndToEndWorkflowPanel.tsx'
  },
  {
    name: 'QuickActionsButton',
    category: 'UI Components',
    status: 'completed',
    description: 'Context-aware quick actions and shortcuts',
    source: 'code-companion/src/components/navi/QuickActionsButton.tsx',
    target: 'AEP/frontend/src/components/navi/QuickActionsButton.tsx'
  },
  {
    name: 'ApprovalDialog',
    category: 'UI Components',
    status: 'completed',
    description: 'Enhanced approval system with detailed context',
    source: 'code-companion/src/components/navi/ApprovalDialog.tsx',
    target: 'AEP/frontend/src/components/navi/ApprovalDialog.tsx'
  },
  {
    name: 'Enhanced NAVI Chat API',
    category: 'Backend APIs',
    status: 'completed',
    description: 'Multi-LLM chat API with context awareness',
    source: 'code-companion/supabase/functions/navi-chat/',
    target: 'AEP/backend/api/routers/navi_chat_enhanced.py'
  },
  {
    name: 'Enhanced Memory API',
    category: 'Backend APIs',
    status: 'completed',
    description: 'Advanced memory management with vector search',
    source: 'code-companion/supabase/functions/memory/',
    target: 'AEP/backend/api/routers/memory_enhanced.py'
  },
  {
    name: 'useMemory Hook',
    category: 'Hooks',
    status: 'completed',
    description: 'Enhanced memory management hook with vector search',
    source: 'code-companion/src/hooks/useMemory.ts',
    target: 'AEP/frontend/src/hooks/useMemory.ts'
  },
  {
    name: 'useNaviChat Hook',
    category: 'Hooks',
    status: 'completed',
    description: 'Advanced chat hook with multi-LLM support',
    source: 'code-companion/src/hooks/useNaviChat.ts',
    target: 'AEP/frontend/src/hooks/useNaviChat.ts'
  },
  {
    name: 'useSmartPrompts Hook',
    category: 'Hooks',
    status: 'completed',
    description: 'Context-aware prompt generation',
    source: 'code-companion/src/hooks/useSmartPrompts.ts',
    target: 'AEP/frontend/src/hooks/useSmartPrompts.ts'
  },
  {
    name: 'Enhanced Chat Panel',
    category: 'VS Code Extension',
    status: 'in-progress',
    description: 'Advanced chat interface for VS Code webview',
    source: 'code-companion UI patterns',
    target: 'AEP/extensions/vscode-aep/webview/src/components/EnhancedNaviChatPanel.tsx'
  },
  {
    name: 'Vector Memory Integration',
    category: 'Memory System',
    status: 'pending',
    description: 'Integration with existing AEP memory and vector systems',
    source: 'code-companion memory architecture',
    target: 'AEP memory subsystem'
  }
];

const statusIcons = {
  completed: <CheckCircle2 className="h-4 w-4 text-green-500" />,
  'in-progress': <AlertTriangle className="h-4 w-4 text-yellow-500" />,
  pending: <Circle className="h-4 w-4 text-gray-400" />,
  testing: <Zap className="h-4 w-4 text-blue-500" />
};

const statusColors = {
  completed: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100',
  'in-progress': 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-100',
  pending: 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-100',
  testing: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-100'
};

const categoryIcons = {
  'UI Components': <Code className="h-4 w-4" />,
  'Backend APIs': <Database className="h-4 w-4" />,
  'Hooks': <Puzzle className="h-4 w-4" />,
  'VS Code Extension': <Bot className="h-4 w-4" />,
  'Memory System': <Sparkles className="h-4 w-4" />
};

export const CodeCompanionIntegrationDashboard: React.FC = () => {
  const completedCount = migrationItems.filter(item => item.status === 'completed').length;
  const totalCount = migrationItems.length;
  const completionPercentage = Math.round((completedCount / totalCount) * 100);

  const groupedItems = migrationItems.reduce((acc, item) => {
    if (!acc[item.category]) {
      acc[item.category] = [];
    }
    acc[item.category].push(item);
    return acc;
  }, {} as Record<string, MigrationItem[]>);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-blue-500" />
            Code-Companion → AEP Integration Progress
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm font-medium">Overall Progress</span>
                <span className="text-sm text-muted-foreground">
                  {completedCount} of {totalCount} items completed
                </span>
              </div>
              <Progress value={completionPercentage} className="h-2" />
              <p className="text-xs text-muted-foreground mt-1">
                {completionPercentage}% complete
              </p>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div className="text-center p-3 bg-green-50 dark:bg-green-950 rounded-lg">
                <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                  {migrationItems.filter(item => item.status === 'completed').length}
                </div>
                <div className="text-green-700 dark:text-green-300">Completed</div>
              </div>
              
              <div className="text-center p-3 bg-yellow-50 dark:bg-yellow-950 rounded-lg">
                <div className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">
                  {migrationItems.filter(item => item.status === 'in-progress').length}
                </div>
                <div className="text-yellow-700 dark:text-yellow-300">In Progress</div>
              </div>
              
              <div className="text-center p-3 bg-gray-50 dark:bg-gray-950 rounded-lg">
                <div className="text-2xl font-bold text-gray-600 dark:text-gray-400">
                  {migrationItems.filter(item => item.status === 'pending').length}
                </div>
                <div className="text-gray-700 dark:text-gray-300">Pending</div>
              </div>
              
              <div className="text-center p-3 bg-blue-50 dark:bg-blue-950 rounded-lg">
                <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                  {migrationItems.filter(item => item.status === 'testing').length}
                </div>
                <div className="text-blue-700 dark:text-blue-300">Testing</div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-4">
        {Object.entries(groupedItems).map(([category, items]) => (
          <Card key={category}>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                {categoryIcons[category as keyof typeof categoryIcons]}
                {category}
                <Badge variant="secondary" className="ml-auto">
                  {items.filter(item => item.status === 'completed').length} / {items.length}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="space-y-3">
                {items.map((item, index) => (
                  <div key={index} className="flex items-start gap-3 p-3 bg-muted/50 rounded-lg">
                    <div className="flex-shrink-0 mt-0.5">
                      {statusIcons[item.status]}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className="font-medium text-sm">{item.name}</h4>
                        <Badge 
                          variant="secondary" 
                          className={`text-xs ${statusColors[item.status]}`}
                        >
                          {item.status}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground mb-2">
                        {item.description}
                      </p>
                      <div className="text-xs space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-muted-foreground">Source:</span>
                          <code className="bg-muted px-1 rounded text-xs">{item.source}</code>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-muted-foreground">Target:</span>
                          <code className="bg-muted px-1 rounded text-xs">{item.target}</code>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="border-dashed">
        <CardContent className="pt-6">
          <div className="text-center space-y-2">
            <Zap className="h-8 w-8 text-blue-500 mx-auto" />
            <h3 className="font-semibold">Integration Benefits</h3>
            <p className="text-sm text-muted-foreground max-w-md mx-auto">
              This integration combines the best of both platforms: AEP's mature architecture with 
              code-companion's modern UI innovations, creating the most comprehensive NAVI platform.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};