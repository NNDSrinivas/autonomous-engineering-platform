import React, { useEffect, useState } from "react";

interface ToastProps {
  message: string;
  type?: "info" | "success" | "warning" | "error";
  duration?: number;
  onClose?: () => void;
}

export const Toast: React.FC<ToastProps> = ({ 
  message, 
  type = "info", 
  duration = 5000,
  onClose 
}) => {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    if (duration > 0) {
      const timer = setTimeout(() => {
        setVisible(false);
        setTimeout(() => onClose?.(), 300); // Allow fade out animation
      }, duration);
      
      return () => clearTimeout(timer);
    }
  }, [duration, onClose]);

  const getTypeStyles = () => {
    switch (type) {
      case "success":
        return "bg-green-600 border-green-500";
      case "warning":
        return "bg-amber-600 border-amber-500";
      case "error":
        return "bg-red-600 border-red-500";
      default:
        return "bg-blue-600 border-blue-500";
    }
  };

  const handleClose = () => {
    setVisible(false);
    setTimeout(() => onClose?.(), 300);
  };

  return (
    <div className={`fixed top-4 right-4 z-50 transform transition-all duration-300 ${
      visible ? "translate-x-0 opacity-100" : "translate-x-full opacity-0"
    }`}>
      <div className={`${getTypeStyles()} text-white px-4 py-3 rounded-lg shadow-lg border-l-4 min-w-80 max-w-md`}>
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1">
            <p className="text-sm font-medium leading-relaxed">{message}</p>
          </div>
          <button
            onClick={handleClose}
            className="text-white/80 hover:text-white transition-colors shrink-0 ml-2"
            aria-label="Close notification"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
};

// Toast manager for programmatic usage
export class ToastManager {
  private static instance: ToastManager;
  private toasts: Array<{ id: string; message: string; type: ToastProps["type"]; duration?: number }> = [];
  private listeners: Set<() => void> = new Set();

  static getInstance() {
    if (!ToastManager.instance) {
      ToastManager.instance = new ToastManager();
    }
    return ToastManager.instance;
  }

  show(message: string, type: ToastProps["type"] = "info", duration = 5000) {
    const id = Math.random().toString(36).substr(2, 9);
    this.toasts.push({ id, message, type, duration });
    this.notifyListeners();
    
    if (duration > 0) {
      setTimeout(() => this.remove(id), duration);
    }
    
    return id;
  }

  remove(id: string) {
    this.toasts = this.toasts.filter(toast => toast.id !== id);
    this.notifyListeners();
  }

  subscribe(listener: () => void) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  getToasts() {
    return [...this.toasts];
  }

  private notifyListeners() {
    this.listeners.forEach(listener => listener());
  }
}

// Hook for using toasts
export function useToasts() {
  const [toasts, setToasts] = useState(() => ToastManager.getInstance().getToasts());

  useEffect(() => {
    const manager = ToastManager.getInstance();
    const unsubscribe = manager.subscribe(() => setToasts(manager.getToasts()));
    return unsubscribe;
  }, []);

  return {
    toasts,
    showToast: (message: string, type?: ToastProps["type"], duration?: number) => 
      ToastManager.getInstance().show(message, type, duration),
    removeToast: (id: string) => ToastManager.getInstance().remove(id),
  };
}