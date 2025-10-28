/**
 * TimelineView - Chronological list of events
 */

import React from 'react';
import dayjs from 'dayjs';
import clsx from 'clsx';

interface TimelineItem {
  id: number;
  ts?: string;
  created_at?: string;
  title: string;
  kind: string;
  foreign_id?: string;
  link?: string;
  summary?: string;
}

interface TimelineViewProps {
  items: TimelineItem[];
  onOpenLink?: (url: string) => void;
}

const KIND_COLORS: Record<string, string> = {
  meeting: 'bg-purple-100 text-purple-800',
  jira_issue: 'bg-blue-100 text-blue-800',
  pr: 'bg-green-100 text-green-800',
  run: 'bg-yellow-100 text-yellow-800',
  incident: 'bg-red-100 text-red-800',
  doc: 'bg-indigo-100 text-indigo-800',
  slack_thread: 'bg-violet-100 text-violet-800',
};

const KIND_ICONS: Record<string, string> = {
  meeting: '📅',
  jira_issue: '🎫',
  pr: '🔀',
  run: '🚀',
  incident: '🔥',
  doc: '📄',
  slack_thread: '💬',
};

export const TimelineView: React.FC<TimelineViewProps> = ({ items, onOpenLink }) => {
  // Sort by timestamp ascending
  const sortedItems = [...items].sort((a, b) => {
    const tsA = a.ts || a.created_at || '';
    const tsB = b.ts || b.created_at || '';
    return new Date(tsA).getTime() - new Date(tsB).getTime();
  });

  if (sortedItems.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
        <p className="text-gray-500">No timeline events</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {sortedItems.map((item, idx) => {
        const timestamp = item.ts || item.created_at;
        const kindColor = KIND_COLORS[item.kind] || 'bg-gray-100 text-gray-800';
        const kindIcon = KIND_ICONS[item.kind] || '📌';

        return (
          <div
            key={item.id || idx}
            className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-2">
                  <span className={clsx('px-2 py-1 rounded text-xs font-medium', kindColor)}>
                    {kindIcon} {item.kind}
                  </span>
                  {timestamp && (
                    <span className="text-xs text-gray-500">
                      {dayjs(timestamp).format('MMM D, YYYY HH:mm')}
                    </span>
                  )}
                </div>
                <h3 className="text-sm font-semibold text-gray-900 mb-1">{item.title}</h3>
                {item.summary && (
                  <p className="text-xs text-gray-600 line-clamp-2">{item.summary}</p>
                )}
              </div>
              {item.link && (
                <button
                  onClick={() => onOpenLink?.(item.link!)}
                  className="px-3 py-1 text-xs font-medium text-blue-600 hover:text-blue-800 border border-blue-300 rounded hover:bg-blue-50 transition-colors whitespace-nowrap"
                >
                  Open Source
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};
