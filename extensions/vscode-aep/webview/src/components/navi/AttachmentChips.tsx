// frontend/src/components/navi/AttachmentChips.tsx
import React from "react";
import "./NaviChatPanel.css";

export interface AttachmentChipData {
  id?: string;
  kind: string;          // "selection" | "file" | "local_file" | ...
  path?: string;
  label?: string;
  language?: string;
  content?: string;
}

interface AttachmentChipsProps {
  attachments: AttachmentChipData[];
  onRemove?: (index: number) => void;
}

const formatSuffix = (att: AttachmentChipData) => {
  switch (att.kind) {
    case "selection":
      return "(selection)";
    case "local_file":
      return "(local file)";
    default:
      return "(current file)";
  }
};

export const AttachmentChips: React.FC<AttachmentChipsProps> = ({
  attachments,
  onRemove,
}) => {
  if (!attachments || attachments.length === 0) return null;

  const basename = (path: string) => path.split(/[\\/]/).pop() ?? path;

  return (
    <div className="navi-attachments-row">
      {attachments.map((att, index) => {
        // Use label if set, otherwise create from path + kind
        const text = att.label ||
          (att.path ? `${basename(att.path)} ${formatSuffix(att)}` : "Attachment");

        return (
          <div
            key={att.id ?? `${att.kind}-${index}`}
            className="navi-attachment-chip"
            data-testid="attachment-item"
          >
            <span className="navi-attachment-chip-label" data-testid="attachment-name">
              📎 {text}
            </span>
            {onRemove && (
              <button
                type="button"
                className="navi-chat-attachment-remove"
                onClick={() => onRemove(index)}
                title="Remove attachment"
                data-testid="remove-attachment-btn"
              >
                ×
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
};
