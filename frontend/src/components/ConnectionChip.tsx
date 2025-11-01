import React from "react";
import { ConnectionStatus } from "../state/connection/useConnection";

interface ConnectionChipProps {
  online: boolean;
  status: ConnectionStatus;
}

export const ConnectionChip: React.FC<ConnectionChipProps> = ({ online, status }) => {
  const getStatusInfo = () => {
    if (!online) {
      return { color: "bg-red-600", text: "Offline", pulse: false };
    }
    
    switch (status) {
      case "connected":
        return { color: "bg-green-600", text: "Live", pulse: false };
      case "connecting":
        return { color: "bg-amber-500", text: "Reconnecting", pulse: true };
      case "disconnected":
        return { color: "bg-red-600", text: "Disconnected", pulse: true };
      default:
        return { color: "bg-gray-500", text: "Unknown", pulse: false };
    }
  };

  const { color, text, pulse } = getStatusInfo();

  return (
    <div className={`fixed bottom-4 right-4 z-50 text-white px-3 py-1 rounded-full shadow-lg text-sm font-medium ${color} ${pulse ? "animate-pulse" : ""}`}>
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full bg-white/80 ${pulse ? "animate-ping" : ""}`} />
        {text}
      </div>
    </div>
  );
};