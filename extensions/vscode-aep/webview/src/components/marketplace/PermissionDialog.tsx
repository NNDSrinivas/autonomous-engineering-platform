import React from "react";
import { ExtensionPermission } from "./types";

interface PermissionDialogProps {
    extensionName: string;
    permissions: ExtensionPermission[];
    onApprove: () => void;
    onCancel: () => void;
    isOpen: boolean;
}

export function PermissionDialog({
    extensionName,
    permissions,
    onApprove,
    onCancel,
    isOpen
}: PermissionDialogProps) {
    if (!isOpen) return null;

    const getRiskColor = (riskLevel: string) => {
        switch (riskLevel) {
            case "critical":
                return "text-red-600 bg-red-50 border-red-200";
            case "high":
                return "text-orange-600 bg-orange-50 border-orange-200";
            case "medium":
                return "text-yellow-600 bg-yellow-50 border-yellow-200";
            case "low":
                return "text-green-600 bg-green-50 border-green-200";
            default:
                return "text-gray-600 bg-gray-50 border-gray-200";
        }
    };

    const getRiskIcon = (riskLevel: string) => {
        switch (riskLevel) {
            case "critical":
                return "🚨";
            case "high":
                return "⚠️";
            case "medium":
                return "⚡";
            case "low":
                return "🔒";
            default:
                return "ℹ️";
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
            <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 max-h-[80vh] overflow-hidden">
                <div className="p-6 border-b border-gray-200">
                    <h2 className="text-xl font-semibold text-gray-900">
                        Extension Permissions Required
                    </h2>
                    <p className="mt-2 text-sm text-gray-600">
                        <strong>{extensionName}</strong> is requesting the following permissions:
                    </p>
                </div>

                <div className="p-6 max-h-60 overflow-y-auto">
                    {permissions.length === 0 ? (
                        <p className="text-gray-500 text-sm">No special permissions required.</p>
                    ) : (
                        <div className="space-y-3">
                            {permissions.map((permission) => (
                                <div
                                    key={permission.type}
                                    className={`p-3 rounded-lg border ${getRiskColor(permission.riskLevel)
                                        }`}
                                >
                                    <div className="flex items-start gap-3">
                                        <span className="text-lg">
                                            {getRiskIcon(permission.riskLevel)}
                                        </span>
                                        <div className="flex-1">
                                            <h4 className="font-medium text-sm">
                                                {permission.type.replace("_", " ").toLowerCase()}
                                                <span className={`ml-2 text-xs px-2 py-1 rounded-full ${getRiskColor(permission.riskLevel)
                                                    }`}>
                                                    {permission.riskLevel}
                                                </span>
                                            </h4>
                                            <p className="text-xs mt-1 opacity-75">
                                                {permission.description}
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                <div className="p-6 bg-gray-50 border-t border-gray-200 flex gap-3">
                    <button
                        onClick={onCancel}
                        className="flex-1 px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 font-medium"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={onApprove}
                        className="flex-1 px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 font-medium"
                    >
                        Approve & Install
                    </button>
                </div>
            </div>
        </div>
    );
}