import React from 'react';

export function installIdleHooks(onIdle: () => void, onActive: () => void, idleMs = 30000) {
  let timer: number | null = null;
  let isIdle = false;

  const reset = () => {
    if (timer) clearTimeout(timer);
    
    // Only call onActive if we were previously idle
    if (isIdle) {
      isIdle = false;
      onActive();
    }
    
    timer = window.setTimeout(() => {
      if (!isIdle) {
        isIdle = true;
        onIdle();
      }
    }, idleMs);
  };

  const handleVisibilityChange = () => {
    if (document.visibilityState === "hidden") {
      // Don't reset timer when tab becomes hidden - let it idle
      return;
    } else {
      // Tab became visible again - reset idle timer
      reset();
    }
  };

  const events = ["mousemove", "keydown", "focus"] as const;
  const passiveEvents = { passive: true };

  // Attach event listeners
  events.forEach((evt) => {
    window.addEventListener(evt, reset, passiveEvents);
  });
  
  document.addEventListener("visibilitychange", handleVisibilityChange);

  // Start the timer immediately
  reset();

  // Return cleanup function
  return () => {
    if (timer) clearTimeout(timer);
    events.forEach((evt) => {
      window.removeEventListener(evt, reset);
    });
    document.removeEventListener("visibilitychange", handleVisibilityChange);
  };
}

// Hook version for React components
export function useIdleDetection(
  onIdle: () => void, 
  onActive: () => void, 
  idleMs = 30000
) {
  const onIdleRef = React.useRef(onIdle);
  const onActiveRef = React.useRef(onActive);

  // Update refs to avoid stale closures
  React.useEffect(() => {
    onIdleRef.current = onIdle;
  }, [onIdle]);

  React.useEffect(() => {
    onActiveRef.current = onActive;
  }, [onActive]);

  React.useEffect(() => {
    return installIdleHooks(
      () => onIdleRef.current(),
      () => onActiveRef.current(),
      idleMs
    );
  }, [idleMs]);
}