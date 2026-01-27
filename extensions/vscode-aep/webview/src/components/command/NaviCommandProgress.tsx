/**
 * NaviCommandProgress - Animated progress bar with particle trail effect
 *
 * Features:
 * - Gradient fill (purple to cyan)
 * - Glowing particle at the progress head
 * - Shimmer effect during execution
 * - Elapsed time display (optional)
 */

import React from 'react';

interface NaviCommandProgressProps {
  /** Progress percentage (0-100), or undefined for indeterminate */
  percent?: number;
  /** Whether the command is actively running */
  isActive?: boolean;
  /** Elapsed time in milliseconds */
  elapsedMs?: number;
  /** Show time label */
  showTime?: boolean;
}

export const NaviCommandProgress: React.FC<NaviCommandProgressProps> = ({
  percent,
  isActive = true,
  elapsedMs,
  showTime = false,
}) => {
  // For indeterminate progress, use a pulsing animation
  const isIndeterminate = percent === undefined;

  // Format elapsed time
  const formatTime = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
  };

  return (
    <div
      className={`navi-command-progress ${isActive ? 'navi-command-progress--active' : ''} ${isIndeterminate ? 'navi-command-progress--indeterminate' : ''}`}
    >
      <div className="navi-command-progress__track">
        <div
          className="navi-command-progress__fill"
          style={{
            width: isIndeterminate ? '30%' : `${Math.min(100, Math.max(0, percent || 0))}%`,
          }}
        />
      </div>
      {showTime && elapsedMs !== undefined && (
        <span className="navi-command-progress__time">
          {formatTime(elapsedMs)}
        </span>
      )}
    </div>
  );
};

export default NaviCommandProgress;
