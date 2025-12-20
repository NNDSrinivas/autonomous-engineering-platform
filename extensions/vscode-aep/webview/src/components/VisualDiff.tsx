import React, { useState } from "react";
import clsx from "clsx";
import "../prism-theme.css";

type Props = {
  diff: string;
};

export default function VisualDiff({ diff }: Props) {
  const [open, setOpen] = useState(true);

  if (!diff) {
    return (
      <div className="text-xs text-gray-500 italic">
        (No diff available)
      </div>
    );
  }

  const lines = diff.split("\n");

  return (
    <div className="border rounded bg-gray-900 text-gray-100 font-mono text-xs">
      <button
        onClick={() => setOpen(!open)}
        className="w-full text-left px-3 py-1 bg-gray-800 hover:bg-gray-700 flex justify-between"
      >
        <span>Changes</span>
        <span>{open ? "▾" : "▸"}</span>
      </button>

      {open && (
        <pre className="overflow-auto max-h-96 p-3">
          {lines.map((line, idx) => (
            <div
              key={idx}
              className={clsx("whitespace-pre-wrap", {
                "text-green-400": line.startsWith("+"),
                "text-red-400": line.startsWith("-"),
                "text-blue-300": line.startsWith("@@"),
              })}
            >
              {line}
            </div>
          ))}
        </pre>
      )}
    </div>
  );
}