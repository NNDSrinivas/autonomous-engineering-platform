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
  PenSquare,
  Filter,
  SortAsc,
  SortDesc
} from 'lucide-react';
import {
  listSessions,
  deleteSession,
  toggleSessionPin,
  toggleSessionStar,
  toggleSessionArchive,
  type ChatSessionSummary
} from '../../utils/chatSessions';

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

// Convert ChatSessionSummary to Conversation format
const sessionToConversation = (session: ChatSessionSummary): Conversation => ({
  id: session.id,
  title: session.title,
  preview: session.lastMessagePreview || 'No messages yet',
  messageCount: session.messageCount,
  createdAt: session.createdAt,
  updatedAt: session.updatedAt,
  isPinned: session.isPinned || false,
  isStarred: session.isStarred || false,
  isArchived: session.isArchived || false,
  workspace: session.repoName || session.workspaceRoot?.split('/').pop(),
  tags: session.tags?.map(t => t.label),
});

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

  // Load conversations from localStorage
  const fetchConversations = useCallback(() => {
    setLoading(true);
    try {
      const sessions = listSessions();
      const conversations = sessions.map(sessionToConversation);
      setConversations(conversations);
    } catch (error) {
      console.error('[HistoryPanel] Error loading sessions:', error);
      setConversations([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      fetchConversations();
    }
  }, [isOpen, fetchConversations]);

  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Delete this conversation?')) return;

    deleteSession(id);
    setConversations(prev => prev.filter(c => c.id !== id));
  };

  const handlePin = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const newValue = toggleSessionPin(id);
    setConversations(prev =>
      prev.map(c => (c.id === id ? { ...c, isPinned: newValue } : c))
    );
  };

  const handleStar = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const newValue = toggleSessionStar(id);
    setConversations(prev =>
      prev.map(c => (c.id === id ? { ...c, isStarred: newValue } : c))
    );
  };

  const handleArchive = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const newValue = toggleSessionArchive(id);
    setConversations(prev =>
      prev.map(c => (c.id === id ? { ...c, isArchived: newValue } : c))
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
              <PenSquare className="h-4 w-4" />
              <span>New Chat</span>
            </button>
            <button className="navi-icon-btn navi-icon-btn--sm history-icon-btn history-close-btn" onClick={onClose}>
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
              <button className="navi-icon-btn navi-icon-btn--sm history-icon-btn history-search-clear" onClick={() => setSearchQuery('')}>
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
              className="navi-icon-btn navi-icon-btn--sm history-icon-btn history-sort-btn"
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
                  <PenSquare className="h-4 w-4" />
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
                      className={`navi-icon-btn navi-icon-btn--sm history-action-btn ${conversation.isPinned ? 'navi-icon-btn--active' : ''}`}
                      onClick={e => handlePin(conversation.id, e)}
                      title={conversation.isPinned ? 'Unpin' : 'Pin'}
                    >
                      <Pin className="h-3.5 w-3.5" />
                    </button>
                    <button
                      className={`navi-icon-btn navi-icon-btn--sm history-action-btn ${conversation.isStarred ? 'navi-icon-btn--active' : ''}`}
                      onClick={e => handleStar(conversation.id, e)}
                      title={conversation.isStarred ? 'Unstar' : 'Star'}
                    >
                      <Star className="h-3.5 w-3.5" />
                    </button>
                    <button
                      className={`navi-icon-btn navi-icon-btn--sm history-action-btn ${conversation.isArchived ? 'navi-icon-btn--active' : ''}`}
                      onClick={e => handleArchive(conversation.id, e)}
                      title={conversation.isArchived ? 'Unarchive' : 'Archive'}
                    >
                      <Archive className="h-3.5 w-3.5" />
                    </button>
                    <button
                      className="navi-icon-btn navi-icon-btn--sm history-action-btn history-action-btn--danger"
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
          background: linear-gradient(160deg, hsl(var(--card) / 0.98), hsl(var(--background) / 0.98));
          border: 1px solid hsl(var(--border) / 0.8);
          border-radius: 20px;
          display: flex;
          flex-direction: column;
          overflow: hidden;
          animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
          box-shadow:
            0 25px 80px hsl(var(--background) / 0.7),
            0 0 40px hsl(var(--primary) / 0.12),
            inset 0 1px 0 hsl(var(--foreground) / 0.04);
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
          border-bottom: 1px solid hsl(var(--border) / 0.7);
          background: hsl(var(--card) / 0.35);
        }

        .history-header-title {
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .history-title-icon {
          color: hsl(var(--primary));
          transition: transform 0.2s ease, filter 0.2s ease;
        }

        .history-header-title:hover .history-title-icon {
          transform: translateY(-1px) scale(1.05);
          filter: drop-shadow(0 6px 12px hsl(var(--primary) / 0.2));
        }

        .history-header h3 {
          margin: 0;
          font-size: 17px;
          font-weight: 600;
          color: hsl(var(--foreground));
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
          background: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)));
          border: 1px solid hsl(var(--primary) / 0.45);
          border-radius: 10px;
          color: hsl(var(--primary-foreground));
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
          box-shadow: 0 6px 18px hsl(var(--primary) / 0.3);
        }

        .history-new-chat-btn:hover {
          transform: translateY(-1px);
          box-shadow: 0 8px 24px hsl(var(--primary) / 0.35);
        }

        .history-icon-btn {
          --icon-btn-size: 30px;
        }

        .history-search-clear {
          --icon-btn-size: 22px;
          border-radius: 999px;
        }

        .history-close-btn.navi-icon-btn:hover {
          background: hsl(var(--destructive) / 0.14);
          border-color: hsl(var(--destructive) / 0.4);
          color: hsl(var(--destructive));
          box-shadow: 0 4px 12px hsl(var(--destructive) / 0.2);
        }

        /* Filter Tabs */
        .history-tabs {
          display: flex;
          gap: 6px;
          padding: 12px 18px;
          border-bottom: 1px solid hsl(var(--border) / 0.6);
          background: hsl(var(--background) / 0.35);
        }

        .history-tab {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 8px 14px;
          background: transparent;
          border: 1px solid transparent;
          border-radius: 10px;
          color: hsl(var(--muted-foreground));
          font-size: 12px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.25s ease;
        }

        .history-tab:hover {
          background: hsl(var(--secondary) / 0.6);
          color: hsl(var(--foreground));
        }

        .history-tab.active {
          background: hsl(var(--secondary) / 0.7);
          border-color: hsl(var(--border) / 0.7);
          color: hsl(var(--foreground));
          box-shadow: inset 0 0 0 1px hsl(var(--primary) / 0.08);
        }

        .history-tab-icon {
          transition: all 0.3s ease;
        }

        .history-tab:hover .history-tab-icon {
          transform: translateY(-1px) scale(1.06);
          filter: drop-shadow(0 6px 12px hsl(var(--primary) / 0.2));
        }

        .history-tab-count {
          padding: 2px 6px;
          background: hsl(var(--secondary) / 0.7);
          border-radius: 6px;
          font-size: 10px;
          font-weight: 600;
          color: hsl(var(--foreground) / 0.75);
        }

        .history-tab.active .history-tab-count {
          background: hsl(var(--secondary) / 0.8);
          color: hsl(var(--foreground));
        }

        /* Search and Filters */
        .history-filters {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 14px 18px;
          border-bottom: 1px solid hsl(var(--border) / 0.6);
        }

        .history-search {
          flex: 1;
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 10px 14px;
          background: hsl(var(--secondary) / 0.45);
          border: 1px solid hsl(var(--border) / 0.7);
          border-radius: 12px;
          transition: all 0.2s ease;
        }

        .history-search:focus-within {
          border-color: hsl(var(--primary) / 0.4);
          box-shadow: 0 0 0 2px hsl(var(--primary) / 0.15);
        }

        .history-search .search-icon {
          color: hsl(var(--muted-foreground));
          transition: transform 0.2s ease, filter 0.2s ease;
        }

        .history-search:focus-within .search-icon {
          transform: translateY(-1px) scale(1.05);
          filter: drop-shadow(0 6px 12px hsl(var(--primary) / 0.18));
        }

        .history-search input {
          flex: 1;
          background: transparent;
          border: none;
          outline: none;
          color: hsl(var(--foreground));
          font-size: 13px;
        }

        .history-search input::placeholder {
          color: hsl(var(--muted-foreground) / 0.8);
        }

        .history-search-clear.navi-icon-btn:hover {
          background: hsl(var(--destructive) / 0.12);
          border-color: hsl(var(--destructive) / 0.4);
          color: hsl(var(--destructive));
        }

        .history-sort {
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .history-sort select {
          padding: 8px 12px;
          background: hsl(var(--secondary) / 0.45);
          border: 1px solid hsl(var(--border) / 0.7);
          border-radius: 10px;
          color: hsl(var(--foreground) / 0.9);
          font-size: 12px;
          cursor: pointer;
          outline: none;
        }

        .history-sort-btn {
          --icon-btn-size: 32px;
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
          color: hsl(var(--muted-foreground));
          text-align: center;
        }

        .loading-spinner {
          width: 32px;
          height: 32px;
          border: 2px solid hsl(var(--primary) / 0.2);
          border-top-color: hsl(var(--primary));
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
          margin-bottom: 12px;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        .empty-icon {
          color: hsl(var(--primary) / 0.35);
          margin-bottom: 12px;
        }

        .history-start-chat-btn {
          display: flex;
          align-items: center;
          gap: 6px;
          margin-top: 16px;
          padding: 10px 18px;
          background: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--accent)));
          border: 1px solid hsl(var(--primary) / 0.45);
          border-radius: 10px;
          color: hsl(var(--primary-foreground));
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .history-start-chat-btn:hover {
          transform: translateY(-1px);
          box-shadow: 0 8px 22px hsl(var(--primary) / 0.35);
        }

        /* History Item */
        .history-item {
          padding: 14px 16px;
          margin-bottom: 8px;
          background: hsl(var(--card) / 0.7);
          border: 1px solid hsl(var(--border) / 0.7);
          border-radius: 14px;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .history-item:hover {
          background: hsl(var(--primary) / 0.08);
          border-color: hsl(var(--primary) / 0.25);
          transform: translateY(-1px);
        }

        .history-item.selected {
          background: hsl(var(--primary) / 0.15);
          border-color: hsl(var(--primary) / 0.4);
        }

        .history-item.pinned {
          border-left: 3px solid hsl(var(--primary));
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
          background: hsl(var(--primary) / 0.2);
          color: hsl(var(--primary));
        }

        .badge-star {
          background: hsl(var(--accent) / 0.2);
          color: hsl(var(--accent));
        }

        .history-item-title {
          flex: 1;
          font-size: 14px;
          font-weight: 500;
          color: hsl(var(--foreground));
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .history-item-date {
          font-size: 11px;
          color: hsl(var(--muted-foreground));
        }

        .history-item-preview {
          margin: 0 0 10px 0;
          font-size: 12px;
          color: hsl(var(--muted-foreground));
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
          color: hsl(var(--muted-foreground));
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
          background: hsl(var(--accent) / 0.16);
          border: 1px solid hsl(var(--accent) / 0.3);
          border-radius: 6px;
          font-size: 10px;
          color: hsl(var(--accent));
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

        .history-action-btn {
          --icon-btn-size: 26px;
        }

        .history-action-btn--danger.navi-icon-btn:hover {
          background: hsl(var(--destructive) / 0.14);
          border-color: hsl(var(--destructive) / 0.4);
          color: hsl(var(--destructive));
        }

        /* Footer */
        .history-footer {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 12px 18px;
          border-top: 1px solid hsl(var(--border) / 0.6);
          font-size: 11px;
          color: hsl(var(--muted-foreground));
        }
      `}</style>
    </div>
  );
};
