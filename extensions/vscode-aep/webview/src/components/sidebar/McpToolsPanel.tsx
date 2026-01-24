import React, { useState, useEffect, useCallback } from 'react';
import { naviClient, McpExecutionResult } from '../../api/navi/client';

// Premium gradient icons with animation support
const ToolsIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
    <defs>
      <linearGradient id="mcpToolsGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#00d4ff" />
        <stop offset="100%" stopColor="#7c3aed" />
      </linearGradient>
    </defs>
    <path
      d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"
      stroke="url(#mcpToolsGrad)"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const CloseIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M18 6L6 18M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const SearchIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="11" cy="11" r="8" />
    <path d="M21 21l-4.35-4.35" />
  </svg>
);

const ChevronIcon = ({ expanded }: { expanded: boolean }) => (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    style={{
      transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
      transition: 'transform 0.2s ease'
    }}
  >
    <path d="M6 9l6 6 6-6" />
  </svg>
);

const PlayIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
    <path d="M8 5v14l11-7z" />
  </svg>
);

const CopyIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="9" y="9" width="13" height="13" rx="2" />
    <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
  </svg>
);

const PlusIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="12" r="10" />
    <path d="M12 8v8M8 12h8" />
  </svg>
);

// Category icons with gradients
const GitIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <defs>
      <linearGradient id="gitGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#f97316" />
        <stop offset="100%" stopColor="#ef4444" />
      </linearGradient>
    </defs>
    <circle cx="6" cy="6" r="3" stroke="url(#gitGrad)" strokeWidth="2" />
    <circle cx="18" cy="18" r="3" stroke="url(#gitGrad)" strokeWidth="2" />
    <circle cx="18" cy="6" r="3" stroke="url(#gitGrad)" strokeWidth="2" />
    <path d="M6 9v3c0 1.1.9 2 2 2h4" stroke="url(#gitGrad)" strokeWidth="2" />
    <path d="M18 9v6" stroke="url(#gitGrad)" strokeWidth="2" />
  </svg>
);

const DatabaseIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <defs>
      <linearGradient id="dbGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#10b981" />
        <stop offset="100%" stopColor="#06b6d4" />
      </linearGradient>
    </defs>
    <ellipse cx="12" cy="5" rx="9" ry="3" stroke="url(#dbGrad)" strokeWidth="2" />
    <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" stroke="url(#dbGrad)" strokeWidth="2" />
    <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" stroke="url(#dbGrad)" strokeWidth="2" />
  </svg>
);

const BugIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <defs>
      <linearGradient id="bugGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#8b5cf6" />
        <stop offset="100%" stopColor="#ec4899" />
      </linearGradient>
    </defs>
    <path d="M8 2l1.5 1.5" stroke="url(#bugGrad)" strokeWidth="2" strokeLinecap="round" />
    <path d="M16 2l-1.5 1.5" stroke="url(#bugGrad)" strokeWidth="2" strokeLinecap="round" />
    <path d="M9 9.5a3 3 0 006 0" stroke="url(#bugGrad)" strokeWidth="2" />
    <path d="M12 9.5V16" stroke="url(#bugGrad)" strokeWidth="2" strokeLinecap="round" />
    <rect x="7" y="9" width="10" height="13" rx="5" stroke="url(#bugGrad)" strokeWidth="2" />
    <path d="M2 13h5M17 13h5M2 17h5M17 17h5" stroke="url(#bugGrad)" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

const FileIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <defs>
      <linearGradient id="fileGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#f59e0b" />
        <stop offset="100%" stopColor="#eab308" />
      </linearGradient>
    </defs>
    <path d="M14.5 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V7.5L14.5 2z" stroke="url(#fileGrad)" strokeWidth="2" />
    <polyline points="14 2 14 8 20 8" stroke="url(#fileGrad)" strokeWidth="2" />
  </svg>
);

const TestIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <defs>
      <linearGradient id="testGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#22c55e" />
        <stop offset="100%" stopColor="#10b981" />
      </linearGradient>
    </defs>
    <path d="M9 11l3 3L22 4" stroke="url(#testGrad)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" stroke="url(#testGrad)" strokeWidth="2" />
  </svg>
);

const AnalysisIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <defs>
      <linearGradient id="analysisGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#3b82f6" />
        <stop offset="100%" stopColor="#8b5cf6" />
      </linearGradient>
    </defs>
    <path d="M21 21H4.6c-.6 0-.9-.4-.9-.9V3" stroke="url(#analysisGrad)" strokeWidth="2" strokeLinecap="round" />
    <path d="M7 14l4-4 4 4 6-6" stroke="url(#analysisGrad)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

interface McpToolProperty {
  type?: string;
  description?: string;
  enum?: string[];
  default?: unknown;
  [key: string]: unknown;
}

interface McpTool {
  name: string;
  description: string;
  inputSchema: {
    type: string;
    properties: Record<string, McpToolProperty>;
    required: string[];
  };
  metadata: {
    category: string;
    requires_approval: boolean;
  };
}

interface McpToolsPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onExecuteTool: (toolName: string, args: Record<string, unknown>) => Promise<void>;
}

const categoryConfig: Record<string, { label: string; icon: React.ReactNode; description: string }> = {
  git_operations: { label: 'Git Operations', icon: <GitIcon />, description: 'Branch, merge, rebase, stash' },
  database_operations: { label: 'Database', icon: <DatabaseIcon />, description: 'Schema, migrations, queries' },
  code_debugging: { label: 'Debugging', icon: <BugIcon />, description: 'Error analysis, performance' },
  file_operations: { label: 'File Operations', icon: <FileIcon />, description: 'Read, write, search files' },
  test_execution: { label: 'Testing', icon: <TestIcon />, description: 'Run tests, coverage' },
  code_analysis: { label: 'Analysis', icon: <AnalysisIcon />, description: 'Complexity, dependencies' },
};

