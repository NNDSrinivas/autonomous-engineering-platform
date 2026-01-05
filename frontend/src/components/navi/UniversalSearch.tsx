import { useState } from 'react';
import { 
  Search, 
  FileText, 
  MessageSquare, 
  Video, 
  GitBranch, 
  LayoutGrid,
  ExternalLink,
  Filter,
  Clock,
  User,
  ChevronDown,
  Sparkles,
  X,
  Code,
  File
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuTrigger,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';

interface SearchResult {
  id: string;
  type: 'jira' | 'slack' | 'teams' | 'confluence' | 'github' | 'meeting' | 'code';
  title: string;
  snippet: string;
  url: string;
  source: string;
  timestamp: Date;
  relevance: number;
  metadata?: {
    author?: string;
    status?: string;
    channel?: string;
    file?: string;
    line?: number;
  };
}

const mockResults: SearchResult[] = [
  {
    id: '1',
    type: 'jira',
    title: 'AEP-142: Add workspace-aware agent loop',
    snippet: 'Implement the core agent loop that maintains awareness of the entire workspace context including files, git history, and project structure.',
    url: '#',
    source: 'Jira',
    timestamp: new Date(Date.now() - 86400000),
    relevance: 0.98,
    metadata: { status: 'In Progress' },
  },
  {
    id: '2',
    type: 'confluence',
    title: 'Agent Architecture Design Document',
    snippet: 'The agent loop follows an event-driven architecture with a sliding window context manager that caps memory usage at 500MB...',
    url: '#',
    source: 'Confluence',
    timestamp: new Date(Date.now() - 172800000),
    relevance: 0.95,
    metadata: { author: 'John Doe' },
  },
  {
    id: '3',
    type: 'slack',
    title: '#engineering - Discussion on context retention',
    snippet: '@sarah mentioned that we should use a sliding window approach for the context manager to avoid memory issues...',
    url: '#',
    source: 'Slack',
    timestamp: new Date(Date.now() - 259200000),
    relevance: 0.92,
    metadata: { channel: '#engineering', author: 'Mike Wilson' },
  },
  {
    id: '4',
    type: 'code',
    title: 'src/agent/context.ts',
    snippet: 'export class ContextManager {\n  private memory: MemoryStore;\n  private maxSize = 500 * 1024 * 1024; // 500MB',
    url: '#',
    source: 'GitHub',
    timestamp: new Date(Date.now() - 3600000),
    relevance: 0.90,
    metadata: { file: 'src/agent/context.ts', line: 42 },
  },
  {
    id: '5',
    type: 'meeting',
    title: 'Sprint Planning - NAVI Core',
    snippet: 'Discussed the workspace-aware agent implementation. Agreed on event-driven approach. Action items: Create PR for file watcher...',
    url: '#',
    source: 'Zoom',
    timestamp: new Date(Date.now() - 432000000),
    relevance: 0.88,
  },
  {
    id: '6',
    type: 'github',
    title: 'PR #142: feat: Add workspace context manager',
    snippet: 'This PR implements the core workspace context manager with file watching, git integration, and memory management.',
    url: '#',
    source: 'GitHub',
    timestamp: new Date(Date.now() - 518400000),
    relevance: 0.85,
    metadata: { status: 'Open', author: 'johndoe' },
  },
  {
    id: '7',
    type: 'teams',
    title: 'Architecture Review Thread',
    snippet: 'The memory footprint should be capped at 500MB to ensure we don\'t run into issues with larger workspaces...',
    url: '#',
    source: 'Teams',
    timestamp: new Date(Date.now() - 604800000),
    relevance: 0.82,
    metadata: { author: 'Alex Kumar' },
  },
];

const getTypeIcon = (type: string) => {
  switch (type) {
    case 'jira': return <LayoutGrid className="h-4 w-4 text-blue-400" />;
    case 'slack': return <MessageSquare className="h-4 w-4 text-purple-400" />;
    case 'teams': return <MessageSquare className="h-4 w-4 text-violet-400" />;
    case 'confluence': return <FileText className="h-4 w-4 text-blue-300" />;
    case 'github': return <GitBranch className="h-4 w-4 text-green-400" />;
    case 'meeting': return <Video className="h-4 w-4 text-sky-400" />;
    case 'code': return <Code className="h-4 w-4 text-syntax-function" />;
    default: return <File className="h-4 w-4 text-muted-foreground" />;
  }
};

const getSourceBadge = (source: string) => {
  const colors: Record<string, string> = {
    'Slack': 'bg-purple-500/10 text-purple-400 border-purple-500/30',
    'Teams': 'bg-violet-500/10 text-violet-400 border-violet-500/30',
    'GitHub': 'bg-green-500/10 text-green-400 border-green-500/30',
    'Jira': 'bg-blue-500/10 text-blue-400 border-blue-500/30',
    'Confluence': 'bg-blue-500/10 text-blue-300 border-blue-300/30',
    'Zoom': 'bg-sky-500/10 text-sky-400 border-sky-500/30',
  };
  return colors[source] || 'bg-muted text-muted-foreground';
};

const formatDate = (date: Date) => {
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const days = Math.floor(diff / 86400000);
  
  if (days === 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days} days ago`;
  return date.toLocaleDateString();
};

export function UniversalSearch() {
  const [query, setQuery] = useState('workspace context');
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState<SearchResult[]>(mockResults);
  const [filters, setFilters] = useState({
    jira: true,
    slack: true,
    teams: true,
    confluence: true,
    github: true,
    meetings: true,
    code: true,
  });

  const handleSearch = () => {
    setIsSearching(true);
    // Simulate search
    setTimeout(() => {
      setIsSearching(false);
    }, 500);
  };

  const filteredResults = results.filter(r => {
    if (r.type === 'jira' && !filters.jira) return false;
    if (r.type === 'slack' && !filters.slack) return false;
    if (r.type === 'teams' && !filters.teams) return false;
    if (r.type === 'confluence' && !filters.confluence) return false;
    if ((r.type === 'github' || r.type === 'code') && !filters.github) return false;
    if (r.type === 'meeting' && !filters.meetings) return false;
    return true;
  });

  return (
    <div className="flex-1 flex flex-col h-full bg-panel-content">
      {/* Header */}
      <div className="px-6 py-4 border-b border-border bg-panel-header">
        <div className="flex items-center gap-3 mb-4">
          <div className="h-10 w-10 rounded-xl bg-primary/10 flex items-center justify-center">
            <Search className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h2 className="font-semibold">Universal Search</h2>
            <p className="text-xs text-muted-foreground">Search across all your connected tools</p>
          </div>
        </div>

        {/* Search Bar */}
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Search Jira, Slack, Confluence, GitHub, meetings..."
              className="h-11 pl-10 pr-10 bg-input text-sm"
            />
            {query && (
              <Button
                variant="ghost"
                size="icon"
                className="absolute right-2 top-1/2 -translate-y-1/2 h-6 w-6"
                onClick={() => setQuery('')}
              >
                <X className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" className="gap-2">
                <Filter className="h-4 w-4" />
                Filters
                <ChevronDown className="h-3 w-3" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuLabel className="text-xs">Sources</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuCheckboxItem
                checked={filters.jira}
                onCheckedChange={(c) => setFilters({ ...filters, jira: c })}
              >
                <LayoutGrid className="h-4 w-4 mr-2 text-blue-400" />
                Jira
              </DropdownMenuCheckboxItem>
              <DropdownMenuCheckboxItem
                checked={filters.slack}
                onCheckedChange={(c) => setFilters({ ...filters, slack: c })}
              >
                <MessageSquare className="h-4 w-4 mr-2 text-purple-400" />
                Slack
              </DropdownMenuCheckboxItem>
              <DropdownMenuCheckboxItem
                checked={filters.teams}
                onCheckedChange={(c) => setFilters({ ...filters, teams: c })}
              >
                <MessageSquare className="h-4 w-4 mr-2 text-violet-400" />
                Teams
              </DropdownMenuCheckboxItem>
              <DropdownMenuCheckboxItem
                checked={filters.confluence}
                onCheckedChange={(c) => setFilters({ ...filters, confluence: c })}
              >
                <FileText className="h-4 w-4 mr-2 text-blue-300" />
                Confluence
              </DropdownMenuCheckboxItem>
              <DropdownMenuCheckboxItem
                checked={filters.github}
                onCheckedChange={(c) => setFilters({ ...filters, github: c })}
              >
                <GitBranch className="h-4 w-4 mr-2 text-green-400" />
                GitHub
              </DropdownMenuCheckboxItem>
              <DropdownMenuCheckboxItem
                checked={filters.meetings}
                onCheckedChange={(c) => setFilters({ ...filters, meetings: c })}
              >
                <Video className="h-4 w-4 mr-2 text-sky-400" />
                Meetings
              </DropdownMenuCheckboxItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button variant="ai" onClick={handleSearch} disabled={isSearching}>
            {isSearching ? (
              <span className="flex items-center gap-2">
                <span className="w-4 h-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
                Searching
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <Sparkles className="h-4 w-4" />
                AI Search
              </span>
            )}
          </Button>
        </div>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto">
        {/* Results Header */}
        <div className="px-6 py-3 border-b border-border bg-card/50">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">
              Found <span className="text-foreground font-medium">{filteredResults.length}</span> results for "{query}"
            </span>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Clock className="h-3 w-3" />
              <span>Sorted by relevance</span>
            </div>
          </div>
        </div>

        {/* Results List */}
        {filteredResults.map((result) => (
          <a
            key={result.id}
            href={result.url}
            className="block px-6 py-4 border-b border-border hover:bg-card/50 transition-colors group"
          >
            <div className="flex gap-4">
              <div className="flex-shrink-0 mt-1">
                {getTypeIcon(result.type)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2 mb-1">
                  <h3 className="text-sm font-medium group-hover:text-primary transition-colors">
                    {result.title}
                  </h3>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <Badge variant="outline" className={cn("text-[10px]", getSourceBadge(result.source))}>
                      {result.source}
                    </Badge>
                    <ExternalLink className="h-3.5 w-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                </div>
                <p className="text-xs text-muted-foreground mb-2 line-clamp-2">
                  {result.snippet}
                </p>
                <div className="flex items-center gap-4 text-[10px] text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {formatDate(result.timestamp)}
                  </span>
                  {result.metadata?.author && (
                    <span className="flex items-center gap-1">
                      <User className="h-3 w-3" />
                      {result.metadata.author}
                    </span>
                  )}
                  {result.metadata?.status && (
                    <Badge variant="outline" className="text-[10px]">
                      {result.metadata.status}
                    </Badge>
                  )}
                  {result.metadata?.file && (
                    <span className="font-mono">
                      {result.metadata.file}:{result.metadata.line}
                    </span>
                  )}
                  <span className="ml-auto text-primary">
                    {Math.round(result.relevance * 100)}% match
                  </span>
                </div>
              </div>
            </div>
          </a>
        ))}
      </div>

      {/* Footer */}
      <div className="px-6 py-3 border-t border-border bg-panel-header">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Searched across 7 integrations</span>
          <span className="flex items-center gap-1">
            <Sparkles className="h-3 w-3 text-primary" />
            Powered by NAVI AI
          </span>
        </div>
      </div>
    </div>
  );
}
