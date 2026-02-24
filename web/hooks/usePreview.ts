/**
 * usePreview - Preview state management hook
 *
 * Manages preview pane visibility and content (HTML or URL)
 */

import { useState, useCallback } from 'react';

export interface PreviewState {
  url: string | null;
  html: string | null;
  type: 'url' | 'html' | null;
  visible: boolean;
}

export function usePreview() {
  const [state, setState] = useState<PreviewState>({
    url: null,
    html: null,
    type: null,
    visible: false,
  });

  const setPreviewUrl = useCallback((url: string) => {
    setState({
      url,
      html: null,
      type: 'url',
      visible: true,
    });
  }, []);

  const setPreviewHtml = useCallback((html: string) => {
    setState({
      url: null,
      html,
      type: 'html',
      visible: true,
    });
  }, []);

  const clearPreview = useCallback(() => {
    setState({
      url: null,
      html: null,
      type: null,
      visible: false,
    });
  }, []);

  const toggleVisibility = useCallback(() => {
    setState((prev) => ({
      ...prev,
      visible: !prev.visible,
    }));
  }, []);

  return {
    ...state,
    setPreviewUrl,
    setPreviewHtml,
    clearPreview,
    toggleVisibility,
  };
}
