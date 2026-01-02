"use client";

import React from "react";
import type { NaviChatMessage } from "../../../types/naviChat";

export interface NaviChatMessageListProps {
  messages: NaviChatMessage[];
  onAppendMessages?: (msgs: NaviChatMessage[]) => void;
}

type NaviSourceLike = {
  id?: string;
  title?: string | null;
  path?: string | null;
  kind?: string | null;
  description?: string | null;
};

function getSourceLabel(source: NaviSourceLike, index: number): string {
  if (source.title && source.title.trim().length > 0) {
    return source.title.trim();
  }
  if (source.path && source.path.trim().length > 0) {
    const parts = source.path.split(/[\\/]/);
    const last = parts[parts.length - 1] || source.path;
    return last;
  }
  return `Source ${index + 1}`;
}

function getSourceSubtitle(source: NaviSourceLike): string | undefined {
  if (source.path && source.path.trim().length > 0) {
    return source.path;
  }
  return source.description ?? undefined;
}

export const NaviChatMessageList: React.FC<NaviChatMessageListProps> = ({
  messages,
}) => {
  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto px-3 py-4 text-sm text-slate-100">
      {messages.map((message) => {
        const isUser = message.role === "user";
        const sources = (message as any).sources ?? (message as any).meta?.sources;
        const messageText =
          message.content ??
          (message as any).text ??
          String((message as any).intent ?? "");

        return (
          <div
            key={message.id}
            className={isUser ? "flex justify-end" : "flex justify-start"}
          >
            <div className="max-w-2xl space-y-2">
              {/* Bubble */}
              <div
                className={
                  isUser
                    ? "rounded-2xl bg-sky-500 px-4 py-2 text-sm text-white shadow-md shadow-sky-900/40"
                    : "rounded-2xl bg-slate-900/90 px-4 py-3 text-sm text-slate-100 border border-slate-800/80 shadow-md shadow-slate-900/40"
                }
              >
                <p className="whitespace-pre-wrap leading-relaxed">
                  {messageText}
                </p>
              </div>

              {/* Related context / sources */}
              {!isUser && Array.isArray(sources) && sources.length > 0 && (
                <MessageSourcesPanel sources={sources as NaviSourceLike[]} />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};

interface MessageSourcesPanelProps {
  sources: NaviSourceLike[];
}

const MessageSourcesPanel: React.FC<MessageSourcesPanelProps> = ({
  sources,
}) => {
  if (!sources || sources.length === 0) return null;

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/90 px-3 py-2 text-xs text-slate-200">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-300">
            Related context
          </span>
          <span className="rounded-full bg-slate-800/80 px-2 py-0.5 text-[10px] font-medium text-slate-400">
            {sources.length} source{sources.length === 1 ? "" : "s"}
          </span>
        </div>
        <span className="text-[10px] uppercase tracking-wide text-slate-500">
          OTHER
        </span>
      </div>

      <div className="flex flex-wrap gap-2">
        {sources.map((source, index) => {
          const label = getSourceLabel(source, index);
          const subtitle = getSourceSubtitle(source);

          return (
            <button
              key={source.id ?? `${label}-${index}`}
              type="button"
              className="group flex min-w-[110px] max-w-xs flex-col rounded-xl border border-slate-700/70 bg-slate-900/80 px-2.5 py-1.5 text-left shadow-sm shadow-slate-900/40 transition hover:border-pink-500/80 hover:bg-slate-900"
            >
              <span className="flex items-center gap-1.5">
                <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-pink-500/80 text-[9px] font-semibold text-white shadow-sm shadow-pink-900/60">
                  🔗
                </span>
                <span className="truncate text-[11px] font-medium text-slate-50">
                  {label}
                </span>
              </span>
              <div className="mt-0.5 flex items-center justify-between gap-2">
                <span className="line-clamp-1 text-[10px] text-slate-500">
                  {subtitle}
                </span>
                <span className="text-[9px] font-semibold uppercase tracking-wide text-pink-400/80">
                  Source
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
