import React, { useState, useEffect } from "react";

interface ExplainModalProps {
  hunkId: string;
  filePath: string;
  onClose: () => void;
  onExplain: (hunkId: string, filePath: string, onMessage: (msg: string) => void) => void;
}

export default function ExplainModal({ hunkId, filePath, onClose, onExplain }: ExplainModalProps) {
  const [text, setText] = useState("Loading explanation...");

  useEffect(() => {
    onExplain(hunkId, filePath, (msg) => {
      setText(msg);
    });
  }, [hunkId, filePath, onExplain]);

  return (
    <div className="modal-bg">
      <div className="modal">
        <h3>Explanation</h3>

        <pre>{text}</pre>

        <button onClick={onClose}>Close</button>
      </div>
    </div>
  );
}
