import React, { useState } from "react";
import { useVSCodeAPI } from "../hooks/useVSCodeAPI";

type Props = {
  filePath: string;
  fixId: string;
};

export default function AutoFixButton({ filePath, fixId }: Props) {
  const vscode = useVSCodeAPI();
  const [loading, setLoading] = useState(false);

  const applyFix = () => {
    setLoading(true);
    vscode.postMessage({
      type: "aep.fix.apply",
      payload: { filePath, fixId },
    });
  };

  return (
    <button
      onClick={applyFix}
      disabled={loading}
      className="mt-2 px-3 py-1.5 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 disabled:opacity-50"
    >
      {loading ? "Applying…" : "Auto-fix via Navi"}
    </button>
  );
}