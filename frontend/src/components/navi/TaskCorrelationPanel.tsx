import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Input } from '@/components/ui/input';
import { 
  Link2, 
  FileCode, 
  GitBranch, 
  GitCommit,
  GitPullRequest,
  MessageSquare,
  FileText,
  Plus,
  Loader2,
  ExternalLink,
  Trash2,
  Sparkles
} from 'lucide-react';
import { useTaskCorrelation } from '@/hooks/useAIFeatures';
import { cn } from '@/lib/utils';
import type { JiraTask } from '@/types';

interface TaskCorrelationPanelProps {
  selectedTask: JiraTask | null;
}

const typeIcons = {
  file: FileCode,
  pr: GitPullRequest,
  commit: GitCommit,
  branch: GitBranch,
  slack_thread: MessageSquare,
  confluence_page: FileText
};

const typeLabels = {
  file: 'File',
  pr: 'Pull Request',
  commit: 'Commit',
  branch: 'Branch',
  slack_thread: 'Slack Thread',
  confluence_page: 'Confluence Page'
};

export function TaskCorrelationPanel({ selectedTask }: TaskCorrelationPanelProps) {
  const task = selectedTask;
  const {
    isAnalyzing, 
    analysis, 
    linkedItems, 
    analyzeTask, 
    linkItems, 
    fetchLinks 
  } = useTaskCorrelation();
  
  const [newLinkUrl, setNewLinkUrl] = useState('');
  const [newLinkType, setNewLinkType] = useState<string>('file');

  useEffect(() => {
    if (task?.key) {
      fetchLinks(task.key);
    }
  }, [task?.key, fetchLinks]);

  const handleAnalyze = () => {
    if (!task) return;
    analyzeTask(task.key, task.title, task.description || '');
  };

  const handleAddLink = () => {
    if (!newLinkUrl || !task) return;
    
    linkItems(
      task.key,
      [{
        type: newLinkType as any,
        id: newLinkUrl,
        url: newLinkUrl,
        title: newLinkUrl.split('/').pop() || newLinkUrl
      }],
      task.title,
      task.description
    );
    
    setNewLinkUrl('');
  };

  const handleLinkSuggested = (file: string) => {
    if (!task) return;
    linkItems(
      task.key,
      [{
        type: 'file',
        id: file,
        title: file.split('/').pop() || file
      }],
      task.title,
      task.description
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Link2 className="h-4 w-4 text-primary" />
          <h3 className="font-medium text-sm">Task Correlations</h3>
        </div>
        <Badge variant="outline">{linkedItems.length} linked</Badge>
      </div>

      {/* AI Analysis */}
      <div className="p-3 bg-primary/5 rounded-lg border border-primary/20">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium flex items-center gap-2">
            <Sparkles className="h-4 w-4" />
            AI Analysis
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleAnalyze}
            disabled={isAnalyzing}
          >
            {isAnalyzing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              'Analyze'
            )}
          </Button>
        </div>

        {analysis && (
          <div className="space-y-3 mt-3">
            <div>
              <span className="text-xs text-muted-foreground">Suggested Files</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {analysis.suggestedFiles?.map((file) => (
                  <Badge 
                    key={file} 
                    variant="secondary" 
                    className="text-xs cursor-pointer hover:bg-primary/20"
                    onClick={() => handleLinkSuggested(file)}
                  >
                    <Plus className="h-3 w-3 mr-1" />
                    {file.split('/').pop()}
                  </Badge>
                ))}
              </div>
            </div>

            <div>
              <span className="text-xs text-muted-foreground">Keywords</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {analysis.keywords?.map((keyword) => (
                  <Badge key={keyword} variant="outline" className="text-xs">
                    {keyword}
                  </Badge>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-4 text-xs">
              <span className="text-muted-foreground">
                Complexity: <span className={cn(
                  'font-medium',
                  analysis.complexity === 'low' && 'text-green-500',
                  analysis.complexity === 'medium' && 'text-yellow-500',
                  analysis.complexity === 'high' && 'text-red-500'
                )}>{analysis.complexity}</span>
              </span>
              <span className="text-muted-foreground">
                Est. Files: <span className="font-medium text-foreground">{analysis.estimatedFiles}</span>
              </span>
            </div>

            {analysis.suggestedBranchName && (
              <div className="text-xs">
                <span className="text-muted-foreground">Suggested Branch: </span>
                <code className="bg-secondary px-1 rounded">{analysis.suggestedBranchName}</code>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Linked Items */}
      <ScrollArea className="h-[200px]">
        <div className="space-y-2">
          {linkedItems.map((item, index) => {
            const Icon = typeIcons[item.type] || FileCode;
            return (
              <div 
                key={`${item.type}-${item.id}-${index}`}
                className="flex items-center justify-between p-2 rounded-lg border border-border hover:bg-secondary/30 transition-colors"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <Icon className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm truncate">{item.title || item.id}</p>
                    <Badge variant="outline" className="text-[10px]">
                      {typeLabels[item.type]}
                    </Badge>
                  </div>
                </div>
                {item.url && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 flex-shrink-0"
                    onClick={() => window.open(item.url, '_blank')}
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                  </Button>
                )}
              </div>
            );
          })}

          {linkedItems.length === 0 && (
            <div className="text-center py-6 text-muted-foreground">
              <Link2 className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No linked items yet</p>
              <p className="text-xs">Use AI analysis or add links manually</p>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Add Manual Link */}
      <div className="flex gap-2">
        <select
          value={newLinkType}
          onChange={(e) => setNewLinkType(e.target.value)}
          className="h-9 rounded-md border border-input bg-background px-2 text-sm"
        >
          {Object.entries(typeLabels).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <Input
          placeholder="URL or file path..."
          value={newLinkUrl}
          onChange={(e) => setNewLinkUrl(e.target.value)}
          className="flex-1"
          onKeyDown={(e) => e.key === 'Enter' && handleAddLink()}
        />
        <Button size="icon" onClick={handleAddLink} disabled={!newLinkUrl}>
          <Plus className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
