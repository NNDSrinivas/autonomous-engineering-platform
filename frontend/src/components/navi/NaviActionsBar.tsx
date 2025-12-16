import React from "react";
import type { NaviAction } from "../../types/naviChat";

interface NaviActionsBarProps {
  actions?: NaviAction[];
  onActionClick?: (actionId: string) => void;
}

export const NaviActionsBar: React.FC<NaviActionsBarProps> = ({
  actions = [],
  onActionClick,
}) => {
  return (
    <div className="navi-actions-bar">
      {actions.map((action) => (
        <button
          key={action.id}
          onClick={() => onActionClick?.(action.id)}
          title={action.description}
        >
          {action.title}
        </button>
      ))}
    </div>
  );
};
