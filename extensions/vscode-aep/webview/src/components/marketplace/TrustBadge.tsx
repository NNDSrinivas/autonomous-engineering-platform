import React from "react";
import { TrustLevel } from "./types";

interface TrustBadgeProps {
    level: TrustLevel;
    className?: string;
}

export function TrustBadge({ level, className = "" }: TrustBadgeProps) {
    const getBadgeStyle = () => {
        switch (level) {
            case "CORE":
                return {
                    bg: "bg-green-100",
                    text: "text-green-800",
                    border: "border-green-200",
                    icon: "🏛️",
                    label: "NAVI Core"
                };
            case "VERIFIED":
                return {
                    bg: "bg-blue-100",
                    text: "text-blue-800",
                    border: "border-blue-200",
                    icon: "✅",
                    label: "Verified"
                };
            case "ORG_APPROVED":
                return {
                    bg: "bg-purple-100",
                    text: "text-purple-800",
                    border: "border-purple-200",
                    icon: "🏢",
                    label: "Org Approved"
                };
            case "UNTRUSTED":
                return {
                    bg: "bg-red-100",
                    text: "text-red-800",
                    border: "border-red-200",
                    icon: "⚠️",
                    label: "Untrusted"
                };
            default:
                return {
                    bg: "bg-gray-100",
                    text: "text-gray-800",
                    border: "border-gray-200",
                    icon: "❓",
                    label: "Unknown"
                };
        }
    };

    const style = getBadgeStyle();

    return (
        <span
            className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium border ${style.bg
                } ${style.text} ${style.border} ${className}`}
            title={`Trust Level: ${style.label}`}
        >
            <span>{style.icon}</span>
            <span>{style.label}</span>
        </span>
    );
}