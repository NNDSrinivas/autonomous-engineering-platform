import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Pin,
  Star,
  Archive,
  Trash2,
  Search,
  X,
  Clock,
  MessageSquare,
  Folder,
  Plus,
  Filter,
  SortAsc,
  SortDesc
} from 'lucide-react';

interface Conversation {
  id: string;
  title: string;
  preview: string;
  messageCount: number;
  createdAt: string;
  updatedAt: string;
  isPinned: boolean;
  isStarred?: boolean;
  isArchived?: boolean;
  workspace?: string;
  tags?: string[];
}

interface HistoryPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectConversation: (id: string) => void;
  onNewChat: () => void;
}

type FilterTab = 'all' | 'pinned' | 'starred' | 'archived';

// Mock data for demonstration
const MOCK_CONVERSATIONS: Conversation[] = [
  {
    id: '1',
    title: 'Fix authentication bug in login flow',
    preview: 'The login button is not redirecting properly after OAuth...',
    messageCount: 12,
    createdAt: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
    updatedAt: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
    isPinned: true,
    isStarred: true,
    isArchived: false,
    workspace: 'autonomous-engineering-platform',
    tags: ['bug', 'auth'],
  },
  {
    id: '2',
    title: 'Implement MCP tools panel',
    preview: 'Creating a new UI component for managing MCP tools...',
    messageCount: 24,
    createdAt: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
    updatedAt: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
    isPinned: true,
    isStarred: false,
    isArchived: false,
    workspace: 'autonomous-engineering-platform',
    tags: ['feature', 'ui'],
  },
  {
    id: '3',
    title: 'Database migration for user preferences',
    preview: 'Need to add new columns for storing user preferences...',
    messageCount: 8,
    createdAt: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
    updatedAt: new Date(Date.now() - 1000 * 60 * 60 * 20).toISOString(),
    isPinned: false,
    isStarred: true,
    isArchived: false,
    workspace: 'autonomous-engineering-platform',
    tags: ['database'],
  },
  {
    id: '4',
    title: 'Review PR #45 - API refactoring',
    preview: 'Looking at the changes in the API layer for better...',
    messageCount: 15,
    createdAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 2).toISOString(),
    updatedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 2).toISOString(),
    isPinned: false,
    isStarred: false,
    isArchived: true,
    workspace: 'autonomous-engineering-platform',
    tags: ['review'],
  },
  {
    id: '5',
    title: 'Help with React hooks optimization',
    preview: 'How do I properly memoize this expensive computation...',
    messageCount: 6,
    createdAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 5).toISOString(),
    updatedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 5).toISOString(),
    isPinned: false,
    isStarred: false,
    isArchived: false,
    workspace: 'my-react-app',
    tags: ['react', 'performance'],
  },
];

