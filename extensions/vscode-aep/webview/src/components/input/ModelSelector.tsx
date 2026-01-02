import React, { useState } from 'react';

export type Model = 'auto' | 'gpt-4.1' | 'gpt-4o' | 'claude-sonnet-4' | 'claude-opus' | 'gemini-pro';

interface ModelSelectorProps {
  value: Model;
  onChange: (model: Model) => void;
}

/**
 * ModelSelector - Copilot-style model dropdown
 * 
 * Phase 4.0 UI Parity:
 * - Model selection matching Copilot behavior
 * - Speed/cost hints for each model
 * - Clear visual hierarchy
 */
export function ModelSelector({ value, onChange }: ModelSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);

  const models: Array<{ 
    id: Model; 
    label: string; 
    provider?: string;
    isProvider?: boolean;
  }> = [
    { id: 'auto', label: 'Auto (Recommended)', provider: '' },
    { id: 'gpt-4.1', label: 'GPT-4.1', provider: 'OpenAI', isProvider: false },
    { id: 'gpt-4o', label: 'GPT-4o', provider: 'OpenAI', isProvider: false },
    { id: 'claude-sonnet-4', label: 'Claude Sonnet 4', provider: 'Anthropic', isProvider: false },
    { id: 'claude-opus', label: 'Claude Opus 4', provider: 'Anthropic', isProvider: false },
    { id: 'gemini-pro', label: 'Gemini Pro', provider: 'Google', isProvider: false },
  ];

  const currentModel = models.find(m => m.id === value) || models[0];

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1.5 px-2 py-1 h-[28px] text-xs bg-[var(--vscode-input-background)] border border-[var(--vscode-input-border)] rounded-md hover:border-[var(--vscode-focusBorder)] transition-colors min-w-[80px]"
      >
        <span className="font-medium text-[var(--vscode-foreground)] text-xs">{currentModel.label}</span>
        <svg 
          className={`w-3 h-3 text-[var(--vscode-descriptionForeground)] transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute bottom-full mb-1 left-0 min-w-[220px] bg-[var(--vscode-dropdown-background)] border border-[var(--vscode-dropdown-border)] rounded-md shadow-lg z-50">
          {/* Auto (Recommended) */}
          <button
            key="auto"
            onClick={() => {
              onChange('auto');
              setIsOpen(false);
            }}
            className={`w-full flex items-center justify-between px-3 py-2.5 text-sm text-left hover:bg-[var(--vscode-list-hoverBackground)] transition-colors border-b border-[var(--vscode-dropdown-border)] ${
              value === 'auto' ? 'bg-[var(--vscode-list-activeSelectionBackground)] text-[var(--vscode-list-activeSelectionForeground)]' : 'text-[var(--vscode-foreground)]'
            }`}
          >
            <span className="font-medium">Auto (Recommended)</span>
            {value === 'auto' && (
              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
            )}
          </button>
          
          {/* OpenAI */}
          <div className="navi-model-provider px-3 py-1.5 text-[11px] uppercase opacity-45 bg-[var(--vscode-dropdown-background)]">
            OpenAI
          </div>
          {models.filter(m => m.provider === 'OpenAI').map((model) => (
            <button
              key={model.id}
              onClick={() => {
                onChange(model.id);
                setIsOpen(false);
              }}
              className={`w-full flex items-center justify-between px-4 py-2 text-sm text-left hover:bg-[var(--vscode-list-hoverBackground)] transition-colors ${
                value === model.id ? 'bg-[var(--vscode-list-activeSelectionBackground)] text-[var(--vscode-list-activeSelectionForeground)]' : 'text-[var(--vscode-foreground)]'
              }`}
            >
              <span>{model.label}</span>
              {value === model.id && (
                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
              )}
            </button>
          ))}
          
          {/* Anthropic */}
          <div className="navi-model-provider px-3 py-1.5 text-[11px] uppercase opacity-45 bg-[var(--vscode-dropdown-background)] mt-1">
            Anthropic
          </div>
          {models.filter(m => m.provider === 'Anthropic').map((model) => (
            <button
              key={model.id}
              onClick={() => {
                onChange(model.id);
                setIsOpen(false);
              }}
              className={`w-full flex items-center justify-between px-4 py-2 text-sm text-left hover:bg-[var(--vscode-list-hoverBackground)] transition-colors ${
                value === model.id ? 'bg-[var(--vscode-list-activeSelectionBackground)] text-[var(--vscode-list-activeSelectionForeground)]' : 'text-[var(--vscode-foreground)]'
              }`}
            >
              <span>{model.label}</span>
              {value === model.id && (
                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
              )}
            </button>
          ))}
          
          {/* Google */}
          <div className="navi-model-provider px-3 py-1.5 text-[11px] uppercase opacity-45 bg-[var(--vscode-dropdown-background)] mt-1">
            Google
          </div>
          {models.filter(m => m.provider === 'Google').map((model) => (
            <button
              key={model.id}
              onClick={() => {
                onChange(model.id);
                setIsOpen(false);
              }}
              className={`w-full flex items-center justify-between px-4 py-2 text-sm text-left hover:bg-[var(--vscode-list-hoverBackground)] transition-colors ${
                value === model.id ? 'bg-[var(--vscode-list-activeSelectionBackground)] text-[var(--vscode-list-activeSelectionForeground)]' : 'text-[var(--vscode-foreground)]'
              }`}
            >
              <span>{model.label}</span>
              {value === model.id && (
                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
              )}
            </button>
          ))}
          
          {/* Separator */}
          <div className="border-t border-[var(--vscode-dropdown-border)] my-1" />
          
          {/* Manage Models */}
          <button
            onClick={() => {
              console.log('Opening model settings...');
              // TODO: Open Settings → Providers
              setIsOpen(false);
            }}
            className="w-full flex items-center gap-2 px-3 py-2 text-xs text-left hover:bg-[var(--vscode-list-hoverBackground)] text-[var(--vscode-foreground)] rounded-b-md transition-colors"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span>Manage Models…</span>
          </button>
        </div>
      )}

      {/* Click outside to close */}
      {isOpen && (
        <div 
          className="fixed inset-0 z-40" 
          onClick={() => setIsOpen(false)}
        />
      )}
    </div>
  );
}