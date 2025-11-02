import React from 'react';

export function installIdleHooks(onIdle: () => void, onActive: () => void, idleMs = 30000) {
  let timer: number | null = null;
  let isIdle = false;
  let throttleTimer: number | null = null;

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

  // Throttled version of reset for high-frequency events like mousemove
  const throttledReset = () => {
    if (throttleTimer) return; // Already throttled
    
    reset();
    throttleTimer = window.setTimeout(() => {
      throttleTimer = null;
    }, 100); // Throttle to once per 100ms
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

  const events = ["keydown", "focus"] as const;
  const passiveEvents = { passive: true };

  // Attach event listeners - use throttled reset for mousemove
  events.forEach((evt) => {
    window.addEventListener(evt, reset, passiveEvents);
  });
  
  // Use throttled reset for high-frequency mousemove events
  window.addEventListener("mousemove", throttledReset, passiveEvents);
  
  document.addEventListener("visibilitychange", handleVisibilityChange);

  // Start the timer immediately
  reset();

  // Return cleanup function
  return () => {
    if (timer) clearTimeout(timer);
    if (throttleTimer) clearTimeout(throttleTimer);
    events.forEach((evt) => {
      window.removeEventListener(evt, reset);
    });
    window.removeEventListener("mousemove", throttledReset);
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