export const HistoryPanel: React.FC<HistoryPanelProps> = ({
  isOpen,
  onClose,
  onSelectConversation,
  onNewChat,
}) => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'date' | 'title'>('date');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [activeTab, setActiveTab] = useState<FilterTab>('all');
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Fetch conversations from backend
  const fetchConversations = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/memory/conversations');
      if (response.ok) {
        const data = await response.json();
        setConversations(data.conversations || []);
      } else {
        setConversations(MOCK_CONVERSATIONS);
      }
    } catch {
      setConversations(MOCK_CONVERSATIONS);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      fetchConversations();
    }
  }, [isOpen, fetchConversations]);

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Delete this conversation?')) return;

    try {
      await fetch(`/api/memory/conversations/${id}`, { method: 'DELETE' });
    } catch {
      // Continue anyway
    }
    setConversations(prev => prev.filter(c => c.id !== id));
  };

  const handlePin = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setConversations(prev =>
      prev.map(c => (c.id === id ? { ...c, isPinned: !c.isPinned } : c))
    );
  };

  const handleStar = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setConversations(prev =>
      prev.map(c => (c.id === id ? { ...c, isStarred: !c.isStarred } : c))
    );
  };

  const handleArchive = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setConversations(prev =>
      prev.map(c => (c.id === id ? { ...c, isArchived: !c.isArchived } : c))
    );
  };

  const handleSelect = (id: string) => {
    setSelectedId(id);
    onSelectConversation(id);
  };

  // Filter and sort conversations
  const filteredConversations = useMemo(() => {
    let result = [...conversations];

    // Filter by tab
    switch (activeTab) {
      case 'pinned':
        result = result.filter(c => c.isPinned);
        break;
      case 'starred':
        result = result.filter(c => c.isStarred);
        break;
      case 'archived':
        result = result.filter(c => c.isArchived);
        break;
      default:
        result = result.filter(c => !c.isArchived);
    }

    // Filter by search query
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(
        c =>
          c.title.toLowerCase().includes(query) ||
          c.preview.toLowerCase().includes(query) ||
          c.tags?.some(t => t.toLowerCase().includes(query))
      );
    }

    // Sort
    result.sort((a, b) => {
      let comparison = 0;
      if (sortBy === 'date') {
        comparison = new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
      } else {
        comparison = a.title.localeCompare(b.title);
      }
      return sortOrder === 'asc' ? -comparison : comparison;
    });

    // Always show pinned first (except in archived tab)
    if (activeTab !== 'archived') {
      result.sort((a, b) => (b.isPinned ? 1 : 0) - (a.isPinned ? 1 : 0));
    }

    return result;
  }, [conversations, searchQuery, sortBy, sortOrder, activeTab]);

  const formatDate = (isoString: string): string => {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;

    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString();
  };

  // Tab counts
  const tabCounts = useMemo(() => ({
    all: conversations.filter(c => !c.isArchived).length,
    pinned: conversations.filter(c => c.isPinned).length,
    starred: conversations.filter(c => c.isStarred).length,
    archived: conversations.filter(c => c.isArchived).length,
  }), [conversations]);

  if (!isOpen) return null;

  return (
    <div className="history-panel-overlay" onClick={onClose}>
      <div className="history-panel" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="history-header">
          <div className="history-header-title">
            <Clock className="h-5 w-5 history-title-icon" />
            <h3>Chat History</h3>
          </div>
          <div className="history-header-actions">
            <button className="history-new-chat-btn" onClick={onNewChat}>
              <Plus className="h-4 w-4" />
              <span>New Chat</span>
            </button>
            <button className="history-close-btn" onClick={onClose}>
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Filter Tabs */}
        <div className="history-tabs">
          <button
            className={`history-tab ${activeTab === 'all' ? 'active' : ''}`}
            onClick={() => setActiveTab('all')}
          >
            <Filter className="h-3.5 w-3.5 history-tab-icon history-tab-icon--all" />
            <span>All</span>
            <span className="history-tab-count">{tabCounts.all}</span>
          </button>
          <button
            className={`history-tab ${activeTab === 'pinned' ? 'active' : ''}`}
            onClick={() => setActiveTab('pinned')}
          >
            <Pin className="h-3.5 w-3.5 history-tab-icon history-tab-icon--pin" />
            <span>Pinned</span>
            <span className="history-tab-count">{tabCounts.pinned}</span>
          </button>
          <button
            className={`history-tab ${activeTab === 'starred' ? 'active' : ''}`}
            onClick={() => setActiveTab('starred')}
          >
            <Star className="h-3.5 w-3.5 history-tab-icon history-tab-icon--star" />
            <span>Starred</span>
            <span className="history-tab-count">{tabCounts.starred}</span>
          </button>
          <button
            className={`history-tab ${activeTab === 'archived' ? 'active' : ''}`}
            onClick={() => setActiveTab('archived')}
          >
            <Archive className="h-3.5 w-3.5 history-tab-icon history-tab-icon--archive" />
            <span>Archived</span>
            <span className="history-tab-count">{tabCounts.archived}</span>
          </button>
        </div>

        {/* Search and Sort */}
        <div className="history-filters">
          <div className="history-search">
            <Search className="h-4 w-4 search-icon" />
            <input
              type="text"
              placeholder="Search conversations..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button className="search-clear" onClick={() => setSearchQuery('')}>
                <X className="h-3 w-3" />
              </button>
            )}
          </div>

          <div className="history-sort">
            <select value={sortBy} onChange={e => setSortBy(e.target.value as 'date' | 'title')}>
              <option value="date">Date</option>
              <option value="title">Title</option>
            </select>
            <button
              className="sort-order-btn"
              onClick={() => setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')}
              title={sortOrder === 'asc' ? 'Ascending' : 'Descending'}
            >
              {sortOrder === 'asc' ? (
                <SortAsc className="h-4 w-4" />
              ) : (
                <SortDesc className="h-4 w-4" />
              )}
            </button>
          </div>
        </div>

        {/* Conversation List */}
        <div className="history-list">
          {loading ? (
            <div className="history-loading">
              <div className="loading-spinner" />
              <span>Loading conversations...</span>
            </div>
          ) : filteredConversations.length === 0 ? (
            <div className="history-empty">
              <MessageSquare className="h-10 w-10 empty-icon" />
              <p>{searchQuery ? 'No matching conversations' : `No ${activeTab === 'all' ? '' : activeTab + ' '}conversations yet`}</p>
              {activeTab === 'all' && (
                <button className="history-start-chat-btn" onClick={onNewChat}>
                  <Plus className="h-4 w-4" />
                  Start a new chat
                </button>
              )}
            </div>
          ) : (
            filteredConversations.map(conversation => (
              <div
                key={conversation.id}
                className={`history-item ${selectedId === conversation.id ? 'selected' : ''} ${conversation.isPinned ? 'pinned' : ''}`}
                onClick={() => handleSelect(conversation.id)}
              >
                <div className="history-item-header">
                  <div className="history-item-badges">
                    {conversation.isPinned && (
                      <span className="badge badge-pin" title="Pinned">
                        <Pin className="h-3 w-3" />
                      </span>
                    )}
                    {conversation.isStarred && (
                      <span className="badge badge-star" title="Starred">
                        <Star className="h-3 w-3" />
                      </span>
                    )}
                  </div>
                  <span className="history-item-title">{conversation.title}</span>
                  <span className="history-item-date">{formatDate(conversation.updatedAt)}</span>
                </div>

                <p className="history-item-preview">{conversation.preview}</p>

                <div className="history-item-footer">
                  <div className="history-item-meta">
                    <span className="meta-item">
                      <MessageSquare className="h-3 w-3" />
                      {conversation.messageCount}
                    </span>
                    {conversation.workspace && (
                      <span className="meta-item workspace">
                        <Folder className="h-3 w-3" />
                        {conversation.workspace}
                      </span>
                    )}
                  </div>

                  {conversation.tags && conversation.tags.length > 0 && (
                    <div className="history-item-tags">
                      {conversation.tags.map(tag => (
                        <span key={tag} className="tag">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}

                  <div className="history-item-actions">
                    <button
                      className={`action-btn ${conversation.isPinned ? 'active' : ''}`}
                      onClick={e => handlePin(conversation.id, e)}
                      title={conversation.isPinned ? 'Unpin' : 'Pin'}
                    >
                      <Pin className="h-3.5 w-3.5" />
                    </button>
                    <button
                      className={`action-btn ${conversation.isStarred ? 'active' : ''}`}
                      onClick={e => handleStar(conversation.id, e)}
                      title={conversation.isStarred ? 'Unstar' : 'Star'}
                    >
                      <Star className="h-3.5 w-3.5" />
                    </button>
                    <button
                      className={`action-btn ${conversation.isArchived ? 'active' : ''}`}
                      onClick={e => handleArchive(conversation.id, e)}
                      title={conversation.isArchived ? 'Unarchive' : 'Archive'}
                    >
                      <Archive className="h-3.5 w-3.5" />
                    </button>
                    <button
                      className="action-btn action-btn--danger"
                      onClick={e => handleDelete(conversation.id, e)}
                      title="Delete"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer Stats */}
        <div className="history-footer">
          <span>{filteredConversations.length} of {conversations.length} conversations</span>
        </div>
      </div>

      <style>{`
        .history-panel-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.6);
          backdrop-filter: blur(8px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          animation: fadeIn 0.2s ease;
        }

        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }

        .history-panel {
          width: 90%;
          max-width: 650px;
          max-height: 85vh;
          background: linear-gradient(145deg, rgba(25, 30, 40, 0.98), rgba(15, 18, 25, 0.98));
          border: 1px solid rgba(100, 180, 255, 0.15);
          border-radius: 20px;
          display: flex;
          flex-direction: column;
          overflow: hidden;
          animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
          box-shadow:
            0 25px 80px rgba(0, 0, 0, 0.6),
            0 0 40px rgba(100, 180, 255, 0.08),
            inset 0 1px 0 rgba(255, 255, 255, 0.05);
        }

        @keyframes slideUp {
          from {
            opacity: 0;
            transform: translateY(30px) scale(0.95);
          }
          to {
            opacity: 1;
            transform: translateY(0) scale(1);
          }
        }

        /* Header */
        .history-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 18px 22px;
          border-bottom: 1px solid rgba(100, 180, 255, 0.1);
          background: rgba(255, 255, 255, 0.02);
        }

        .history-header-title {
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .history-title-icon {
          color: #64b4ff;
          animation: pulse 2s ease-in-out infinite;
        }

        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.6; }
        }

        .history-header h3 {
          margin: 0;
          font-size: 17px;
          font-weight: 600;
          color: #fff;
          letter-spacing: -0.02em;
        }

        .history-header-actions {
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .history-new-chat-btn {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 8px 14px;
          background: linear-gradient(135deg, #3b82f6, #8b5cf6);
          border: none;
          border-radius: 10px;
          color: white;
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
          box-shadow: 0 2px 10px rgba(59, 130, 246, 0.3);
        }

        .history-new-chat-btn:hover {
          transform: translateY(-1px);
          box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4);
        }

        .history-close-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 32px;
          height: 32px;
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          color: rgba(255, 255, 255, 0.6);
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .history-close-btn:hover {
          background: rgba(239, 68, 68, 0.15);
          border-color: rgba(239, 68, 68, 0.3);
          color: #ef4444;
        }

        /* Filter Tabs */
        .history-tabs {
          display: flex;
          gap: 6px;
          padding: 12px 18px;
          border-bottom: 1px solid rgba(100, 180, 255, 0.08);
          background: rgba(0, 0, 0, 0.2);
        }

        .history-tab {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 8px 14px;
          background: transparent;
          border: 1px solid transparent;
          border-radius: 10px;
          color: rgba(255, 255, 255, 0.5);
          font-size: 12px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.25s ease;
        }

        .history-tab:hover {
          background: rgba(255, 255, 255, 0.05);
          color: rgba(255, 255, 255, 0.8);
        }

        .history-tab.active {
          background: rgba(100, 180, 255, 0.15);
          border-color: rgba(100, 180, 255, 0.3);
          color: #64b4ff;
        }

        .history-tab-icon {
          transition: all 0.3s ease;
        }

        .history-tab:hover .history-tab-icon--pin,
        .history-tab.active .history-tab-icon--pin {
          animation: pinWiggle 0.5s ease;
        }

        .history-tab:hover .history-tab-icon--star,
        .history-tab.active .history-tab-icon--star {
          animation: starSparkle 0.6s ease;
        }

        .history-tab:hover .history-tab-icon--archive,
        .history-tab.active .history-tab-icon--archive {
          animation: archiveSlide 0.4s ease;
        }

        @keyframes pinWiggle {
          0%, 100% { transform: rotate(0deg); }
          25% { transform: rotate(-15deg); }
          75% { transform: rotate(15deg); }
        }

        @keyframes starSparkle {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.2); filter: drop-shadow(0 0 4px gold); }
        }

        @keyframes archiveSlide {
          0% { transform: translateY(0); }
          50% { transform: translateY(2px); }
          100% { transform: translateY(0); }
        }

        .history-tab-count {
          padding: 2px 6px;
          background: rgba(255, 255, 255, 0.1);
          border-radius: 6px;
          font-size: 10px;
          font-weight: 600;
        }

        .history-tab.active .history-tab-count {
          background: rgba(100, 180, 255, 0.25);
        }

        /* Search and Filters */
        .history-filters {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 14px 18px;
          border-bottom: 1px solid rgba(100, 180, 255, 0.08);
        }

        .history-search {
          flex: 1;
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 10px 14px;
          background: rgba(0, 0, 0, 0.25);
          border: 1px solid rgba(100, 180, 255, 0.1);
          border-radius: 12px;
          transition: all 0.2s ease;
        }

        .history-search:focus-within {
          border-color: rgba(100, 180, 255, 0.3);
          box-shadow: 0 0 15px rgba(100, 180, 255, 0.1);
        }

        .history-search .search-icon {
          color: rgba(255, 255, 255, 0.4);
        }

        .history-search input {
          flex: 1;
          background: transparent;
          border: none;
          outline: none;
          color: #fff;
          font-size: 13px;
        }

        .history-search input::placeholder {
          color: rgba(255, 255, 255, 0.35);
        }

        .search-clear {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 18px;
          height: 18px;
          background: rgba(255, 255, 255, 0.1);
          border: none;
          border-radius: 50%;
          color: rgba(255, 255, 255, 0.5);
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .search-clear:hover {
          background: rgba(239, 68, 68, 0.2);
          color: #ef4444;
        }

        .history-sort {
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .history-sort select {
          padding: 8px 12px;
          background: rgba(0, 0, 0, 0.25);
          border: 1px solid rgba(100, 180, 255, 0.1);
          border-radius: 10px;
          color: rgba(255, 255, 255, 0.8);
          font-size: 12px;
          cursor: pointer;
          outline: none;
        }

        .sort-order-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 34px;
          height: 34px;
          background: rgba(0, 0, 0, 0.25);
          border: 1px solid rgba(100, 180, 255, 0.1);
          border-radius: 10px;
          color: rgba(255, 255, 255, 0.6);
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .sort-order-btn:hover {
          background: rgba(100, 180, 255, 0.1);
          color: #64b4ff;
        }

        /* Conversation List */
        .history-list {
          flex: 1;
          overflow-y: auto;
          padding: 12px;
        }

        .history-loading,
        .history-empty {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 50px 20px;
          color: rgba(255, 255, 255, 0.5);
          text-align: center;
        }

        .loading-spinner {
          width: 32px;
          height: 32px;
          border: 2px solid rgba(100, 180, 255, 0.2);
          border-top-color: #64b4ff;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
          margin-bottom: 12px;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        .empty-icon {
          color: rgba(100, 180, 255, 0.3);
          margin-bottom: 12px;
        }

        .history-start-chat-btn {
          display: flex;
          align-items: center;
          gap: 6px;
          margin-top: 16px;
          padding: 10px 18px;
          background: linear-gradient(135deg, #3b82f6, #8b5cf6);
          border: none;
          border-radius: 10px;
          color: white;
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .history-start-chat-btn:hover {
          transform: translateY(-1px);
          box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4);
        }

        /* History Item */
        .history-item {
          padding: 14px 16px;
          margin-bottom: 8px;
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(100, 180, 255, 0.08);
          border-radius: 14px;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .history-item:hover {
          background: rgba(100, 180, 255, 0.06);
          border-color: rgba(100, 180, 255, 0.15);
          transform: translateY(-1px);
        }

        .history-item.selected {
          background: rgba(100, 180, 255, 0.12);
          border-color: rgba(100, 180, 255, 0.3);
        }

        .history-item.pinned {
          border-left: 3px solid #64b4ff;
        }

        .history-item-header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 8px;
        }

        .history-item-badges {
          display: flex;
          gap: 4px;
        }

        .badge {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 20px;
          height: 20px;
          border-radius: 5px;
        }

        .badge-pin {
          background: rgba(100, 180, 255, 0.2);
          color: #64b4ff;
        }

        .badge-star {
          background: rgba(250, 204, 21, 0.2);
          color: #facc15;
        }

        .history-item-title {
          flex: 1;
          font-size: 14px;
          font-weight: 500;
          color: #fff;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .history-item-date {
          font-size: 11px;
          color: rgba(255, 255, 255, 0.4);
        }

        .history-item-preview {
          margin: 0 0 10px 0;
          font-size: 12px;
          color: rgba(255, 255, 255, 0.5);
          line-height: 1.4;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          overflow: hidden;
        }

        .history-item-footer {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
        }

        .history-item-meta {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .meta-item {
          display: flex;
          align-items: center;
          gap: 4px;
          font-size: 11px;
          color: rgba(255, 255, 255, 0.4);
        }

        .meta-item.workspace {
          max-width: 120px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .history-item-tags {
          display: flex;
          gap: 4px;
        }

        .tag {
          padding: 2px 8px;
          background: rgba(139, 92, 246, 0.15);
          border-radius: 6px;
          font-size: 10px;
          color: rgba(139, 92, 246, 0.9);
        }

        .history-item-actions {
          display: flex;
          gap: 4px;
          opacity: 0;
          transition: opacity 0.2s ease;
        }

        .history-item:hover .history-item-actions {
          opacity: 1;
        }

        .action-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 28px;
          height: 28px;
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 7px;
          color: rgba(255, 255, 255, 0.5);
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .action-btn:hover {
          background: rgba(100, 180, 255, 0.15);
          border-color: rgba(100, 180, 255, 0.3);
          color: #64b4ff;
        }

        .action-btn.active {
          background: rgba(100, 180, 255, 0.2);
          border-color: rgba(100, 180, 255, 0.4);
          color: #64b4ff;
        }

        .action-btn--danger:hover {
          background: rgba(239, 68, 68, 0.15);
          border-color: rgba(239, 68, 68, 0.3);
          color: #ef4444;
        }

        /* Footer */
        .history-footer {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 12px 18px;
          border-top: 1px solid rgba(100, 180, 255, 0.08);
          font-size: 11px;
          color: rgba(255, 255, 255, 0.4);
        }
      `}</style>
    </div>
  );
};
