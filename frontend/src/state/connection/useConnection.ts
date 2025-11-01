import { useEffect, useState } from "react";

export type ConnectionStatus = "connected" | "connecting" | "disconnected";

export function useConnection() {
  const [online, setOnline] = useState(navigator.onLine);
  const [status, setStatus] = useState<ConnectionStatus>("connecting");

  useEffect(() => {
    const handleOnline = () => setOnline(true);
    const handleOffline = () => setOnline(false);
    
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    
    return () => { 
      window.removeEventListener("online", handleOnline); 
      window.removeEventListener("offline", handleOffline); 
    };
  }, []);

  useEffect(() => {
    const handleStreamOpen = () => setStatus("connected");
    const handleStreamError = () => setStatus("disconnected");
    
    window.addEventListener("aep-stream-open", handleStreamOpen);
    window.addEventListener("aep-stream-error", handleStreamError);
    
    return () => {
      window.removeEventListener("aep-stream-open", handleStreamOpen);
      window.removeEventListener("aep-stream-error", handleStreamError);
    };
  }, []);

  // Auto-reset to connecting when coming back online
  useEffect(() => {
    if (online && status === "disconnected") {
      setStatus("connecting");
    }
  }, [online, status]);

  return { online, status, setStatus };
}