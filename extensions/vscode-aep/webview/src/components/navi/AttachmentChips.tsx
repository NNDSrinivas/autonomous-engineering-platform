// frontend/src/components/navi/AttachmentChips.tsx
import React from "react";
import { Paperclip, X, Image } from "lucide-react";
import "./NaviChatPanel.css";

export interface AttachmentChipData {
  id?: string;
  kind: string;          // "selection" | "file" | "local_file" | "image" | ...
  path?: string;
  label?: string;
  language?: string;
  content?: string;      // For images, this is base64 data URL
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
    case "image":
      return "(image)";
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
        const isImage = att.kind === 'image';
        // Use label if set, otherwise create from path + kind
        const text = att.label ||
          (att.path ? `${basename(att.path)} ${formatSuffix(att)}` : "Attachment");

        return (
          <div
            key={att.id ?? `${att.kind}-${index}`}
            className={`navi-attachment-chip ${isImage ? 'navi-attachment-chip--image' : ''}`}
            data-testid="attachment-item"
          >
            {isImage && att.content ? (
              <img
                src={att.content}
                alt={text}
                className="navi-attachment-chip-preview"
              />
            ) : (
              <span className="navi-attachment-chip-icon" aria-hidden="true">
                {isImage ? (
                  <Image className="h-3.5 w-3.5 navi-icon-3d" />
                ) : (
                  <Paperclip className="h-3.5 w-3.5 navi-icon-3d" />
                )}
              </span>
            )}
            <span className="navi-attachment-chip-label" data-testid="attachment-name">
              {text}
            </span>
            {onRemove && (
              <button
                type="button"
                className="navi-chat-attachment-remove navi-icon-button"
                onClick={() => onRemove(index)}
                title="Remove attachment"
                data-testid="remove-attachment-btn"
              >
                <X className="h-3.5 w-3.5 navi-icon-3d" />
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
};
