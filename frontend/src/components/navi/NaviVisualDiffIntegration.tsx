import React from 'react';
import VisualDiffViewer from './ui/VisualDiffViewer';

export interface NaviVisualDiffIntegrationProps {
    isVisible?: boolean;
    className?: string;
}

/**
 * Integration component for the new Visual Diff Viewer with existing NAVI chat system
 */
export function NaviVisualDiffIntegration({
    isVisible = true,
    className = ""
}: NaviVisualDiffIntegrationProps) {
    if (!isVisible) return null;

    return (
        <div className={`navi-visual-diff-integration ${className}`}>
            <VisualDiffViewer />
        </div>
    );
}

export default NaviVisualDiffIntegration;