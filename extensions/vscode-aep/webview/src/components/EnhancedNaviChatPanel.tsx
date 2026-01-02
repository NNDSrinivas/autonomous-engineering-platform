/**
 * Enhanced NAVI Chat Panel for VS Code Extension
 * Incorporates features from code-companion for improved IDE integration
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/Card';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { ScrollArea } from './ui/ScrollArea';
import { Badge } from './ui/Badge';
import { Separator } from './ui/Separator';
import { 
  MessageSquare, 
  Sparkles, 
  Clock, 
  CheckCircle2, 
  AlertCircle,
  Send,
  Bot,
  User,
  Code,
  FileText,
  Lightbulb,
  Settings,
  RefreshCw
} from 'lucide-react';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  context?: {
    file?: string;
    selection?: string;
    task?: string;
  };
  metadata?: {
    model?: string;
    tokens?: number;
    confidence?: number;
  };
}

interface NaviChatPanelProps {
  onSendMessage?: (message: string, context?: any) => Promise<string>;
  currentFile?: string;
  selectedText?: string;
  workspaceContext?: any;
  className?: string;
}

export const EnhancedNaviChatPanel: React.FC<NaviChatPanelProps> = ({
  onSendMessage,
  currentFile,
  selectedText,
  workspaceContext,
  className = ""
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedModel, setSelectedModel] = useState('auto/recommended');
  const [showContext, setShowContext] = useState(false);
  const [contextSummary, setContextSummary] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Initialize with welcome message
  useEffect(() => {
    const welcomeMessage: ChatMessage = {
      id: 'welcome',
      role: 'assistant',
      content: "Hello! I'm NAVI, your Autonomous Engineering Intelligence. I can help you with code analysis, task understanding, and development workflows. How can I assist you today?",
      timestamp: new Date().toISOString(),
      metadata: {
        model: 'system',
        confidence: 1.0
      }
    };
    setMessages([welcomeMessage]);
  }, []);

  // Update context summary when workspace context changes
  useEffect(() => {
    if (workspaceContext) {
      const summary = generateContextSummary(workspaceContext);
      setContextSummary(summary);
    }
  }, [workspaceContext, currentFile, selectedText]);

  const generateContextSummary = (context: any): string => {
    const parts = [];
    
    if (currentFile) {
      parts.push(`📄 File: ${currentFile.split('/').pop()}`);
    }
    
    if (selectedText) {
      const preview = selectedText.length > 50 
        ? selectedText.substring(0, 50) + '...' 
        : selectedText;
      parts.push(`✂️ Selection: "${preview}"`);
    }
    
    if (context?.jiraTask) {
      parts.push(`🎫 Task: ${context.jiraTask.key} - ${context.jiraTask.title}`);
    }
    
    if (context?.branch) {
      parts.push(`🌿 Branch: ${context.branch}`);
    }
    
    return parts.join(' • ');
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: `msg_${Date.now()}_user`,
      role: 'user',
      content: inputMessage,
      timestamp: new Date().toISOString(),
      context: {
        file: currentFile,
        selection: selectedText,
      }
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      // Prepare context for the AI
      const context = {
        currentFile,
        selectedText,
        workspaceContext,
        messages: messages.slice(-5) // Last 5 messages for context
      };

      const response = await onSendMessage?.(inputMessage, context) || 
                      await mockAIResponse(inputMessage, context);

      const assistantMessage: ChatMessage = {
        id: `msg_${Date.now()}_assistant`,
        role: 'assistant',
        content: response,
        timestamp: new Date().toISOString(),
        metadata: {
          model: selectedModel,
          confidence: 0.95
        }
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      const errorMessage: ChatMessage = {
        id: `msg_${Date.now()}_error`,
        role: 'system',
        content: `Error: ${error instanceof Error ? error.message : 'Unknown error occurred'}`,
        timestamp: new Date().toISOString(),
        metadata: {
          model: 'error',
          confidence: 0.0
        }
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const mockAIResponse = async (message: string, context: any): Promise<string> => {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Generate contextual response based on input
    if (message.toLowerCase().includes('help')) {
      return "I can help you with:\n• Code analysis and suggestions\n• Explaining code functionality\n• Debugging assistance\n• Task breakdown and planning\n• Integration with Jira, Confluence, and other tools";
    }
    
    if (context.selectedText) {
      return `I can see you've selected some code. This appears to be ${context.selectedText.length} characters of code. Would you like me to:\n• Explain what this code does\n• Suggest improvements\n• Find potential issues\n• Generate documentation`;
    }
    
    return `I understand you're asking about: "${message}". Based on your current context${context.currentFile ? ` in ${context.currentFile.split('/').pop()}` : ''}, I'm ready to help. Could you provide more specific details about what you'd like me to assist with?`;
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const clearChat = () => {
    setMessages([]);
  };

  const exportChat = () => {
    const chatData = {
      messages,
      timestamp: new Date().toISOString(),
      context: {
        file: currentFile,
        workspace: workspaceContext?.name
      }
    };
    
    // In VS Code extension, this would use vscode.workspace.fs
    console.log('Export chat:', chatData);
  };

  const getMessageIcon = (role: string) => {
    switch (role) {
      case 'user': return <User className="h-4 w-4" />;
      case 'assistant': return <Bot className="h-4 w-4 text-blue-500" />;
      case 'system': return <AlertCircle className="h-4 w-4 text-orange-500" />;
      default: return <MessageSquare className="h-4 w-4" />;
    }
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  return (
    <Card className={`h-full flex flex-col ${className}`}>
      <CardHeader className="flex-shrink-0 pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Sparkles className="h-5 w-5 text-blue-500" />
            NAVI Chat
          </CardTitle>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowContext(!showContext)}
              className="h-8 px-2"
            >
              <FileText className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={clearChat}
              className="h-8 px-2"
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={exportChat}
              className="h-8 px-2"
            >
              <Settings className="h-4 w-4" />
            </Button>
          </div>
        </div>
        
        {showContext && contextSummary && (
          <div className="mt-2">
            <Separator className="mb-2" />
            <div className="text-xs text-muted-foreground bg-muted p-2 rounded">
              <div className="font-medium mb-1">Context:</div>
              <div>{contextSummary}</div>
            </div>
          </div>
        )}
      </CardHeader>

      <CardContent className="flex-1 flex flex-col p-0">
        <ScrollArea className="flex-1 px-4">
          <div className="space-y-4 pb-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex gap-3 ${
                  message.role === 'user' ? 'justify-end' : 'justify-start'
                }`}
              >
                {message.role !== 'user' && (
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-muted flex items-center justify-center">
                    {getMessageIcon(message.role)}
                  </div>
                )}
                
                <div
                  className={`max-w-[80%] rounded-lg p-3 ${
                    message.role === 'user'
                      ? 'bg-primary text-primary-foreground ml-12'
                      : message.role === 'system'
                      ? 'bg-orange-100 text-orange-900 dark:bg-orange-950 dark:text-orange-100'
                      : 'bg-muted'
                  }`}
                >
                  <div className="whitespace-pre-wrap text-sm">
                    {message.content}
                  </div>
                  
                  <div className="flex items-center justify-between mt-2 pt-2 border-t border-opacity-20">
                    <span className="text-xs opacity-70">
                      {formatTimestamp(message.timestamp)}
                    </span>
                    {message.metadata?.model && (
                      <Badge variant="secondary" className="text-xs">
                        {message.metadata.model}
                      </Badge>
                    )}
                  </div>
                </div>
                
                {message.role === 'user' && (
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary flex items-center justify-center">
                    {getMessageIcon(message.role)}
                  </div>
                )}
              </div>
            ))}
            
            {isLoading && (
              <div className="flex gap-3 justify-start">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-muted flex items-center justify-center">
                  <Bot className="h-4 w-4 text-blue-500 animate-pulse" />
                </div>
                <div className="bg-muted rounded-lg p-3">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <div className="flex space-x-1">
                      <div className="w-2 h-2 bg-current rounded-full animate-bounce" />
                      <div className="w-2 h-2 bg-current rounded-full animate-bounce" style={{animationDelay: '0.1s'}} />
                      <div className="w-2 h-2 bg-current rounded-full animate-bounce" style={{animationDelay: '0.2s'}} />
                    </div>
                    NAVI is thinking...
                  </div>
                </div>
              </div>
            )}
          </div>
          <div ref={messagesEndRef} />
        </ScrollArea>

        <div className="flex-shrink-0 p-4 border-t">
          <div className="flex gap-2">
            <Input
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask NAVI anything about your code, tasks, or development workflow..."
              className="flex-1"
              disabled={isLoading}
            />
            <Button 
              onClick={handleSendMessage} 
              disabled={!inputMessage.trim() || isLoading}
              size="sm"
              className="px-3"
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
          
          <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
            <Code className="h-3 w-3" />
            <span>Model: {selectedModel}</span>
            {workspaceContext?.name && (
              <>
                <Separator orientation="vertical" className="h-3" />
                <span>Workspace: {workspaceContext.name}</span>
              </>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};