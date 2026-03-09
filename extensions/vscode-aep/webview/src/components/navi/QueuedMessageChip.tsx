import React from 'react';
import { X, Zap } from 'lucide-react';

interface QueuedMessage {
  id: string;
  text: string;
  createdAt: string;
}

interface Props {
  message: QueuedMessage;
  position: number;
  onSendNow: (id: string) => void;
  onRemove: (id: string) => void;
}

export const QueuedMessageChip: React.FC<Props> = ({
  message,
  position,
  onSendNow,
  onRemove,
}) => {
  return (
    <div className="navi-queue-chip">
      <span className="navi-queue-chip-index" aria-hidden>
        {position + 1}
      </span>
      <span className="navi-queue-chip-text" title={message.text}>
        {message.text}
      </span>
      <div className="navi-queue-chip-actions">
        <button
          onClick={() => onSendNow(message.id)}
          className="navi-queue-chip-send"
          title="Cancel current and send now"
          type="button"
        >
          <Zap size={11} />
          <span>Now</span>
        </button>
        <button
          onClick={() => onRemove(message.id)}
          className="navi-queue-chip-remove"
          title="Remove"
          aria-label="Remove queued message"
          type="button"
        >
          <X size={12} />
        </button>
      </div>
    </div>
  );
};
