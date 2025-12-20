import { useEffect, useState, useCallback, useRef } from "react";
import { useVSCodeAPI } from "./useVSCodeAPI";

export interface ReviewEntry {
  id: string;
  file?: string;
  line?: number;
  severity: 'error' | 'warning' | 'info' | 'suggestion' | 'low' | 'medium' | 'high';
  title?: string;
  description?: string;
  suggestion?: string;
  diff?: string;
  canAutoFix: boolean;
  issues?: Array<{
    id?: string;
    title?: string;
    description?: string;
    severity?: string;
    canAutoFix?: boolean;
    fixId?: string;
  }>;
}

export interface StreamError {
  message: string;
  code?: string;
  timestamp: number;
}

export interface StreamStatus {
  connected: boolean;
  streaming: boolean;
  error?: StreamError;
  retryCount: number;
  lastHeartbeat?: number;
}

export function useReviewStream() {
  const vscode = useVSCodeAPI();
  const [progress, setProgress] = useState<string | null>(null);
  const [progressPercentage, setProgressPercentage] = useState<number>(0);
  const [entries, setEntries] = useState<ReviewEntry[]>([]);
  const [done, setDone] = useState(false);
  const [summary, setSummary] = useState<any | null>(null);
  const [status, setStatus] = useState<StreamStatus>({
    connected: false,
    streaming: false,
    retryCount: 0
  });
  const [metrics, setMetrics] = useState({
    totalFiles: 0,
    processedFiles: 0,
    issuesFound: 0,
    startTime: null as number | null,
    endTime: null as number | null
  });
  
  const heartbeatRef = useRef<NodeJS.Timeout | null>(null);
  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const resetState = useCallback(() => {
    setProgress(null);
    setProgressPercentage(0);
    setEntries([]);
    setDone(false);
    setSummary(null);
    setMetrics({
      totalFiles: 0,
      processedFiles: 0,
      issuesFound: 0,
      startTime: null,
      endTime: null
    });
  }, []);

  const startHeartbeat = useCallback(() => {
    if (heartbeatRef.current) clearInterval(heartbeatRef.current);
    heartbeatRef.current = setInterval(() => {
      setStatus(prev => ({
        ...prev,
        lastHeartbeat: Date.now()
      }));
    }, 1000);
  }, []);

  const stopHeartbeat = useCallback(() => {
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }
  }, []);

  const handleRetry = useCallback(() => {
    setStatus(prev => ({
      ...prev,
      retryCount: prev.retryCount + 1,
      error: undefined
    }));
    
    // Request reconnection through extension
    vscode.postMessage({ 
      type: "aep.stream.retry",
      retryCount: status.retryCount + 1
    });
  }, [vscode, status.retryCount]);

  const startReview = useCallback(() => {
    resetState();
    setStatus({
      connected: true,
      streaming: true,
      retryCount: 0
    });
    setMetrics(prev => ({ ...prev, startTime: Date.now() }));
    startHeartbeat();
    
    vscode.postMessage({ type: "aep.review.start" });
  }, [vscode, resetState, startHeartbeat]);

  const stopReview = useCallback(() => {
    setStatus(prev => ({ ...prev, streaming: false }));
    stopHeartbeat();
    
    vscode.postMessage({ type: "aep.review.stop" });
  }, [vscode, stopHeartbeat]);

  useEffect(() => {
    const handler = (event: MessageEvent) => {
      const msg = event.data;

      switch (msg.type) {
        case "review.connected":
          setStatus(prev => ({
            ...prev,
            connected: true,
            error: undefined
          }));
          break;

        case "review.disconnected":
          setStatus(prev => ({
            ...prev,
      connected: false,
      streaming: false
    }));
    stopHeartbeat();
    break;

        case "review.summary":
          setSummary(msg.summary || null);
          if (msg.summary?.totalFiles) {
            setMetrics(prev => ({
              ...prev,
              totalFiles: msg.summary.totalFiles,
              processedFiles: msg.summary.listedFiles?.length ?? prev.processedFiles
            }));
          }
          break;

        case "review.progress":
          setProgress(msg.text);
          if (msg.percentage !== undefined) {
            setProgressPercentage(msg.percentage);
          }
          if (msg.totalFiles) {
            setMetrics(prev => ({ 
              ...prev, 
              totalFiles: msg.totalFiles,
              processedFiles: msg.processedFiles || prev.processedFiles
            }));
          }
          break;

        case "review.entry":
          const entry: ReviewEntry = {
            id: msg.entry.id || `entry-${Date.now()}-${Math.random()}`,
            file: msg.entry.file,
            line: msg.entry.line,
            severity: msg.entry.severity || 'info',
            title: msg.entry.title,
            description: msg.entry.description,
            suggestion: msg.entry.suggestion,
            diff: msg.entry.diff,
            canAutoFix: msg.entry.canAutoFix || false,
            issues: msg.entry.issues || []
          };
          setEntries(prev => [...prev, entry]);
          setMetrics(prev => ({ 
            ...prev, 
            issuesFound: prev.issuesFound + (entry.issues?.length || 1)
          }));
          break;

        case "review.done":
          setDone(true);
          setProgress("Review completed");
          setProgressPercentage(100);
          setStatus(prev => ({ ...prev, streaming: false }));
          setMetrics(prev => ({ ...prev, endTime: Date.now() }));
          if (msg.summary) {
            setSummary(msg.summary);
          }
          if (msg.entries && msg.entries.length) {
            setEntries(prev => prev.length ? prev : msg.entries);
          }
          stopHeartbeat();
          break;

        case "review.error":
          const error: StreamError = {
            message: msg.message || "Stream error occurred",
            code: msg.code,
            timestamp: Date.now()
          };
          setStatus(prev => ({
            ...prev,
            streaming: false,
            error
          }));
          setProgress(`Error: ${error.message}`);
          stopHeartbeat();
          
          // Auto-retry on connection errors
          if (msg.code === 'CONNECTION_LOST' && status.retryCount < 3) {
            retryTimeoutRef.current = setTimeout(() => {
              handleRetry();
            }, Math.pow(2, status.retryCount) * 1000); // Exponential backoff
          }
          break;

        case "review.heartbeat":
          setStatus(prev => ({
            ...prev,
            lastHeartbeat: Date.now()
          }));
          break;

        default:
          break;
      }
    };

    window.addEventListener("message", handler);
    return () => {
      window.removeEventListener("message", handler);
      stopHeartbeat();
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
      }
    };
  }, [stopHeartbeat, handleRetry, status.retryCount]);

  return { 
    progress, 
    progressPercentage,
    entries, 
    done, 
    summary,
    status,
    metrics,
    actions: {
      startReview,
      stopReview,
      retry: handleRetry,
      reset: resetState
    }
  };
}
