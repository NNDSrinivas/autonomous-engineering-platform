import React, { useState } from "react";
import { MarketplaceExtension, InstallationProgress } from "./types";
import { TrustBadge } from "./TrustBadge";
import { PermissionDialog } from "./PermissionDialog";

interface InstallButtonProps {
    extension: MarketplaceExtension;
    installationProgress?: InstallationProgress;
    onInstall: (extensionId: string) => void;
    onUninstall: (extensionId: string) => void;
    onEnable: (extensionId: string) => void;
    onDisable: (extensionId: string) => void;
}

export function InstallButton({
    extension,
    installationProgress,
    onInstall,
    onUninstall,
    onEnable,
    onDisable
}: InstallButtonProps) {
    const [showPermissionDialog, setShowPermissionDialog] = useState(false);

    const handleInstallClick = () => {
        // Always show permission dialog for security - no silent installs
        setShowPermissionDialog(true);
    };

    const handlePermissionApprove = () => {
        setShowPermissionDialog(false);
        onInstall(extension.id);
    };

    const handlePermissionCancel = () => {
        setShowPermissionDialog(false);
    };

    // Show progress during installation
    if (installationProgress && installationProgress.status !== "complete") {
        return (
            <div className="flex items-center gap-2">
                <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                <span className="text-sm text-gray-600 capitalize">
                    {installationProgress.status}... {installationProgress.progress}%
                </span>
            </div>
        );
    }

    // Extension is installed
    if (extension.isInstalled) {
        return (
            <div className="flex gap-2">
                {extension.isEnabled ? (
                    <button
                        onClick={() => onDisable(extension.id)}
                        className="px-3 py-1 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
                    >
                        Disable
                    </button>
                ) : (
                    <button
                        onClick={() => onEnable(extension.id)}
                        className="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700"
                    >
                        Enable
                    </button>
                )}
                <button
                    onClick={() => onUninstall(extension.id)}
                    className="px-3 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-700"
                >
                    Uninstall
                </button>
            </div>
        );
    }

    // Extension is not installed
    return (
        <>
            <button
                onClick={handleInstallClick}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
            >
                Install
            </button>

            <PermissionDialog
                extensionName={extension.name}
                permissions={extension.permissions}
                onApprove={handlePermissionApprove}
                onCancel={handlePermissionCancel}
                isOpen={showPermissionDialog}
            />
        </>
    );
}