// frontend/src/components/navi/AttachmentToolbar.tsx

import React from "react";
import * as vscodeApi from "../../utils/vscodeApi";

interface AttachmentToolbarProps {
  className?: string;
}

export const AttachmentToolbar: React.FC<AttachmentToolbarProps> = ({
  className,
}) => {
  const handleSelection = () => {
    vscodeApi.postMessage({ type: 'attachSelection' });
  };

  const handleCurrentFile = () => {
    vscodeApi.postMessage({ type: 'attachCurrentFile' });
  };

  const handleLocalFile = () => {
    vscodeApi.postMessage({ type: 'attachLocalFile' });
  };

  const rootClass = ["navi-attachment-toolbar", className]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={rootClass}>
      <span className="navi-attachment-label">ATTACH:</span>
      <button
        type="button"
        className="navi-pill navi-pill--ghost navi-attachment-btn"
        onClick={handleSelection}
      >
        Selection
      </button>
      <button
        type="button"
        className="navi-pill navi-pill--ghost navi-attachment-btn"
        onClick={handleCurrentFile}
      >
        Current file
      </button>
      <button
        type="button"
        className="navi-pill navi-pill--ghost navi-attachment-btn"
        onClick={handleLocalFile}
        data-testid="attach-file-btn"
      >
        Local file…
      </button>
    </div>
  );
};
