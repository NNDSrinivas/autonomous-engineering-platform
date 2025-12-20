import React from "react";
import "./diff.css";

interface FileTreeProps {
  files: { path: string; hunks: any[] }[];
  selectedFile: string;
  onSelectFile: (filePath: string) => void;
}

export default function FileTree({ files, selectedFile, onSelectFile }: FileTreeProps) {
  return (
    <div className="file-tree">
      {files.map(f => (
        <div
          key={f.path}
          className={
            "file-tree-item " + (selectedFile === f.path ? "file-selected" : "")
          }
          onClick={() => onSelectFile(f.path)}
        >
          <span className="file-name">{f.path}</span>
          <span className="file-hunk-count">{f.hunks.length}</span>
        </div>
      ))}
    </div>
  );
}