// Custom MCP Server interface
interface CustomMcpServer {
  id: string;
  name: string;
  url: string;
  transport: 'http' | 'websocket' | 'stdio';
  apiKey?: string;
  enabled: boolean;
  status: 'connected' | 'disconnected' | 'error';
  toolCount?: number;
}

export const McpToolsPanel: React.FC<McpToolsPanelProps> = ({
  isOpen,
  onClose,
  onExecuteTool,
}) => {
  const [tools, setTools] = useState<McpTool[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedTool, setSelectedTool] = useState<McpTool | null>(null);
  const [toolArgs, setToolArgs] = useState<Record<string, unknown>>({});
  const [executionResult, setExecutionResult] = useState<McpExecutionResult | null>(null);
  const [executing, setExecuting] = useState(false);
  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>({});
  const [searchQuery, setSearchQuery] = useState('');

  // Custom MCP Server state
  const [showAddServerModal, setShowAddServerModal] = useState(false);
  const [customServers, setCustomServers] = useState<CustomMcpServer[]>([]);
  const [newServer, setNewServer] = useState<Partial<CustomMcpServer>>({
    name: '',
    url: '',
    transport: 'http',
    apiKey: '',
    enabled: true,
  });
  const [addingServer, setAddingServer] = useState(false);

  const fetchTools = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await naviClient.listMcpTools();
      const fetchedTools = response.tools as unknown as McpTool[];
      setTools(fetchedTools);
      if (fetchedTools.length > 0) {
        const firstCategory = fetchedTools[0].metadata.category;
        setExpandedCategories({ [firstCategory]: true });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load MCP tools');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen && tools.length === 0) {
      fetchTools();
    }
  }, [isOpen, fetchTools, tools.length]);

  const filteredTools = tools.filter(tool =>
    tool.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    tool.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const toolsByCategory = filteredTools.reduce((acc, tool) => {
    const category = tool.metadata.category;
    if (!acc[category]) acc[category] = [];
    acc[category].push(tool);
    return acc;
  }, {} as Record<string, McpTool[]>);

  const toggleCategory = (category: string) => {
    setExpandedCategories(prev => ({ ...prev, [category]: !prev[category] }));
  };

  const handleSelectTool = (tool: McpTool) => {
    setSelectedTool(tool);
    setExecutionResult(null);
    const initialArgs: Record<string, unknown> = {};
    Object.entries(tool.inputSchema.properties).forEach(([key, prop]) => {
      if (prop.default !== undefined) {
        initialArgs[key] = prop.default;
      }
    });
    setToolArgs(initialArgs);
  };

  const handleArgChange = (key: string, value: unknown) => {
    setToolArgs(prev => ({ ...prev, [key]: value }));
  };

  const handleExecute = async () => {
    if (!selectedTool) return;
    setExecuting(true);
    setExecutionResult(null);
    try {
      const result = await naviClient.executeMcpTool(selectedTool.name, toolArgs, true);
      setExecutionResult(result);
      await onExecuteTool(selectedTool.name, toolArgs);
    } catch (err) {
      setExecutionResult({
        success: false,
        data: null,
        error: err instanceof Error ? err.message : 'Execution failed',
        metadata: {},
      });
    } finally {
      setExecuting(false);
    }
  };

  const copyResult = () => {
    if (executionResult) {
      navigator.clipboard.writeText(JSON.stringify(executionResult.data, null, 2));
    }
  };

  // Custom MCP Server handlers
  const handleAddServer = async () => {
    if (!newServer.name || !newServer.url) return;

    setAddingServer(true);

    // Simulate server connection test
    await new Promise(resolve => setTimeout(resolve, 1500));

    const server: CustomMcpServer = {
      id: `custom-${Date.now()}`,
      name: newServer.name,
      url: newServer.url,
      transport: newServer.transport || 'http',
      apiKey: newServer.apiKey,
      enabled: true,
      status: 'connected',
      toolCount: Math.floor(Math.random() * 10) + 1, // Simulated
    };

    setCustomServers(prev => [...prev, server]);
    setNewServer({ name: '', url: '', transport: 'http', apiKey: '', enabled: true });
    setShowAddServerModal(false);
    setAddingServer(false);
  };

  const handleRemoveServer = (serverId: string) => {
    setCustomServers(prev => prev.filter(s => s.id !== serverId));
  };

  const handleToggleServer = (serverId: string) => {
    setCustomServers(prev =>
      prev.map(s =>
        s.id === serverId
          ? { ...s, enabled: !s.enabled, status: s.enabled ? 'disconnected' : 'connected' }
          : s
      )
    );
  };

  if (!isOpen) return null;

  const totalTools = tools.length;

  return (
    <div className="mcp-overlay" onClick={onClose}>
      <div className="mcp-panel" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="mcp-header">
          <div className="mcp-header__left">
            <div className="mcp-header__icon">
              <ToolsIcon />
            </div>
            <div className="mcp-header__title">
              <h2>MCP Tools</h2>
              <span className="mcp-header__subtitle">Model Context Protocol</span>
            </div>
          </div>
          <div className="mcp-header__right">
            <span className="mcp-header__count">{totalTools} tools</span>
            <button className="mcp-close" onClick={onClose}>
              <CloseIcon />
            </button>
          </div>
        </div>

        {/* Search */}
        <div className="mcp-search">
          <div className="mcp-search__input-wrapper">
            <SearchIcon />
            <input
              type="text"
              placeholder="Search tools..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="mcp-search__input"
            />
          </div>
        </div>

        {/* Content */}
        <div className="mcp-content">
          {loading && (
            <div className="mcp-loading">
              <div className="mcp-loading__spinner" />
              <span>Loading tools...</span>
            </div>
          )}

          {error && (
            <div className="mcp-error">
              <div className="mcp-error__icon">!</div>
              <p>API request failed: 404 {error}</p>
              <button className="mcp-error__retry" onClick={fetchTools}>Retry</button>
            </div>
          )}

          {!loading && !error && (
            <div className="mcp-body">
              {/* Categories List */}
              <div className="mcp-categories">
                {Object.entries(toolsByCategory).map(([category, categoryTools]) => {
                  const config = categoryConfig[category] || { label: category, icon: <ToolsIcon />, description: '' };
                  const isExpanded = expandedCategories[category];

                  return (
                    <div key={category} className={`mcp-category ${isExpanded ? 'mcp-category--expanded' : ''}`}>
                      <button className="mcp-category__header" onClick={() => toggleCategory(category)}>
                        <div className="mcp-category__icon-wrapper">
                          {config.icon}
                        </div>
                        <div className="mcp-category__info">
                          <span className="mcp-category__name">{config.label}</span>
                          <span className="mcp-category__desc">{config.description}</span>
                        </div>
                        <div className="mcp-category__meta">
                          <span className="mcp-category__count">{categoryTools.length}</span>
                          <ChevronIcon expanded={isExpanded} />
                        </div>
                      </button>

                      {isExpanded && (
                        <div className="mcp-category__tools">
                          {categoryTools.map((tool) => (
                            <button
                              key={tool.name}
                              className={`mcp-tool-item ${selectedTool?.name === tool.name ? 'mcp-tool-item--selected' : ''}`}
                              onClick={() => handleSelectTool(tool)}
                            >
                              <div className="mcp-tool-item__content">
                                <span className="mcp-tool-item__name">
                                  {tool.name.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
                                </span>
                                {tool.metadata.requires_approval && (
                                  <span className="mcp-tool-item__badge">Approval</span>
                                )}
                              </div>
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mcp-tool-item__arrow">
                                <path d="M9 18l6-6-6-6" />
                              </svg>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Selected Tool Panel */}
              {selectedTool && (
                <div className="mcp-tool-detail">
                  <div className="mcp-tool-detail__header">
                    <h3>{selectedTool.name.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}</h3>
                    {selectedTool.metadata.requires_approval && (
                      <span className="mcp-tool-detail__badge">Requires Approval</span>
                    )}
                  </div>
                  <p className="mcp-tool-detail__desc">{selectedTool.description}</p>

                  {/* Parameters */}
                  <div className="mcp-params">
                    <h4>Parameters</h4>
                    {Object.entries(selectedTool.inputSchema.properties).map(([key, prop]) => (
                      <div key={key} className="mcp-param">
                        <label className="mcp-param__label">
                          {key}
                          {selectedTool.inputSchema.required.includes(key) && (
                            <span className="mcp-param__required">*</span>
                          )}
                        </label>
                        {prop.enum ? (
                          <select
                            className="mcp-param__input mcp-param__select"
                            value={String(toolArgs[key] || '')}
                            onChange={(e) => handleArgChange(key, e.target.value)}
                          >
                            <option value="">Select...</option>
                            {prop.enum.map((opt) => (
                              <option key={opt} value={opt}>{opt}</option>
                            ))}
                          </select>
                        ) : prop.type === 'boolean' ? (
                          <select
                            className="mcp-param__input mcp-param__select"
                            value={String(toolArgs[key] || false)}
                            onChange={(e) => handleArgChange(key, e.target.value === 'true')}
                          >
                            <option value="false">false</option>
                            <option value="true">true</option>
                          </select>
                        ) : (
                          <input
                            type={prop.type === 'number' ? 'number' : 'text'}
                            className="mcp-param__input"
                            value={String(toolArgs[key] || '')}
                            onChange={(e) => handleArgChange(key, prop.type === 'number' ? Number(e.target.value) : e.target.value)}
                            placeholder={prop.description}
                          />
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Execute Button */}
                  <button
                    className={`mcp-execute ${executing ? 'mcp-execute--loading' : ''}`}
                    onClick={handleExecute}
                    disabled={executing}
                  >
                    {executing ? (
                      <>
                        <div className="mcp-execute__spinner" />
                        Executing...
                      </>
                    ) : (
                      <>
                        <PlayIcon />
                        Execute Tool
                      </>
                    )}
                  </button>

                  {/* Result */}
                  {executionResult && (
                    <div className={`mcp-result ${executionResult.success ? 'mcp-result--success' : 'mcp-result--error'}`}>
                      <div className="mcp-result__header">
                        <span className="mcp-result__status">
                          {executionResult.success ? 'Success' : 'Error'}
                        </span>
                        <button className="mcp-result__copy" onClick={copyResult} title="Copy">
                          <CopyIcon />
                        </button>
                      </div>
                      <pre className="mcp-result__output">
                        {executionResult.error || JSON.stringify(executionResult.data, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )}

              {/* Custom Servers Section */}
              {customServers.length > 0 && (
                <div className="mcp-custom-servers">
                  <h4 className="mcp-custom-servers__title">Custom Servers</h4>
                  <div className="mcp-custom-servers__list">
                    {customServers.map((server) => (
                      <div key={server.id} className={`mcp-server-card ${!server.enabled ? 'mcp-server-card--disabled' : ''}`}>
                        <div className="mcp-server-card__header">
                          <div className={`mcp-server-card__status mcp-server-card__status--${server.status}`} />
                          <span className="mcp-server-card__name">{server.name}</span>
                          <span className="mcp-server-card__transport">{server.transport.toUpperCase()}</span>
                        </div>
                        <div className="mcp-server-card__url">{server.url}</div>
                        <div className="mcp-server-card__footer">
                          <span className="mcp-server-card__tools">{server.toolCount} tools</span>
                          <div className="mcp-server-card__actions">
                            <button
                              className="mcp-server-card__btn"
                              onClick={() => handleToggleServer(server.id)}
                              title={server.enabled ? 'Disable' : 'Enable'}
                            >
                              {server.enabled ? (
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                  <rect x="1" y="5" width="22" height="14" rx="7" ry="7" />
                                  <circle cx="16" cy="12" r="3" fill="currentColor" />
                                </svg>
                              ) : (
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                  <rect x="1" y="5" width="22" height="14" rx="7" ry="7" />
                                  <circle cx="8" cy="12" r="3" />
                                </svg>
                              )}
                            </button>
                            <button
                              className="mcp-server-card__btn mcp-server-card__btn--danger"
                              onClick={() => handleRemoveServer(server.id)}
                              title="Remove"
                            >
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                              </svg>
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Add Custom Server */}
              <button className="mcp-add-server" onClick={() => setShowAddServerModal(true)}>
                <PlusIcon />
                <span>Add Custom MCP Server</span>
              </button>
            </div>
          )}
        </div>

        {/* Add Server Modal */}
        {showAddServerModal && (
          <div className="mcp-modal-overlay" onClick={() => setShowAddServerModal(false)}>
            <div className="mcp-modal" onClick={e => e.stopPropagation()}>
              <div className="mcp-modal__header">
                <h3>Add Custom MCP Server</h3>
                <button className="mcp-modal__close" onClick={() => setShowAddServerModal(false)}>
                  <CloseIcon />
                </button>
              </div>
              <div className="mcp-modal__content">
                <p className="mcp-modal__description">
                  Connect to an external MCP server to extend NAVI's capabilities with custom tools.
                </p>

                <div className="mcp-modal__field">
                  <label>Server Name *</label>
                  <input
                    type="text"
                    placeholder="e.g., Internal Tools Server"
                    value={newServer.name}
                    onChange={(e) => setNewServer(prev => ({ ...prev, name: e.target.value }))}
                  />
                </div>

                <div className="mcp-modal__field">
                  <label>Server URL *</label>
                  <input
                    type="text"
                    placeholder="e.g., https://mcp.yourcompany.com"
                    value={newServer.url}
                    onChange={(e) => setNewServer(prev => ({ ...prev, url: e.target.value }))}
                  />
                </div>

                <div className="mcp-modal__field">
                  <label>Transport Protocol</label>
                  <select
                    value={newServer.transport}
                    onChange={(e) => setNewServer(prev => ({ ...prev, transport: e.target.value as 'http' | 'websocket' | 'stdio' }))}
                  >
                    <option value="http">HTTP</option>
                    <option value="websocket">WebSocket</option>
                    <option value="stdio">Standard I/O</option>
                  </select>
                </div>

                <div className="mcp-modal__field">
                  <label>API Key (Optional)</label>
                  <input
                    type="password"
                    placeholder="Enter API key for authentication"
                    value={newServer.apiKey}
                    onChange={(e) => setNewServer(prev => ({ ...prev, apiKey: e.target.value }))}
                  />
                </div>

                <div className="mcp-modal__info">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <path d="M12 16v-4M12 8h.01" />
                  </svg>
                  <span>
                    The server must implement the Model Context Protocol (MCP) specification.
                    <a href="https://modelcontextprotocol.io" target="_blank" rel="noopener noreferrer"> Learn more</a>
                  </span>
                </div>
              </div>
              <div className="mcp-modal__footer">
                <button className="mcp-modal__btn mcp-modal__btn--secondary" onClick={() => setShowAddServerModal(false)}>
                  Cancel
                </button>
                <button
                  className="mcp-modal__btn mcp-modal__btn--primary"
                  onClick={handleAddServer}
                  disabled={!newServer.name || !newServer.url || addingServer}
                >
                  {addingServer ? (
                    <>
                      <div className="mcp-modal__spinner" />
                      Connecting...
                    </>
                  ) : (
                    'Add Server'
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        <style>{`
          /* ============================================
             MCP TOOLS PANEL - Premium Design
             ============================================ */

          .mcp-overlay {
            position: fixed;
            inset: 0;
            background: hsl(var(--background) / 0.85);
            backdrop-filter: blur(12px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            animation: mcp-fade-in 0.2s ease;
          }

          @keyframes mcp-fade-in {
            from { opacity: 0; }
            to { opacity: 1; }
          }

          .mcp-panel {
            width: 94%;
            max-width: 720px;
            max-height: 88vh;
            background: linear-gradient(
              165deg,
              hsl(var(--card)) 0%,
              hsl(var(--background)) 100%
            );
            border: 1px solid hsl(var(--border) / 0.4);
            border-radius: 24px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            animation: mcp-slide-up 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            box-shadow:
              0 0 0 1px hsl(var(--primary) / 0.1),
              0 25px 80px -12px hsl(0 0% 0% / 0.5),
              0 0 120px hsl(var(--primary) / 0.08);
          }

          @keyframes mcp-slide-up {
            from {
              opacity: 0;
              transform: translateY(30px) scale(0.96);
            }
            to {
              opacity: 1;
              transform: translateY(0) scale(1);
            }
          }

          /* Header */
          .mcp-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 20px 24px;
            background: linear-gradient(
              180deg,
              hsl(var(--card) / 0.8) 0%,
              hsl(var(--card) / 0.4) 100%
            );
            border-bottom: 1px solid hsl(var(--border) / 0.3);
          }

          .mcp-header__left {
            display: flex;
            align-items: center;
            gap: 14px;
          }

          .mcp-header__icon {
            width: 48px;
            height: 48px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, hsl(var(--primary) / 0.15), hsl(var(--accent) / 0.15));
            border: 1px solid hsl(var(--primary) / 0.2);
            border-radius: 14px;
            box-shadow: 0 0 30px hsl(var(--primary) / 0.2);
          }

          .mcp-header__title h2 {
            margin: 0;
            font-size: 20px;
            font-weight: 700;
            color: hsl(var(--foreground));
            letter-spacing: -0.02em;
          }

          .mcp-header__subtitle {
            font-size: 12px;
            color: hsl(var(--muted-foreground));
          }

          .mcp-header__right {
            display: flex;
            align-items: center;
            gap: 16px;
          }

          .mcp-header__count {
            padding: 6px 14px;
            background: hsl(var(--secondary) / 0.4);
            border: 1px solid hsl(var(--border) / 0.3);
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            color: hsl(var(--primary));
          }

          .mcp-close {
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: hsl(var(--secondary) / 0.4);
            border: 1px solid hsl(var(--border) / 0.3);
            border-radius: 12px;
            color: hsl(var(--muted-foreground));
            cursor: pointer;
            transition: all 0.2s ease;
          }

          .mcp-close:hover {
            background: hsl(var(--destructive) / 0.15);
            border-color: hsl(var(--destructive) / 0.3);
            color: hsl(var(--destructive));
            transform: rotate(90deg);
          }

          /* Search */
          .mcp-search {
            padding: 16px 24px;
            border-bottom: 1px solid hsl(var(--border) / 0.2);
          }

          .mcp-search__input-wrapper {
            position: relative;
            display: flex;
            align-items: center;
          }

          .mcp-search__input-wrapper svg {
            position: absolute;
            left: 14px;
            color: hsl(var(--muted-foreground));
            pointer-events: none;
          }

          .mcp-search__input {
            width: 100%;
            padding: 12px 14px 12px 42px;
            background: hsl(var(--secondary) / 0.3);
            border: 1px solid hsl(var(--border) / 0.3);
            border-radius: 12px;
            font-size: 14px;
            color: hsl(var(--foreground));
            outline: none;
            transition: all 0.2s ease;
          }

          .mcp-search__input:focus {
            background: hsl(var(--secondary) / 0.5);
            border-color: hsl(var(--primary) / 0.5);
            box-shadow: 0 0 0 3px hsl(var(--primary) / 0.1);
          }

          .mcp-search__input::placeholder {
            color: hsl(var(--muted-foreground));
          }

          /* Content */
          .mcp-content {
            flex: 1;
            overflow-y: auto;
            padding: 20px 24px;
          }

          .mcp-content::-webkit-scrollbar {
            width: 6px;
          }

          .mcp-content::-webkit-scrollbar-track {
            background: transparent;
          }

          .mcp-content::-webkit-scrollbar-thumb {
            background: hsl(var(--primary) / 0.2);
            border-radius: 3px;
          }

          /* Loading */
          .mcp-loading {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 16px;
            padding: 60px 20px;
            color: hsl(var(--muted-foreground));
          }

          .mcp-loading__spinner {
            width: 36px;
            height: 36px;
            border: 3px solid hsl(var(--border));
            border-top-color: hsl(var(--primary));
            border-radius: 50%;
            animation: mcp-spin 1s linear infinite;
          }

          @keyframes mcp-spin {
            to { transform: rotate(360deg); }
          }

          /* Error */
          .mcp-error {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 16px;
            padding: 48px 24px;
            background: hsl(var(--destructive) / 0.05);
            border: 1px solid hsl(var(--destructive) / 0.2);
            border-radius: 16px;
            text-align: center;
          }

          .mcp-error__icon {
            width: 48px;
            height: 48px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: hsl(var(--destructive) / 0.15);
            border-radius: 50%;
            font-size: 24px;
            font-weight: 700;
            color: hsl(var(--destructive));
          }

          .mcp-error p {
            margin: 0;
            font-size: 14px;
            color: hsl(var(--destructive));
          }

          .mcp-error__retry {
            padding: 10px 24px;
            background: hsl(var(--secondary) / 0.5);
            border: 1px solid hsl(var(--border));
            border-radius: 10px;
            font-size: 13px;
            font-weight: 600;
            color: hsl(var(--foreground));
            cursor: pointer;
            transition: all 0.2s ease;
          }

          .mcp-error__retry:hover {
            background: hsl(var(--secondary));
            border-color: hsl(var(--primary) / 0.3);
          }

          /* Body Layout */
          .mcp-body {
            display: flex;
            flex-direction: column;
            gap: 16px;
          }

          /* Categories */
          .mcp-categories {
            display: flex;
            flex-direction: column;
            gap: 10px;
          }

          .mcp-category {
            background: hsl(var(--card) / 0.5);
            border: 1px solid hsl(var(--border) / 0.3);
            border-radius: 16px;
            overflow: hidden;
            transition: all 0.2s ease;
          }

          .mcp-category:hover {
            border-color: hsl(var(--border) / 0.5);
          }

          .mcp-category--expanded {
            background: hsl(var(--card) / 0.8);
            border-color: hsl(var(--primary) / 0.2);
          }

          .mcp-category__header {
            display: flex;
            align-items: center;
            width: 100%;
            padding: 14px 18px;
            background: transparent;
            border: none;
            cursor: pointer;
            transition: background 0.15s ease;
          }

          .mcp-category__header:hover {
            background: hsl(var(--secondary) / 0.3);
          }

          .mcp-category__icon-wrapper {
            width: 42px;
            height: 42px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: hsl(var(--secondary) / 0.5);
            border-radius: 12px;
            margin-right: 14px;
            transition: all 0.2s ease;
          }

          .mcp-category:hover .mcp-category__icon-wrapper {
            transform: scale(1.05);
          }

          .mcp-category__info {
            flex: 1;
            text-align: left;
          }

          .mcp-category__name {
            display: block;
            font-size: 14px;
            font-weight: 600;
            color: hsl(var(--foreground));
          }

          .mcp-category__desc {
            display: block;
            font-size: 11px;
            color: hsl(var(--muted-foreground));
            margin-top: 2px;
          }

          .mcp-category__meta {
            display: flex;
            align-items: center;
            gap: 10px;
          }

          .mcp-category__count {
            padding: 4px 10px;
            background: hsl(var(--secondary) / 0.5);
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            color: hsl(var(--muted-foreground));
          }

          .mcp-category--expanded .mcp-category__count {
            background: hsl(var(--primary) / 0.15);
            color: hsl(var(--primary));
          }

          /* Tool Items */
          .mcp-category__tools {
            padding: 4px 12px 12px 70px;
            display: flex;
            flex-direction: column;
            gap: 4px;
          }

          .mcp-tool-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 14px;
            background: transparent;
            border: 1px solid transparent;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.15s ease;
            text-align: left;
          }

          .mcp-tool-item:hover {
            background: hsl(var(--secondary) / 0.4);
          }

          .mcp-tool-item--selected {
            background: hsl(var(--primary) / 0.1);
            border-color: hsl(var(--primary) / 0.3);
          }

          .mcp-tool-item__content {
            display: flex;
            align-items: center;
            gap: 10px;
          }

          .mcp-tool-item__name {
            font-size: 13px;
            color: hsl(var(--foreground));
          }

          .mcp-tool-item__badge {
            padding: 2px 8px;
            background: hsl(45 93% 47% / 0.15);
            border: 1px solid hsl(45 93% 47% / 0.3);
            border-radius: 10px;
            font-size: 9px;
            font-weight: 600;
            color: hsl(45 93% 47%);
            text-transform: uppercase;
          }

          .mcp-tool-item__arrow {
            color: hsl(var(--muted-foreground));
            opacity: 0;
            transform: translateX(-4px);
            transition: all 0.15s ease;
          }

          .mcp-tool-item:hover .mcp-tool-item__arrow,
          .mcp-tool-item--selected .mcp-tool-item__arrow {
            opacity: 1;
            transform: translateX(0);
          }

          .mcp-tool-item--selected .mcp-tool-item__arrow {
            color: hsl(var(--primary));
          }

          /* Tool Detail Panel */
          .mcp-tool-detail {
            margin-top: 8px;
            padding: 20px;
            background: hsl(var(--card));
            border: 1px solid hsl(var(--border) / 0.4);
            border-radius: 16px;
          }

          .mcp-tool-detail__header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 8px;
          }

          .mcp-tool-detail__header h3 {
            margin: 0;
            font-size: 16px;
            font-weight: 700;
            color: hsl(var(--foreground));
          }

          .mcp-tool-detail__badge {
            padding: 4px 10px;
            background: hsl(45 93% 47% / 0.12);
            border: 1px solid hsl(45 93% 47% / 0.25);
            border-radius: 10px;
            font-size: 10px;
            font-weight: 600;
            color: hsl(45 93% 47%);
          }

          .mcp-tool-detail__desc {
            margin: 0 0 20px;
            font-size: 13px;
            line-height: 1.6;
            color: hsl(var(--muted-foreground));
          }

          /* Parameters */
          .mcp-params {
            margin-bottom: 20px;
          }

          .mcp-params h4 {
            margin: 0 0 12px;
            font-size: 12px;
            font-weight: 600;
            color: hsl(var(--muted-foreground));
            text-transform: uppercase;
            letter-spacing: 0.05em;
          }

          .mcp-param {
            margin-bottom: 14px;
          }

          .mcp-param:last-child {
            margin-bottom: 0;
          }

          .mcp-param__label {
            display: block;
            margin-bottom: 6px;
            font-size: 13px;
            font-weight: 500;
            color: hsl(var(--foreground));
          }

          .mcp-param__required {
            color: hsl(var(--destructive));
            margin-left: 2px;
          }

          .mcp-param__input {
            width: 100%;
            padding: 10px 14px;
            background: hsl(var(--secondary) / 0.3);
            border: 1px solid hsl(var(--border) / 0.4);
            border-radius: 10px;
            font-size: 13px;
            color: hsl(var(--foreground));
            outline: none;
            transition: all 0.2s ease;
          }

          .mcp-param__input:focus {
            background: hsl(var(--secondary) / 0.5);
            border-color: hsl(var(--primary) / 0.5);
            box-shadow: 0 0 0 3px hsl(var(--primary) / 0.1);
          }

          .mcp-param__input::placeholder {
            color: hsl(var(--muted-foreground) / 0.7);
          }

          .mcp-param__select {
            cursor: pointer;
          }

          /* Execute Button */
          .mcp-execute {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            width: 100%;
            padding: 14px 20px;
            background: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)));
            border: none;
            border-radius: 12px;
            font-size: 14px;
            font-weight: 600;
            color: white;
            cursor: pointer;
            transition: all 0.2s ease;
          }

          .mcp-execute:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 8px 30px hsl(var(--primary) / 0.4);
          }

          .mcp-execute:disabled {
            opacity: 0.7;
            cursor: not-allowed;
          }

          .mcp-execute__spinner {
            width: 16px;
            height: 16px;
            border: 2px solid rgba(255,255,255,0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: mcp-spin 0.8s linear infinite;
          }

          /* Result */
          .mcp-result {
            margin-top: 16px;
            border-radius: 12px;
            overflow: hidden;
          }

          .mcp-result--success {
            background: hsl(142 76% 36% / 0.08);
            border: 1px solid hsl(142 76% 36% / 0.2);
          }

          .mcp-result--error {
            background: hsl(var(--destructive) / 0.08);
            border: 1px solid hsl(var(--destructive) / 0.2);
          }

          .mcp-result__header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 14px;
            background: hsl(0 0% 0% / 0.1);
          }

          .mcp-result__status {
            font-size: 12px;
            font-weight: 600;
          }

          .mcp-result--success .mcp-result__status {
            color: hsl(142 76% 46%);
          }

          .mcp-result--error .mcp-result__status {
            color: hsl(var(--destructive));
          }

          .mcp-result__copy {
            padding: 6px;
            background: hsl(var(--secondary) / 0.5);
            border: none;
            border-radius: 6px;
            color: hsl(var(--muted-foreground));
            cursor: pointer;
            transition: all 0.15s ease;
          }

          .mcp-result__copy:hover {
            background: hsl(var(--secondary));
            color: hsl(var(--foreground));
          }

          .mcp-result__output {
            margin: 0;
            padding: 14px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            line-height: 1.5;
            color: hsl(var(--foreground));
            max-height: 200px;
            overflow: auto;
            white-space: pre-wrap;
            word-break: break-all;
          }

          /* Add Server Button */
          .mcp-add-server {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            width: 100%;
            padding: 14px 20px;
            background: hsl(var(--secondary) / 0.3);
            border: 2px dashed hsl(var(--border) / 0.5);
            border-radius: 14px;
            font-size: 14px;
            font-weight: 500;
            color: hsl(var(--muted-foreground));
            cursor: pointer;
            transition: all 0.2s ease;
          }

          .mcp-add-server:hover {
            background: hsl(var(--secondary) / 0.5);
            border-color: hsl(var(--primary) / 0.4);
            color: hsl(var(--primary));
          }

          .mcp-add-server svg {
            transition: transform 0.2s ease;
          }

          .mcp-add-server:hover svg {
            transform: rotate(90deg);
          }

          /* ============================================
             CUSTOM SERVERS SECTION
             ============================================ */

          .mcp-custom-servers {
            margin-top: 8px;
            margin-bottom: 16px;
          }

          .mcp-custom-servers__title {
            margin: 0 0 12px;
            font-size: 12px;
            font-weight: 600;
            color: hsl(var(--muted-foreground));
            text-transform: uppercase;
            letter-spacing: 0.05em;
          }

          .mcp-custom-servers__list {
            display: flex;
            flex-direction: column;
            gap: 10px;
          }

          .mcp-server-card {
            padding: 14px 16px;
            background: linear-gradient(
              135deg,
              hsl(var(--card) / 0.8) 0%,
              hsl(var(--secondary) / 0.3) 100%
            );
            border: 1px solid hsl(var(--border) / 0.4);
            border-radius: 14px;
            transition: all 0.2s ease;
          }

          .mcp-server-card:hover {
            border-color: hsl(var(--primary) / 0.3);
            box-shadow: 0 4px 20px hsl(var(--primary) / 0.1);
          }

          .mcp-server-card--disabled {
            opacity: 0.5;
          }

          .mcp-server-card__header {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 6px;
          }

          .mcp-server-card__status {
            width: 8px;
            height: 8px;
            border-radius: 50%;
          }

          .mcp-server-card__status--connected {
            background: hsl(142 76% 46%);
            box-shadow: 0 0 8px hsl(142 76% 46% / 0.6);
          }

          .mcp-server-card__status--disconnected {
            background: hsl(var(--muted-foreground));
          }

          .mcp-server-card__status--error {
            background: hsl(var(--destructive));
            box-shadow: 0 0 8px hsl(var(--destructive) / 0.6);
          }

          .mcp-server-card__name {
            flex: 1;
            font-size: 14px;
            font-weight: 600;
            color: hsl(var(--foreground));
          }

          .mcp-server-card__transport {
            padding: 3px 8px;
            background: hsl(var(--secondary) / 0.5);
            border-radius: 6px;
            font-size: 9px;
            font-weight: 600;
            color: hsl(var(--muted-foreground));
            letter-spacing: 0.03em;
          }

          .mcp-server-card__url {
            font-size: 11px;
            color: hsl(var(--muted-foreground));
            margin-bottom: 10px;
            word-break: break-all;
          }

          .mcp-server-card__footer {
            display: flex;
            align-items: center;
            justify-content: space-between;
          }

          .mcp-server-card__tools {
            font-size: 11px;
            color: hsl(var(--primary));
          }

          .mcp-server-card__actions {
            display: flex;
            gap: 6px;
          }

          .mcp-server-card__btn {
            padding: 6px;
            background: hsl(var(--secondary) / 0.4);
            border: 1px solid hsl(var(--border) / 0.3);
            border-radius: 6px;
            color: hsl(var(--muted-foreground));
            cursor: pointer;
            transition: all 0.15s ease;
          }

          .mcp-server-card__btn:hover {
            background: hsl(var(--secondary) / 0.8);
            color: hsl(var(--foreground));
          }

          .mcp-server-card__btn--danger:hover {
            background: hsl(var(--destructive) / 0.15);
            border-color: hsl(var(--destructive) / 0.3);
            color: hsl(var(--destructive));
          }

          /* ============================================
             ADD SERVER MODAL
             ============================================ */

          .mcp-modal-overlay {
            position: fixed;
            inset: 0;
            background: hsl(0 0% 0% / 0.7);
            backdrop-filter: blur(8px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1100;
            animation: mcp-fade-in 0.15s ease;
          }

          .mcp-modal {
            width: 90%;
            max-width: 480px;
            background: linear-gradient(
              165deg,
              hsl(var(--card)) 0%,
              hsl(var(--background)) 100%
            );
            border: 1px solid hsl(var(--border) / 0.5);
            border-radius: 20px;
            overflow: hidden;
            animation: mcp-slide-up 0.25s cubic-bezier(0.16, 1, 0.3, 1);
            box-shadow:
              0 0 0 1px hsl(var(--primary) / 0.1),
              0 25px 80px -12px hsl(0 0% 0% / 0.6);
          }

          .mcp-modal__header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 18px 22px;
            background: hsl(var(--card) / 0.5);
            border-bottom: 1px solid hsl(var(--border) / 0.3);
          }

          .mcp-modal__header h3 {
            margin: 0;
            font-size: 16px;
            font-weight: 700;
            color: hsl(var(--foreground));
          }

          .mcp-modal__close {
            padding: 8px;
            background: hsl(var(--secondary) / 0.4);
            border: 1px solid hsl(var(--border) / 0.3);
            border-radius: 8px;
            color: hsl(var(--muted-foreground));
            cursor: pointer;
            transition: all 0.15s ease;
          }

          .mcp-modal__close:hover {
            background: hsl(var(--destructive) / 0.15);
            border-color: hsl(var(--destructive) / 0.3);
            color: hsl(var(--destructive));
          }

          .mcp-modal__content {
            padding: 22px;
          }

          .mcp-modal__description {
            margin: 0 0 20px;
            font-size: 13px;
            color: hsl(var(--muted-foreground));
            line-height: 1.5;
          }

          .mcp-modal__field {
            margin-bottom: 16px;
          }

          .mcp-modal__field:last-of-type {
            margin-bottom: 0;
          }

          .mcp-modal__field label {
            display: block;
            margin-bottom: 6px;
            font-size: 12px;
            font-weight: 600;
            color: hsl(var(--foreground));
          }

          .mcp-modal__field input,
          .mcp-modal__field select {
            width: 100%;
            padding: 11px 14px;
            background: hsl(var(--secondary) / 0.3);
            border: 1px solid hsl(var(--border) / 0.4);
            border-radius: 10px;
            font-size: 13px;
            color: hsl(var(--foreground));
            outline: none;
            transition: all 0.2s ease;
          }

          .mcp-modal__field input:focus,
          .mcp-modal__field select:focus {
            background: hsl(var(--secondary) / 0.5);
            border-color: hsl(var(--primary) / 0.5);
            box-shadow: 0 0 0 3px hsl(var(--primary) / 0.1);
          }

          .mcp-modal__field input::placeholder {
            color: hsl(var(--muted-foreground) / 0.7);
          }

          .mcp-modal__field select {
            cursor: pointer;
          }

          .mcp-modal__info {
            display: flex;
            align-items: flex-start;
            gap: 10px;
            margin-top: 20px;
            padding: 14px;
            background: hsl(var(--primary) / 0.08);
            border: 1px solid hsl(var(--primary) / 0.15);
            border-radius: 10px;
          }

          .mcp-modal__info svg {
            flex-shrink: 0;
            color: hsl(var(--primary));
            margin-top: 1px;
          }

          .mcp-modal__info span {
            font-size: 12px;
            color: hsl(var(--muted-foreground));
            line-height: 1.5;
          }

          .mcp-modal__info a {
            color: hsl(var(--primary));
            text-decoration: none;
          }

          .mcp-modal__info a:hover {
            text-decoration: underline;
          }

          .mcp-modal__footer {
            display: flex;
            justify-content: flex-end;
            gap: 10px;
            padding: 16px 22px;
            background: hsl(var(--card) / 0.3);
            border-top: 1px solid hsl(var(--border) / 0.3);
          }

          .mcp-modal__btn {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 11px 20px;
            font-size: 13px;
            font-weight: 600;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.2s ease;
          }

          .mcp-modal__btn--secondary {
            background: hsl(var(--secondary) / 0.5);
            border: 1px solid hsl(var(--border) / 0.5);
            color: hsl(var(--muted-foreground));
          }

          .mcp-modal__btn--secondary:hover {
            background: hsl(var(--secondary));
            color: hsl(var(--foreground));
          }

          .mcp-modal__btn--primary {
            background: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)));
            border: none;
            color: white;
          }

          .mcp-modal__btn--primary:hover:not(:disabled) {
            transform: translateY(-1px);
            box-shadow: 0 4px 20px hsl(var(--primary) / 0.4);
          }

          .mcp-modal__btn--primary:disabled {
            opacity: 0.6;
            cursor: not-allowed;
          }

          .mcp-modal__spinner {
            width: 14px;
            height: 14px;
            border: 2px solid rgba(255,255,255,0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: mcp-spin 0.8s linear infinite;
          }
        `}</style>
      </div>
    </div>
  );
};

export default McpToolsPanel;
