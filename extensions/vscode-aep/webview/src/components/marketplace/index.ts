/**
 * Extension Marketplace Components - Phase 7.1
 * 
 * Enterprise-grade extension marketplace UI components for VS Code
 * Integrates with existing webview framework and Phase 7.0 backend
 */

export { MarketplacePage } from "./MarketplacePage";
export { ExtensionCard } from "./ExtensionCard";
export { InstallButton } from "./InstallButton";
export { TrustBadge } from "./TrustBadge";
export { PermissionDialog } from "./PermissionDialog";

export type {
    TrustLevel,
    ExtensionCategory,
    PermissionType,
    ExtensionPermission,
    MarketplaceExtension,
    InstallationProgress,
    ExtensionManifest
} from "./types";