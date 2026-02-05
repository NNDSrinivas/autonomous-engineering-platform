import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";
import "./EnhancedNaviMarkdown.css";

interface EnhancedNaviMarkdownProps {
  content: string;
  thinking?: string[];
  className?: string;
}

export const EnhancedNaviMarkdown: React.FC<EnhancedNaviMarkdownProps> = ({
  content,
  thinking = [],
  className = "",
}) => {
  const [isThinkingExpanded, setIsThinkingExpanded] = useState(false);

  return (
    <div className={`navi-enhanced-markdown ${className}`}>
      {/* Main message content with proper markdown rendering */}
      <div className="navi-main-content">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeHighlight]}
          components={{
            // Custom renderers for better styling
            h1: ({ node, ...props }) => (
              <h1 className="text-2xl font-bold mt-4 mb-2" {...props} />
            ),
            h2: ({ node, ...props }) => (
              <h2 className="text-xl font-bold mt-3 mb-2" {...props} />
            ),
            h3: ({ node, ...props }) => (
              <h3 className="text-lg font-semibold mt-2 mb-1" {...props} />
            ),
            h4: ({ node, ...props }) => (
              <h4 className="text-base font-semibold mt-2 mb-1" {...props} />
            ),
            p: ({ node, ...props }) => (
              <p className="my-2 leading-relaxed" {...props} />
            ),
            ul: ({ node, ...props }) => (
              <ul className="list-disc list-inside my-2 space-y-1" {...props} />
            ),
            ol: ({ node, ...props }) => (
              <ol className="list-decimal list-inside my-2 space-y-1" {...props} />
            ),
            li: ({ node, ...props }) => (
              <li className="ml-4" {...props} />
            ),
            code: ({ node, inline, className, children, ...props }: any) => {
              if (inline) {
                return (
                  <code
                    className="bg-gray-800 text-pink-400 px-1.5 py-0.5 rounded text-sm font-mono"
                    {...props}
                  >
                    {children}
                  </code>
                );
              }
              return (
                <code
                  className={`block bg-gray-900 p-3 rounded-md overflow-x-auto text-sm font-mono ${className || ""}`}
                  {...props}
                >
                  {children}
                </code>
              );
            },
            pre: ({ node, ...props }) => (
              <pre className="my-3 overflow-x-auto" {...props} />
            ),
            blockquote: ({ node, ...props }) => (
              <blockquote
                className="border-l-4 border-blue-500 pl-4 my-2 italic text-gray-300"
                {...props}
              />
            ),
            a: ({ node, ...props }) => (
              <a
                className="text-blue-400 hover:text-blue-300 underline"
                target="_blank"
                rel="noopener noreferrer"
                {...props}
              />
            ),
            table: ({ node, ...props }) => (
              <div className="overflow-x-auto my-3">
                <table className="min-w-full border border-gray-700" {...props} />
              </div>
            ),
            th: ({ node, ...props }) => (
              <th className="border border-gray-700 px-3 py-2 bg-gray-800 font-semibold" {...props} />
            ),
            td: ({ node, ...props }) => (
              <td className="border border-gray-700 px-3 py-2" {...props} />
            ),
          }}
        >
          {content}
        </ReactMarkdown>
      </div>

      {/* Collapsible thinking section */}
      {thinking && thinking.length > 0 && (
        <div className="navi-thinking-section mt-4 border-t border-gray-700 pt-3">
          <button
            onClick={() => setIsThinkingExpanded(!isThinkingExpanded)}
            className="flex items-center gap-2 text-sm text-gray-400 hover:text-gray-300 transition-colors"
          >
            <span className={`transform transition-transform ${isThinkingExpanded ? 'rotate-90' : ''}`}>
              ▶
            </span>
            <span className="font-medium">
              {isThinkingExpanded ? 'Hide' : 'Show'} reasoning ({thinking.length} steps)
            </span>
          </button>

          {isThinkingExpanded && (
            <div className="mt-3 pl-6 space-y-2">
              {thinking.map((step, index) => (
                <div
                  key={index}
                  className="flex gap-3 text-sm text-gray-400 border-l-2 border-gray-700 pl-3 py-1"
                >
                  <span className="text-gray-600 font-mono text-xs mt-0.5">
                    {index + 1}.
                  </span>
                  <span className="flex-1">{step}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
