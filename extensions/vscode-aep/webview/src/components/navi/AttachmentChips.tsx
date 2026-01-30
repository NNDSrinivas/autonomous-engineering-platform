// frontend/src/components/navi/AttachmentChips.tsx
import React from "react";
import { Paperclip, X, Image, Video, FileText } from "lucide-react";
import "./NaviChatPanel.css";

export interface AttachmentChipData {
  id?: string;
  kind: string;          // "selection" | "file" | "local_file" | "image" | "video" | ...
  path?: string;
  label?: string;
  language?: string;
  content?: string;      // For images, this is base64 data URL; for videos, this is context text
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
    case "video":
      // Check if video has been processed (has transcription/frames)
      if (att.content && att.content.includes("VIDEO ANALYSIS")) {
        return "(video - processed)";
      }
      return "(video)";
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
        const isVideo = att.kind === 'video';
        const isProcessedVideo = isVideo && att.content?.includes('VIDEO ANALYSIS');

        // Use label if set, otherwise create from path + kind
        const text = att.label ||
          (att.path ? `${basename(att.path)} ${formatSuffix(att)}` : "Attachment");

        // Determine CSS class
        let chipClass = 'navi-attachment-chip';
        if (isImage) chipClass += ' navi-attachment-chip--image';
        if (isVideo) chipClass += ' navi-attachment-chip--video';
        if (isProcessedVideo) chipClass += ' navi-attachment-chip--processed';

        return (
          <div
            key={att.id ?? `${att.kind}-${index}`}
            className={chipClass}
            data-testid="attachment-item"
            title={isProcessedVideo ? 'Video processed with transcription and frames' : undefined}
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
                ) : isVideo ? (
                  <Video className="h-3.5 w-3.5 navi-icon-3d" />
                ) : (
                  <Paperclip className="h-3.5 w-3.5 navi-icon-3d" />
                )}
              </span>
            )}
            <span className="navi-attachment-chip-label" data-testid="attachment-name">
              {text}
            </span>
            {isProcessedVideo && (
              <span className="navi-attachment-chip-badge" title="Transcription + frames extracted">
                <FileText className="h-2.5 w-2.5" />
              </span>
            )}
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
