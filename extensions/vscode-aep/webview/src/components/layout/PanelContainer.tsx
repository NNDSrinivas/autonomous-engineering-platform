import React from 'react';

interface PanelContainerProps {
  children: React.ReactNode;
}

/**
 * PanelContainer - Outer shell with VS Code native look
 * 
 * This is the root container that establishes the native IDE feel.
 * Uses VS Code CSS variables for perfect integration.
 */
export function PanelContainer({ children }: PanelContainerProps) {
  return (
    <div className="flex h-full flex-col bg-[var(--vscode-sideBar-background)] text-[var(--vscode-foreground)]">
      {children}
    </div>
  );
}