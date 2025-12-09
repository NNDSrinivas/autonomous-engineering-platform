import React from "react";

interface NaviCheckErrorsAndFixPanelProps {
  onCheck?: () => void;
  onFix?: () => void;
}

export const NaviCheckErrorsAndFixPanel: React.FC<
  NaviCheckErrorsAndFixPanelProps
> = ({ onCheck, onFix }) => {
  return (
    <div className="navi-errors-panel">
      <button onClick={onCheck}>Check Errors</button>
      <button onClick={onFix}>Fix Issues</button>
    </div>
  );
};
