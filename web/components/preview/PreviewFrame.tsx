/**
 * PreviewFrame - Iframe wrapper for preview content
 *
 * Supports:
 * - Static HTML via srcDoc
 * - URLs via src
 * - Loading states
 * - Error handling
 *
 * Security:
 * - sandbox="allow-scripts" (NO allow-same-origin for XSS protection)
 * - referrerPolicy="no-referrer"
 */

import React, { useState } from 'react';

interface PreviewFrameProps {
  src?: string;
  srcDoc?: string;
  className?: string;
}

export function PreviewFrame({ src, srcDoc, className = '' }: PreviewFrameProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);

  const handleLoad = () => {
    setIsLoading(false);
    setHasError(false);
  };

  const handleError = () => {
    setIsLoading(false);
    setHasError(true);
  };

  return (
    <div className={`relative w-full h-full ${className}`}>
      {/* Loading State */}
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-50">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4" />
            <p className="text-sm text-gray-600">Loading preview...</p>
          </div>
        </div>
      )}

      {/* Error State */}
      {hasError && !isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-red-50">
          <div className="text-center p-6">
            <svg className="w-16 h-16 text-red-500 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <h3 className="text-lg font-medium text-red-900 mb-2">Preview Failed</h3>
            <p className="text-sm text-red-700">Unable to load preview content</p>
          </div>
        </div>
      )}

      {/* Preview Iframe */}
      <iframe
        src={src}
        srcDoc={srcDoc}
        sandbox="allow-scripts"  // NO allow-same-origin for security (prevents XSS data exfiltration)
        referrerPolicy="no-referrer"
        className="w-full h-full border-0"
        onLoad={handleLoad}
        onError={handleError}
        title="Preview"
      />
    </div>
  );
}
