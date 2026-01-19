// frontend/src/components/navi/AttachmentToolbar.tsx

import React, { useState, useRef, useEffect } from "react";
import {
  FileText,
  Paperclip,
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

  const attachmentOptions: AttachmentOption[] = [
    {
      id: 'selection',
      icon: <SquareDashedMousePointer className="h-4 w-4" />,
      label: 'Selection',
      description: 'Attach selected text from editor',
      action: handleSelection,
      shortcut: '⌘⇧S'
    },
    {
      id: 'current-file',
      icon: <FileText className="h-4 w-4" />,
      label: 'Current File',
      description: 'Attach the active file',
      action: handleCurrentFile,
      shortcut: '⌘⇧F'
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
      {/* Main attachment button with popup - using Paperclip icon */}
      <div className="navi-attachment-menu-container">
        <button
          ref={buttonRef}
          type="button"
          className={`navi-attachment-icon navi-icon-button navi-attachment-main-btn ${menuOpen ? 'is-active' : ''}`}
          onClick={() => setMenuOpen(!menuOpen)}
          title="Add context (files, images, URLs)"
          aria-label="Open attachments menu"
          aria-expanded={menuOpen}
        >
          <Paperclip className={`h-4 w-4 navi-icon-3d transition-transform duration-200 ${menuOpen ? 'rotate-12' : ''}`} />
        </button>

        {/* Popup menu */}
        {menuOpen && (
          <>
            <div className="navi-attachment-backdrop" onClick={() => setMenuOpen(false)} />
            <div ref={menuRef} className="navi-attachment-menu">
              <div className="navi-attachment-menu-header">
                <span className="navi-attachment-menu-title">Add Context</span>
                <span className="navi-attachment-menu-hint">Attach files, media, or code</span>
              </div>
              <div className="navi-attachment-menu-grid">
                {attachmentOptions.map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    className="navi-attachment-option"
                    onClick={option.action}
                  >
                    <div className="navi-attachment-option-icon">{option.icon}</div>
                    <div className="navi-attachment-option-content">
                      <span className="navi-attachment-option-label">{option.label}</span>
                      <span className="navi-attachment-option-desc">{option.description}</span>
                    </div>
                    {option.shortcut && (
                      <kbd className="navi-attachment-option-shortcut">{option.shortcut}</kbd>
                    )}
                  </button>
                ))}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Quick access button for current file */}
      <button
        type="button"
        className="navi-attachment-icon navi-icon-button"
        onClick={handleCurrentFile}
        title="Attach current file"
        aria-label="Attach current file"
      >
        <FileText className="h-4 w-4 navi-icon-3d" />
      </button>
    </div>
  );
};
