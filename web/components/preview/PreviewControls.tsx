/**
 * PreviewControls - Preview toolbar with actions
 *
 * Actions:
 * - Refresh preview
 * - Open in new tab
 * - Device size selector (mobile/tablet/desktop)
 * - Toggle visibility
 * - Copy preview URL
 */

import React, { useState } from 'react';

interface PreviewControlsProps {
  previewUrl?: string;
  onRefresh: () => void;
  onToggleVisibility: () => void;
  visible: boolean;
}

type DeviceSize = 'mobile' | 'tablet' | 'desktop';

export function PreviewControls({
  previewUrl,
  onRefresh,
  onToggleVisibility,
  visible,
}: PreviewControlsProps) {
  // Phase 1: Device size selector is visual-only (UI feedback)
  // Phase 2: Will implement actual iframe resizing with width constraints
  const [deviceSize, setDeviceSize] = useState<DeviceSize>('desktop');
  const [copied, setCopied] = useState(false);

  const handleOpenNewTab = () => {
    if (!previewUrl) return;

    // Validate URL using allowlist approach - only allow safe schemes and same-origin
    // Relative paths (starting with /) are safe
    if (previewUrl.startsWith('/')) {
      window.open(previewUrl, '_blank', 'noopener,noreferrer');
      return;
    }

    // For absolute URLs, parse and validate the protocol AND hostname
    try {
      const url = new URL(previewUrl);
      const allowedProtocols = ['http:', 'https:'];

      if (!allowedProtocols.includes(url.protocol)) {
        console.error('Preview URL must use http or https protocol');
        return;
      }

      // Only allow same-origin URLs (prevent open redirect to arbitrary domains)
      if (url.origin !== window.location.origin) {
        console.error('Preview URL must be same-origin (relative paths only)');
        return;
      }

      window.open(previewUrl, '_blank', 'noopener,noreferrer');
    } catch (err) {
      console.error('Invalid preview URL:', err);
    }
  };

  const handleCopyUrl = async () => {
    if (!previewUrl) return;

    try {
      // Build absolute URL correctly - handle both relative and absolute URLs
      const absoluteUrl = previewUrl.startsWith('/')
        ? window.location.origin + previewUrl
        : previewUrl;

      await navigator.clipboard.writeText(absoluteUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy URL:', err);
    }
  };

  return (
    <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b border-gray-200">
      {/* Left: Device Selector */}
      <div className="flex items-center space-x-2">
        <button
          onClick={() => setDeviceSize('mobile')}
          className={`px-3 py-1 text-xs rounded transition-colors ${
            deviceSize === 'mobile'
              ? 'bg-blue-600 text-white'
              : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
          }`}
          title="Mobile (375px)"
        >
          📱 Mobile
        </button>
        <button
          onClick={() => setDeviceSize('tablet')}
          className={`px-3 py-1 text-xs rounded transition-colors ${
            deviceSize === 'tablet'
              ? 'bg-blue-600 text-white'
              : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
          }`}
          title="Tablet (768px)"
        >
          📱 Tablet
        </button>
        <button
          onClick={() => setDeviceSize('desktop')}
          className={`px-3 py-1 text-xs rounded transition-colors ${
            deviceSize === 'desktop'
              ? 'bg-blue-600 text-white'
              : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
          }`}
          title="Desktop (100%)"
        >
          🖥️ Desktop
        </button>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center space-x-2">
        {/* Refresh */}
        <button
          onClick={onRefresh}
          className="px-3 py-1 text-xs bg-white border border-gray-300 rounded hover:bg-gray-50 transition-colors"
          title="Refresh preview"
        >
          🔄 Refresh
        </button>

        {/* Open in new tab */}
        {previewUrl && (
          <button
            onClick={handleOpenNewTab}
            className="px-3 py-1 text-xs bg-white border border-gray-300 rounded hover:bg-gray-50 transition-colors"
            title="Open in new tab"
          >
            ↗️ Open
          </button>
        )}

        {/* Copy URL */}
        {previewUrl && (
          <button
            onClick={handleCopyUrl}
            className="px-3 py-1 text-xs bg-white border border-gray-300 rounded hover:bg-gray-50 transition-colors"
            title="Copy preview URL"
          >
            {copied ? '✅ Copied' : '📋 Copy URL'}
          </button>
        )}

        {/* Toggle visibility */}
        <button
          onClick={onToggleVisibility}
          className="px-3 py-1 text-xs bg-white border border-gray-300 rounded hover:bg-gray-50 transition-colors"
          title={visible ? 'Hide preview' : 'Show preview'}
        >
          {visible ? '👁️ Hide' : '👁️ Show'}
        </button>
      </div>
    </div>
  );
}
