/**
 * NaviStatusRing - Futuristic status indicator for command execution
 *
 * Visual states:
 * - running: Spinning ring with orbiting particle
 * - success: Green circle with morphing checkmark
 * - error: Red pulsing ring with X icon
 */

import React from 'react';

export type CommandStatus = 'running' | 'done' | 'error';

interface NaviStatusRingProps {
  status: CommandStatus;
  size?: 'sm' | 'md' | 'lg';
}

export const NaviStatusRing: React.FC<NaviStatusRingProps> = ({
  status,
  size = 'md'
}) => {
  const sizeClasses = {
    sm: 'navi-status-ring--sm',
    md: 'navi-status-ring--md',
    lg: 'navi-status-ring--lg',
  };

  // Map 'done' to 'success' for CSS class
  const statusClass = status === 'done' ? 'success' : status;

  return (
    <div
      className={`navi-status-ring navi-status-ring--${statusClass} ${sizeClasses[size]}`}
      role="status"
      aria-label={`Command ${status}`}
    >
      {/* The ring and icon are rendered via CSS ::before and ::after */}
    </div>
  );
};

export default NaviStatusRing;
