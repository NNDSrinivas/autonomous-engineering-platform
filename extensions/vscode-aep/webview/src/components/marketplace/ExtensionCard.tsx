import React from "react";
import { MarketplaceExtension, InstallationProgress } from "./types";
import { TrustBadge } from "./TrustBadge";
import { InstallButton } from "./InstallButton";

interface ExtensionCardProps {
    extension: MarketplaceExtension;
    installationProgress?: InstallationProgress;
    onInstall: (extensionId: string) => void;
    onUninstall: (extensionId: string) => void;
    onEnable: (extensionId: string) => void;
    onDisable: (extensionId: string) => void;
    onViewDetails: (extensionId: string) => void;
}

export function ExtensionCard({
    extension,
    installationProgress,
    onInstall,
    onUninstall,
    onEnable,
    onDisable,
    onViewDetails
}: ExtensionCardProps) {
    const formatDownloads = (count: number): string => {
        if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`;
        if (count >= 1000) return `${(count / 1000).toFixed(1)}K`;
        return count.toString();
    };

    const formatRating = (rating: number): string => {
        return rating.toFixed(1);
    };

    const renderStars = (rating: number) => {
        const stars = [];
        const fullStars = Math.floor(rating);
        const hasHalfStar = rating % 1 >= 0.5;

        for (let i = 0; i < 5; i++) {
            if (i < fullStars) {
                stars.push(
                    <span key={i} className="text-yellow-400">
                        ★
                    </span>
                );
            } else if (i === fullStars && hasHalfStar) {
                stars.push(
                    <span key={i} className="text-yellow-400">
                        ☆
                    </span>
                );
            } else {
                stars.push(
                    <span key={i} className="text-gray-300">
                        ☆
                    </span>
                );
            }
        }
        return stars;
    };

    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow">
            <div className="flex items-start gap-4">
                {/* Extension Icon */}
                <div className="flex-shrink-0">
                    {extension.iconUrl ? (
                        <img
                            src={extension.iconUrl}
                            alt={`${extension.name} icon`}
                            className="w-16 h-16 rounded-lg object-cover border border-gray-200"
                        />
                    ) : (
                        <div className="w-16 h-16 bg-gray-100 rounded-lg flex items-center justify-center border border-gray-200">
                            <span className="text-2xl text-gray-400">⚡</span>
                        </div>
                    )}
                </div>

                {/* Extension Details */}
                <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between mb-2">
                        <div>
                            <h3 className="text-lg font-semibold text-gray-900 mb-1">
                                {extension.name}
                            </h3>
                            <div className="flex items-center gap-2 mb-2">
                                <span className="text-sm text-gray-600">
                                    by {extension.author.name}
                                </span>
                                {extension.author.verified && (
                                    <span className="text-blue-500 text-sm">✓ Verified</span>
                                )}
                                {extension.author.organization && (
                                    <span className="text-xs text-gray-500 px-2 py-1 bg-gray-100 rounded">
                                        {extension.author.organization}
                                    </span>
                                )}
                                <TrustBadge level={extension.trustLevel} />
                            </div>
                        </div>
                        <InstallButton
                            extension={extension}
                            installationProgress={installationProgress}
                            onInstall={onInstall}
                            onUninstall={onUninstall}
                            onEnable={onEnable}
                            onDisable={onDisable}
                        />
                    </div>

                    <p className="text-sm text-gray-700 mb-3 line-clamp-2">
                        {extension.description}
                    </p>

                    {/* Tags */}
                    {extension.tags && extension.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mb-3">
                            <span className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded-full font-medium">
                                {extension.category}
                            </span>
                            {extension.tags.slice(0, 3).map((tag) => (
                                <span
                                    key={tag}
                                    className="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded-full"
                                >
                                    {tag}
                                </span>
                            ))}
                            {extension.tags.length > 3 && (
                                <span className="px-2 py-1 text-xs text-gray-500">
                                    +{extension.tags.length - 3} more
                                </span>
                            )}
                        </div>
                    )}

                    {/* Metadata */}
                    <div className="flex items-center gap-4 text-sm text-gray-500">
                        <div className="flex items-center gap-1">
                            {renderStars(extension.rating)}
                            <span className="ml-1">{formatRating(extension.rating)}</span>
                        </div>
                        <div>{formatDownloads(extension.downloads)} downloads</div>
                        <div>v{extension.version}</div>
                        <div>{new Date(extension.lastUpdated).toLocaleDateString()}</div>
                    </div>

                    {/* High-risk permissions warning */}
                    {extension.permissions.some(p => p.riskLevel === "high") && (
                        <div className="mt-3 p-2 bg-yellow-50 border border-yellow-200 rounded-md">
                            <div className="flex items-center gap-2">
                                <span className="text-yellow-600">⚠️</span>
                                <span className="text-sm text-yellow-800">
                                    This extension requires high-risk permissions
                                </span>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Actions */}
            <div className="mt-4 pt-4 border-t border-gray-100">
                <button
                    onClick={() => onViewDetails(extension.id)}
                    className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                >
                    View Details →
                </button>
            </div>
        </div>
    );
}
