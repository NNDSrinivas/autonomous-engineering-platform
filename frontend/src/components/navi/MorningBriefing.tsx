import { useState, useEffect, useCallback } from 'react';
import { 
  Sun, 
  CheckCircle2, 
  MessageSquare, 
  Calendar, 
  RefreshCw, 
  ChevronRight,
  AlertCircle,
  Clock,
  ExternalLink,
  X,
  Link2
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { useSlackIntegration, type SlackMessageData } from '@/hooks/useSlackIntegration';
import { useCalendarIntegration, type CalendarEvent } from '@/hooks/useCalendarIntegration';
import { supabase } from '@/integrations/supabase/client';
import { format } from 'date-fns';
import type { JiraTask } from '@/types';

interface MorningBriefingProps {
  userName?: string;
  jiraTasks?: JiraTask[];
  onTaskClick?: (task: JiraTask) => void;
  onDismiss?: () => void;
  compact?: boolean;
}

const getGreeting = (): string => {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
};

const priorityColors: Record<string, string> = {
  critical: 'bg-destructive text-destructive-foreground',
  high: 'bg-orange-500/20 text-orange-400',
  medium: 'bg-yellow-500/20 text-yellow-400',
  low: 'bg-muted text-muted-foreground',
};

const statusColors: Record<string, string> = {
  todo: 'bg-muted text-muted-foreground',
  in_progress: 'bg-primary/20 text-primary',
  in_review: 'bg-purple-500/20 text-purple-400',
  blocked: 'bg-destructive/20 text-destructive',
  done: 'bg-green-500/20 text-green-400',
};

export function MorningBriefing({ 
  userName = 'there', 
  jiraTasks = [],
  onTaskClick,
  onDismiss,
  compact = false
}: MorningBriefingProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [slackMentions, setSlackMentions] = useState<SlackMessageData[]>([]);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  
  const { fetchMessages, users, fetchUsers } = useSlackIntegration();
  const { 
    events: calendarEvents, 
    fetchTodayEvents, 
    connections: calendarConnections,
    checkConnections,
    connectCalendar
  } = useCalendarIntegration();

  // Get assigned tasks (filter by current user or all if no assignee filter)
  const assignedTasks = jiraTasks.filter(task => 
    task.status !== 'done' && task.status !== 'blocked'
  ).slice(0, compact ? 3 : 5);

  const loadBriefingData = useCallback(async () => {
    setIsLoading(true);
    
    try {
      // Check auth
      const { data: { session } } = await supabase.auth.getSession();
      setIsAuthenticated(!!session);
      
      if (session) {
        // Fetch data in parallel
        await Promise.all([
          fetchUsers().then(async () => {
            const messages = await fetchMessages();
            // Filter for mentions
            const mentions = messages.filter((msg: SlackMessageData) => 
              msg.text?.includes('<@') || msg.text?.includes('@')
            ).slice(0, compact ? 3 : 5);
            setSlackMentions(mentions);
          }),
          checkConnections().then(() => fetchTodayEvents()),
        ]);
      }
    } catch (err) {
      console.error('Failed to load briefing data:', err);
    } finally {
      setIsLoading(false);
    }
  }, [fetchMessages, fetchUsers]);

  useEffect(() => {
    loadBriefingData();
  }, [loadBriefingData]);

  const formatMeetingTime = (date: Date) => {
    return format(date, 'h:mm a');
  };

  const getUserName = (userId: string) => {
    return users.get(userId)?.real_name || userId;
  };

  return (
    <Card className="w-full bg-gradient-to-br from-primary/5 via-background to-secondary/5 border-primary/20 shadow-lg">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-full bg-primary/10">
              <Sun className="h-5 w-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-lg font-semibold">
                {getGreeting()}, {userName}!
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                {format(new Date(), 'EEEE, MMMM d')}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={loadBriefingData}
              disabled={isLoading}
              className="h-8 w-8"
            >
              <RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} />
            </Button>
            {onDismiss && (
              <Button 
                variant="ghost" 
                size="icon" 
                onClick={onDismiss}
                className="h-8 w-8"
              >
                <X className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      
      <CardContent className="space-y-4">
        {/* Quick Stats */}
        <div className="grid grid-cols-3 gap-3">
          <div className="flex flex-col items-center p-3 rounded-lg bg-secondary/50">
            <CheckCircle2 className="h-5 w-5 text-primary mb-1" />
            <span className="text-2xl font-bold">{assignedTasks.length}</span>
            <span className="text-xs text-muted-foreground">Tasks</span>
          </div>
          <div className="flex flex-col items-center p-3 rounded-lg bg-secondary/50">
            <MessageSquare className="h-5 w-5 text-primary mb-1" />
            <span className="text-2xl font-bold">{slackMentions.length}</span>
            <span className="text-xs text-muted-foreground">Mentions</span>
          </div>
          <div className="flex flex-col items-center p-3 rounded-lg bg-secondary/50">
            <Calendar className="h-5 w-5 text-primary mb-1" />
            <span className="text-2xl font-bold">{calendarEvents.length}</span>
            <span className="text-xs text-muted-foreground">Meetings</span>
          </div>
        </div>

        {/* Tasks Section */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-medium">Your Tasks</h3>
          </div>
          
          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          ) : assignedTasks.length > 0 ? (
            <ScrollArea className="max-h-32">
              <div className="space-y-1.5">
                {assignedTasks.map(task => (
                  <div
                    key={task.id}
                    onClick={() => onTaskClick?.(task)}
                    className="flex items-center justify-between p-2 rounded-md bg-secondary/30 hover:bg-secondary/50 cursor-pointer transition-colors group"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <Badge variant="outline" className="text-[10px] shrink-0">
                        {task.key}
                      </Badge>
                      <span className="text-sm truncate">{task.title}</span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Badge className={cn("text-[10px]", priorityColors[task.priority])}>
                        {task.priority}
                      </Badge>
                      <ChevronRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          ) : (
            <p className="text-sm text-muted-foreground py-2">
              No pending tasks. You're all caught up!
            </p>
          )}
        </div>

        {/* Slack Mentions Section */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-medium">Recent Mentions</h3>
          </div>
          
          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : !isAuthenticated ? (
            <p className="text-sm text-muted-foreground py-2">
              Sign in to see Slack mentions
            </p>
          ) : slackMentions.length > 0 ? (
            <ScrollArea className="max-h-28">
              <div className="space-y-1.5">
                {slackMentions.map(mention => (
                  <div
                    key={mention.ts}
                    className="flex items-start gap-2 p-2 rounded-md bg-secondary/30"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium text-primary">
                          #{mention.channel_name || mention.channel}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {getUserName(mention.user)}
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground truncate">
                        {mention.text}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          ) : (
            <p className="text-sm text-muted-foreground py-2">
              No recent mentions
            </p>
          )}
        </div>

        {/* Meetings Section */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-medium">Today's Meetings</h3>
          </div>
          
          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-12 w-full" />
            </div>
          ) : calendarConnections.length === 0 ? (
            <div className="flex items-center gap-2 p-2 rounded-md bg-secondary/30">
              <Link2 className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground flex-1">No calendar connected</span>
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                onClick={() => connectCalendar('google_calendar')}
              >
                Connect Google
              </Button>
            </div>
          ) : calendarEvents.length > 0 ? (
            <div className="space-y-1.5">
              {calendarEvents.slice(0, compact ? 3 : 5).map(event => (
                <div
                  key={event.id}
                  className="flex items-center justify-between p-2 rounded-md bg-secondary/30"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="flex items-center gap-1 text-primary shrink-0">
                      <Clock className="h-3.5 w-3.5" />
                      <span className="text-xs font-medium">
                        {formatMeetingTime(event.start)}
                      </span>
                    </div>
                    <div className="min-w-0">
                      <span className="text-sm truncate block">{event.title}</span>
                      {event.attendees.length > 0 && (
                        <span className="text-xs text-muted-foreground">
                          {event.attendees.slice(0, 2).join(', ')}{event.attendees.length > 2 ? ` +${event.attendees.length - 2}` : ''}
                        </span>
                      )}
                    </div>
                  </div>
                  {event.meetingUrl && (
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      className="h-7 w-7 shrink-0"
                      asChild
                    >
                      <a href={event.meetingUrl} target="_blank" rel="noopener noreferrer">
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    </Button>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground py-2">
              No meetings scheduled today
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
