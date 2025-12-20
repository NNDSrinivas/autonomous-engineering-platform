import { useState, useEffect, useRef } from 'react';
import { resolveBackendBase } from '../api/navi/client';

export interface ReviewEntry {
  filePath: string;
  baseContent: string;
  updatedContent: string;
  issues: Array<{
    id: string;
    title: string;
    description: string;
    severity: 'low' | 'medium' | 'high';
    canAutoFix: boolean;
    fixId?: string;
  }>;
  severity: 'low' | 'medium' | 'high';
}

export interface ReviewStreamState {
  isStreaming: boolean;
  currentStep: string;
  entries: ReviewEntry[];
  error: string | null;
  isComplete: boolean;
}

export function useReviewStream(apiBaseUrl?: string) {
  const [state, setState] = useState<ReviewStreamState>({
    isStreaming: false,
    currentStep: '',
    entries: [],
    error: null,
    isComplete: false,
  });
  
  const eventSourceRef = useRef<EventSource | null>(null);

  const startReview = () => {
    if (state.isStreaming) return;
    
    const baseUrl = apiBaseUrl || resolveBackendBase();

    // Reset state
    setState({
      isStreaming: true,
      currentStep: 'Connecting...',
      entries: [],
      error: null,
      isComplete: false,
    });

    // Create EventSource connection
    const eventSource = new EventSource(`${baseUrl}/api/navi/repo/review/stream`);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        switch (data.kind) {
          case 'liveProgress':
            setState(prev => ({
              ...prev,
              currentStep: data.step,
            }));
            break;
            
          case 'reviewEntry':
            setState(prev => ({
              ...prev,
              entries: [...prev.entries, data.entry],
            }));
            break;
            
          case 'done':
            setState(prev => ({
              ...prev,
              isStreaming: false,
              isComplete: true,
              currentStep: 'Review complete!',
            }));
            eventSource.close();
            break;
            
          case 'error':
            setState(prev => ({
              ...prev,
              isStreaming: false,
              error: data.message || 'Unknown error occurred',
            }));
            eventSource.close();
            break;
        }
      } catch (err) {
        console.error('Failed to parse SSE event:', err);
        setState(prev => ({
          ...prev,
          error: 'Failed to parse server response',
        }));
      }
    };

    eventSource.onerror = (error) => {
      console.error('EventSource error:', error);
      setState(prev => ({
        ...prev,
        isStreaming: false,
        error: 'Connection error - check if backend is running',
      }));
      eventSource.close();
    };
  };

  const stopReview = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setState(prev => ({
      ...prev,
      isStreaming: false,
    }));
  };

  const resetReview = () => {
    stopReview();
    setState({
      isStreaming: false,
      currentStep: '',
      entries: [],
      error: null,
      isComplete: false,
    });
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  return {
    ...state,
    startReview,
    stopReview,
    resetReview,
  };
}
