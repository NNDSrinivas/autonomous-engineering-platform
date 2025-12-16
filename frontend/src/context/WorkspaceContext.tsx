import React, { createContext, useContext, useEffect, useState } from 'react';

interface WorkspaceContextType {
    workspaceRoot: string | null;
    repoName: string;
    isLoading: boolean;
}

const WorkspaceContext = createContext<WorkspaceContextType | undefined>(undefined);

/**
 * WorkspaceProvider - Extracts workspace root from URL and provides it via React Context
 * This is the single source of truth for workspace context in the entire app
 */
export const WorkspaceProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [workspaceRoot, setWorkspaceRoot] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        // Try to get workspace context from VS Code extension first
        const handleVSCodeMessage = (event: MessageEvent) => {
            if (event.data?.type === 'workspaceContext' || event.data?.type === 'workspaceRoot') {
                console.log('[WorkspaceContext] 🎉 Received from VS Code:', event.data);
                setWorkspaceRoot(event.data.workspaceRoot || null);
                setIsLoading(false);
                return;
            }
        };

        // Listen for VS Code messages
        window.addEventListener('message', handleVSCodeMessage);

        // Request workspace context from VS Code extension
        if ((window as any).acquireVsCodeApi) {
            console.log('[WorkspaceContext] 📡 Requesting workspace context from VS Code');
            const vscode = (window as any).acquireVsCodeApi();
            vscode.postMessage({ type: 'requestWorkspaceContext' });
        } else {
            // Fallback: Extract workspace root from URL query params
            console.log('[WorkspaceContext] 📄 Fallback to URL params');
            const fullUrl = window.location.href;
            const searchString = window.location.search;
            console.log('[WorkspaceContext] 🔍 Full URL:', fullUrl);
            console.log('[WorkspaceContext] 🔍 Search string:', searchString);

            const urlParams = new URLSearchParams(searchString);
            let workspaceFromUrl = urlParams.get('workspaceRoot');

            console.log('[WorkspaceContext] 🔍 Extracted workspaceRoot:', workspaceFromUrl);

            if (workspaceFromUrl && workspaceFromUrl.trim()) {
                setWorkspaceRoot(workspaceFromUrl);
                console.log('[WorkspaceContext] ✅ Workspace root detected:', workspaceFromUrl);
            } else {
                setWorkspaceRoot(null);
                console.log('[WorkspaceContext] ⚠️ No workspace root in URL - will use fallback "this repo"');
            }

            setIsLoading(false);
        }

        return () => {
            window.removeEventListener('message', handleVSCodeMessage);
        };
    }, []);

    // Compute repo name from workspace root
    const repoName = workspaceRoot
        ? workspaceRoot
            .replace(/\\/g, '/')
            .split('/')
            .filter(Boolean)
            .pop() || 'this repo'
        : 'this repo';

    const value: WorkspaceContextType = {
        workspaceRoot,
        repoName,
        isLoading,
    };

    return (
        <WorkspaceContext.Provider value={value}>
            {children}
        </WorkspaceContext.Provider>
    );
};

/**
 * useWorkspace - Hook to access workspace context from any component
 * Replaces scattered getWorkspaceRoot() calls throughout the codebase
 */
export const useWorkspace = () => {
    const context = useContext(WorkspaceContext);
    if (!context) {
        throw new Error('useWorkspace must be used within WorkspaceProvider');
    }
    return context;
};
