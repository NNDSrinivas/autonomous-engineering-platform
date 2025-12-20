import React from "react";

interface ToolbarProps {
  viewMode: "split" | "inline";
  setViewMode: (v: "split" | "inline") => void;
}

export default function Toolbar({ viewMode, setViewMode }: ToolbarProps) {
  return (
    <div className="diff-toolbar">
      <button
        className={viewMode === "split" ? "active" : ""}
        onClick={() => setViewMode("split")}
      >
        Split View
      </button>

      <button
        className={viewMode === "inline" ? "active" : ""}
        onClick={() => setViewMode("inline")}
      >
        Inline View
      </button>
    </div>
  );
}