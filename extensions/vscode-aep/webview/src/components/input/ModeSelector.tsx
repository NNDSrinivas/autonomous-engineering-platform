import React, { useState } from 'react';

export type Mode = 'agent' | 'plan' | 'ask' | 'edit';

interface ModeSelectorProps {
  value: Mode;
  onChange: (mode: Mode) => void;
}

/**
 * ModeSelector - Copilot-style mode dropdown
 * 
 * Phase 4.0 UI Parity:
 * - Dropdown style matching Copilot
 * - Clear mode icons and labels  
 * - Proper state management
 */
export function ModeSelector({ value, onChange }: ModeSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);

  const modes: Array<{ id: Mode; label: string }> = [
    { id: 'agent', label: 'Agent' },
    { id: 'plan', label: 'Plan' }, 
    { id: 'ask', label: 'Ask' },
    { id: 'edit', label: 'Edit' },
  ];

  const currentMode = modes.find(m => m.id === value) || modes[0];

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1.5 px-2 py-1 h-[28px] text-xs bg-[var(--vscode-input-background)] border border-[var(--vscode-input-border)] rounded-md hover:border-[var(--vscode-focusBorder)] transition-colors min-w-[70px]"
      >
        <span className="font-medium text-[var(--vscode-foreground)] text-xs">{currentMode.label}</span>
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
        <div className="absolute bottom-full mb-1 left-0 min-w-[90px] bg-[var(--vscode-dropdown-background)] border border-[var(--vscode-dropdown-border)] rounded-md shadow-lg z-50">
          {modes.map((mode) => (
            <button
              key={mode.id}
              onClick={() => {
                onChange(mode.id);
                setIsOpen(false);
              }}
              className={`w-full flex items-center gap-1.5 px-2 py-1.5 text-xs text-left hover:bg-[var(--vscode-list-hoverBackground)] first:rounded-t-md last:rounded-b-md ${
                value === mode.id ? 'bg-[var(--vscode-list-activeSelectionBackground)] text-[var(--vscode-list-activeSelectionForeground)]' : 'text-[var(--vscode-foreground)]'
              }`}
            >
              <span className="text-xs">{mode.label}</span>
              {value === mode.id && (
                <svg className="w-2.5 h-2.5 ml-auto" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
              )}
            </button>
          ))}
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