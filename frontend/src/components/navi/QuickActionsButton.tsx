import { useState } from 'react';
import { 
  Zap, 
  Plus, 
  X,
  MessageSquare,
  FileText,
  GitBranch,
  Play,
  Bug,
  Search,
  Settings,
  RefreshCw,
  Sparkles,
  LayoutGrid,
  Clock,
  Bell,
  Code,
  Keyboard
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface QuickAction {
  id: string;
  icon: React.ElementType;
  label: string;
  shortcut?: string;
  color?: string;
  onClick: () => void;
}

interface QuickActionsButtonProps {
  currentView: string | null;
  onOpenSearch: () => void;
  onOpenTasks: () => void;
  onOpenSettings: () => void;
  onOpenHistory: () => void;
  onOpenNotifications: () => void;
  onOpenShortcuts: () => void;
  onFocusChat: () => void;
}

export function QuickActionsButton({
  currentView,
  onOpenSearch,
  onOpenTasks,
  onOpenSettings,
  onOpenHistory,
  onOpenNotifications,
  onOpenShortcuts,
  onFocusChat,
}: QuickActionsButtonProps) {
  const [isOpen, setIsOpen] = useState(false);

  // Context-aware actions based on current view
  const getContextActions = (): QuickAction[] => {
    const baseActions: QuickAction[] = [
      {
        id: 'shortcuts',
        icon: Keyboard,
        label: 'Keyboard shortcuts',
        shortcut: '⌘?',
        onClick: () => { onOpenShortcuts(); setIsOpen(false); },
      },
    ];

    switch (currentView) {
      case 'tasks':
        return [
          {
            id: 'start-task',
            icon: Play,
            label: 'Start working on task',
            color: 'text-green-400',
            onClick: () => { setIsOpen(false); },
          },
          {
            id: 'create-pr',
            icon: GitBranch,
            label: 'Create pull request',
            shortcut: '⌘⇧P',
            color: 'text-purple-400',
            onClick: () => { setIsOpen(false); },
          },
          {
            id: 'ask-navi',
            icon: Sparkles,
            label: 'Ask NAVI about task',
            color: 'text-primary',
            onClick: () => { onFocusChat(); setIsOpen(false); },
          },
          ...baseActions,
        ];

      case 'search':
        return [
          {
            id: 'search-code',
            icon: Code,
            label: 'Search in codebase',
            color: 'text-syntax-function',
            onClick: () => { setIsOpen(false); },
          },
          {
            id: 'search-docs',
            icon: FileText,
            label: 'Search documentation',
            color: 'text-blue-400',
            onClick: () => { setIsOpen(false); },
          },
          {
            id: 'search-messages',
            icon: MessageSquare,
            label: 'Search messages',
            color: 'text-purple-400',
            onClick: () => { setIsOpen(false); },
          },
          ...baseActions,
        ];

      case 'settings':
        return [
          {
            id: 'sync-all',
            icon: RefreshCw,
            label: 'Sync all integrations',
            color: 'text-green-400',
            onClick: () => { setIsOpen(false); },
          },
          {
            id: 'manage-connectors',
            icon: LayoutGrid,
            label: 'Manage connectors',
            color: 'text-blue-400',
            onClick: () => { setIsOpen(false); },
          },
          ...baseActions,
        ];

      case 'history':
        return [
          {
            id: 'clear-history',
            icon: Clock,
            label: 'Clear history',
            color: 'text-orange-400',
            onClick: () => { setIsOpen(false); },
          },
          {
            id: 'export-chat',
            icon: FileText,
            label: 'Export conversation',
            color: 'text-blue-400',
            onClick: () => { setIsOpen(false); },
          },
          ...baseActions,
        ];

      case 'activity':
        return [
          {
            id: 'mark-read',
            icon: Bell,
            label: 'Mark all as read',
            color: 'text-green-400',
            onClick: () => { setIsOpen(false); },
          },
          {
            id: 'refresh-feed',
            icon: RefreshCw,
            label: 'Refresh activity',
            color: 'text-blue-400',
            onClick: () => { setIsOpen(false); },
          },
          ...baseActions,
        ];

      // Default: Chat view or no view
      default:
        return [
          {
            id: 'ask-navi',
            icon: Sparkles,
            label: 'Ask NAVI',
            shortcut: '⌘B',
            color: 'text-primary',
            onClick: () => { onFocusChat(); setIsOpen(false); },
          },
          {
            id: 'search',
            icon: Search,
            label: 'Universal search',
            shortcut: '⌘K',
            color: 'text-syntax-function',
            onClick: () => { onOpenSearch(); setIsOpen(false); },
          },
          {
            id: 'tasks',
            icon: LayoutGrid,
            label: 'View tasks',
            shortcut: '⌘T',
            color: 'text-blue-400',
            onClick: () => { onOpenTasks(); setIsOpen(false); },
          },
          {
            id: 'debug',
            icon: Bug,
            label: 'Debug with NAVI',
            shortcut: '⌘D',
            color: 'text-orange-400',
            onClick: () => { onFocusChat(); setIsOpen(false); },
          },
          {
            id: 'history',
            icon: Clock,
            label: 'Chat history',
            shortcut: '⌘H',
            onClick: () => { onOpenHistory(); setIsOpen(false); },
          },
          ...baseActions,
        ];
    }
  };

  const actions = getContextActions();

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col-reverse items-end gap-2">
      {/* Action Items */}
      <div className={cn(
        "flex flex-col-reverse gap-2 transition-all duration-300",
        isOpen ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4 pointer-events-none"
      )}>
        {actions.map((action, index) => (
          <div
            key={action.id}
            className="flex items-center gap-2 animate-fade-in"
            style={{ animationDelay: `${index * 50}ms` }}
          >
            {/* Label */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-popover border border-border shadow-lg">
              <span className="text-sm font-medium whitespace-nowrap">{action.label}</span>
              {action.shortcut && (
                <kbd className="px-1.5 py-0.5 text-[10px] font-mono bg-secondary rounded">
                  {action.shortcut}
                </kbd>
              )}
            </div>
            
            {/* Icon Button */}
            <Button
              variant="outline"
              size="icon"
              onClick={action.onClick}
              className={cn(
                "h-10 w-10 rounded-full shadow-lg bg-popover border-border hover:bg-secondary transition-all duration-200 hover:scale-110",
                action.color
              )}
            >
              <action.icon className={cn("h-4 w-4", action.color)} />
            </Button>
          </div>
        ))}
      </div>

      {/* Main FAB */}
      <Button
        variant="ai"
        size="icon"
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "h-14 w-14 rounded-full shadow-xl transition-all duration-300 hover:scale-110",
          isOpen && "rotate-45 bg-destructive hover:bg-destructive/90"
        )}
      >
        {isOpen ? (
          <X className="h-6 w-6" />
        ) : (
          <Zap className="h-6 w-6" />
        )}
      </Button>

      {/* Backdrop */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-background/50 backdrop-blur-sm -z-10 animate-fade-in"
          onClick={() => setIsOpen(false)}
        />
      )}
    </div>
  );
}
