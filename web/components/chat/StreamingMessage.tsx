/**
 * StreamingMessage Component
 * Displays real-time streaming content from NAVI
 */

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { Bot, Loader2 } from 'lucide-react';

export interface StreamingMessageProps {
  content: string;
}

export function StreamingMessage({ content }: StreamingMessageProps) {
  return (
    <div className="relative flex gap-4 px-6 py-5 bg-background border-b border-border/30 animate-in fade-in duration-300">
      {/* Avatar */}
      <div className="flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center bg-gradient-to-br from-cyan-500 to-blue-600 text-white shadow-lg shadow-[0_0_15px_rgba(6,182,212,0.4)]">
        <Bot size={16} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-medium">NAVI</span>
          <Loader2 size={12} className="animate-spin text-muted-foreground" />
        </div>

        <div className="prose prose-sm dark:prose-invert max-w-none">
          {content ? (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeHighlight]}
            >
              {content}
            </ReactMarkdown>
          ) : (
            <div className="flex items-center gap-2 text-muted-foreground">
              <span className="text-sm">Thinking...</span>
            </div>
          )}
        </div>

        {/* Cursor */}
        <span className="inline-block w-2 h-4 ml-1 bg-primary animate-pulse" />
      </div>
    </div>
  );
}

export default StreamingMessage;
