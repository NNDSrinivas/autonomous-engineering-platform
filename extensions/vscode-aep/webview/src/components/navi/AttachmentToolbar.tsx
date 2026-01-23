// frontend/src/components/navi/AttachmentToolbar.tsx

import React, { useState, useRef, useEffect } from "react";
import {
  FileText,
  Paperclip,
  Plus,
  SquareDashedMousePointer,
  Image,
  FolderTree,
  Link,
  Code,
} from "lucide-react";
import * as vscodeApi from "../../utils/vscodeApi";

interface AttachmentToolbarProps {
  className?: string;
}

interface AttachmentOption {
  id: string;
  icon: React.ReactNode;
  label: string;
  description: string;
  action: () => void;
  shortcut?: string;
}

export const AttachmentToolbar: React.FC<AttachmentToolbarProps> = ({
  className,
}) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node) &&
          buttonRef.current && !buttonRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };

    if (menuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [menuOpen]);

  // Close on escape
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMenuOpen(false);
    };
    if (menuOpen) {
      document.addEventListener('keydown', handleEscape);
    }
    return () => document.removeEventListener('keydown', handleEscape);
  }, [menuOpen]);

  const handleSelection = () => {
    vscodeApi.postMessage({ type: 'attachSelection' });
    setMenuOpen(false);
  };

  const handleCurrentFile = () => {
    vscodeApi.postMessage({ type: 'attachCurrentFile' });
    setMenuOpen(false);
  };

  const handleFilesAndFolders = () => {
    vscodeApi.postMessage({ type: 'attachFilesAndFolders' });
    setMenuOpen(false);
  };

  const handleProjectFiles = () => {
    vscodeApi.postMessage({ type: 'attachProjectFiles' });
    setMenuOpen(false);
  };

  const handleMedia = () => {
    vscodeApi.postMessage({ type: 'attachMedia' });
    setMenuOpen(false);
  };

  const handleUrl = () => {
    vscodeApi.postMessage({ type: 'attachUrl' });
    setMenuOpen(false);
  };

  const handleCodeSnippet = () => {
    vscodeApi.postMessage({ type: 'attachCodeSnippet' });
    setMenuOpen(false);
  };

  // Reordered: Most common actions first
  const attachmentOptions: AttachmentOption[] = [
    {
      id: 'current-file',
      icon: <FileText className="h-4 w-4" />,
      label: 'Current File',
      description: 'Attach the active file',
      action: handleCurrentFile,
      shortcut: '⌘⇧F'
    },
    {
      id: 'selection',
      icon: <SquareDashedMousePointer className="h-4 w-4" />,
      label: 'Selection',
      description: 'Attach selected text from editor',
      action: handleSelection,
      shortcut: '⌘⇧S'
    },
    {
      id: 'files-folders',
      icon: <Paperclip className="h-4 w-4" />,
      label: 'Files & Folders',
      description: 'Browse and attach files or folders',
      action: handleFilesAndFolders,
      shortcut: '⌘⇧A'
    },
    {
      id: 'project-files',
      icon: <FolderTree className="h-4 w-4" />,
      label: 'Project Files',
      description: 'Quick-add multiple project files',
      action: handleProjectFiles,
    },
    {
      id: 'media',
      icon: <Image className="h-4 w-4" />,
      label: 'Images & Video',
      description: 'Attach screenshots, images, or recordings',
      action: handleMedia,
    },
    {
      id: 'url',
      icon: <Link className="h-4 w-4" />,
      label: 'URL',
      description: 'Fetch and attach web content',
      action: handleUrl,
    },
    {
      id: 'code',
      icon: <Code className="h-4 w-4" />,
      label: 'Code Snippet',
      description: 'Attach a code snippet',
      action: handleCodeSnippet,
    },
  ];

  const rootClass = ["navi-attachment-toolbar", className]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={rootClass}>
      {/* Single compact "+" button that opens attachment menu */}
      <div className="navi-attachment-menu-container">
        <button
          ref={buttonRef}
          type="button"
          className={`navi-attachment-plus-btn ${menuOpen ? 'is-active' : ''}`}
          onClick={() => setMenuOpen(!menuOpen)}
          title="Add context (files, images, URLs)"
          aria-label="Open attachments menu"
          aria-expanded={menuOpen}
        >
          <Plus className="h-4 w-4" />
        </button>

        {/* Popup menu - positioned above button */}
        {menuOpen && (
          <>
            <div className="navi-attachment-backdrop" onClick={() => setMenuOpen(false)} />
            <div ref={menuRef} className="navi-attachment-menu navi-attachment-menu--compact">
              <div className="navi-attachment-menu-header">
                <span className="navi-attachment-menu-title">Add Context</span>
              </div>
              <div className="navi-attachment-menu-list">
                {attachmentOptions.map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    className="navi-attachment-menu-item"
                    onClick={option.action}
                  >
                    <span className="navi-attachment-menu-item-icon">{option.icon}</span>
                    <span className="navi-attachment-menu-item-label">{option.label}</span>
                    {option.shortcut && (
                      <kbd className="navi-attachment-menu-item-shortcut">{option.shortcut}</kbd>
                    )}
                  </button>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
