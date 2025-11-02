import { useEffect, useState, useRef } from "react";

export type ConnectionStatus = "connected" | "connecting" | "disconnected";

export function useConnection() {
  const [online, setOnline] = useState(navigator.onLine);
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const mountedRef = useRef(true);

  useEffect(() => {
    const handleOnline = () => {
      if (mountedRef.current) setOnline(true);
    };
    const handleOffline = () => {
      if (mountedRef.current) setOnline(false);
    };
    
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    
    return () => { 
      mountedRef.current = false;
      window.removeEventListener("online", handleOnline); 
      window.removeEventListener("offline", handleOffline); 
    };
  }, []);

  useEffect(() => {
    const handleStreamOpen = () => {
      if (mountedRef.current) setStatus("connected");
    };
    const handleStreamError = () => {
      if (mountedRef.current) setStatus("disconnected");
    };
    
    window.addEventListener("aep-stream-open", handleStreamOpen);
    window.addEventListener("aep-stream-error", handleStreamError);
    
    return () => {
      mountedRef.current = false;
      window.removeEventListener("aep-stream-open", handleStreamOpen);
      window.removeEventListener("aep-stream-error", handleStreamError);
    };
  }, []);

  // Auto-reset to connecting when coming back online
  useEffect(() => {
    if (mountedRef.current && online && status === "disconnected") {
      setStatus("connecting");
    }
  }, [online, status]);

  return { online, status, setStatus };
}