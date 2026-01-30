import React, { useState, useEffect } from "react";
import { MarketplaceExtension, ExtensionCategory, TrustLevel, InstallationProgress } from "./types";
import { ExtensionCard } from "./ExtensionCard";
import { resolveBackendBase, buildHeaders } from "../../api/navi/client";

interface MarketplacePageProps {
    onInstall: (extensionId: string) => void;
    onUninstall: (extensionId: string) => void;
    onEnable: (extensionId: string) => void;
    onDisable: (extensionId: string) => void;
    onViewDetails: (extensionId: string) => void;
}

export function MarketplacePage({
    onInstall,
    onUninstall,
    onEnable,
    onDisable,
    onViewDetails
}: MarketplacePageProps) {
    const [extensions, setExtensions] = useState<MarketplaceExtension[]>([]);
    const [filteredExtensions, setFilteredExtensions] = useState<MarketplaceExtension[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedCategory, setSelectedCategory] = useState<ExtensionCategory | "all">("all");
    const [selectedTrust, setSelectedTrust] = useState<TrustLevel | "all">("all");
    const [sortBy, setSortBy] = useState<"name" | "downloads" | "rating" | "updated">("downloads");
    const [installationProgress, setInstallationProgress] = useState<Record<string, InstallationProgress>>({});

    // Categories for filtering
    const categories: { value: ExtensionCategory | "all"; label: string }[] = [
        { value: "all", label: "All Categories" },
        { value: "intelligence", label: "🧠 Intelligence" },
        { value: "automation", label: "🤖 Automation" },
        { value: "security", label: "🔒 Security" },
        { value: "infrastructure", label: "🏗️ Infrastructure" },
        { value: "productivity", label: "📈 Productivity" },
        { value: "integration", label: "🔗 Integration" }
    ];

    const trustLevels: { value: TrustLevel | "all"; label: string }[] = [
        { value: "all", label: "All Trust Levels" },
        { value: "CORE", label: "🏛️ Core" },
        { value: "VERIFIED", label: "✅ Verified" },
        { value: "ORG_APPROVED", label: "🏢 Org Approved" },
        { value: "UNTRUSTED", label: "⚠️ Untrusted" }
    ];

    // Load extensions from backend
    useEffect(() => {
        loadExtensions();
    }, []);

    const loadExtensions = async () => {
        try {
            setLoading(true);
            const response = await fetch(`${resolveBackendBase()}/api/marketplace/extensions`, {
                headers: buildHeaders(),
            });
            if (!response.ok) throw new Error("Failed to load extensions");

            const data = await response.json();
            setExtensions(data.extensions || []);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load extensions");
        } finally {
            setLoading(false);
        }
    };

    // Filter and sort extensions
    useEffect(() => {
        let filtered = extensions.filter(extension => {
            // Search filter
            if (searchQuery) {
                const query = searchQuery.toLowerCase();
                const matchesSearch =
                    extension.name.toLowerCase().includes(query) ||
                    extension.description.toLowerCase().includes(query) ||
                    extension.author.name.toLowerCase().includes(query) ||
                    extension.tags.some(tag => tag.toLowerCase().includes(query));
                if (!matchesSearch) return false;
            }

            // Category filter
            if (selectedCategory !== "all" && extension.category !== selectedCategory) {
                return false;
            }

            // Trust filter
            if (selectedTrust !== "all" && extension.trustLevel !== selectedTrust) {
                return false;
            }

            return true;
        });

        // Sort extensions
        filtered.sort((a, b) => {
            switch (sortBy) {
                case "name":
                    return a.name.localeCompare(b.name);
                case "downloads":
                    return b.downloads - a.downloads;
                case "rating":
                    return b.rating - a.rating;
                case "updated":
                    return new Date(b.lastUpdated).getTime() - new Date(a.lastUpdated).getTime();
                default:
                    return 0;
            }
        });

        setFilteredExtensions(filtered);
    }, [extensions, searchQuery, selectedCategory, selectedTrust, sortBy]);

    const handleInstall = async (extensionId: string) => {
        setInstallationProgress(prev => ({
            ...prev,
            [extensionId]: { extensionId, status: "downloading", progress: 0 }
        }));

        try {
            await onInstall(extensionId);

            // Update extension status
            setExtensions(prev =>
                prev.map(ext =>
                    ext.id === extensionId
                        ? { ...ext, isInstalled: true, isEnabled: true }
                        : ext
                )
            );
        } catch (error) {
            setInstallationProgress(prev => ({
                ...prev,
                [extensionId]: {
                    extensionId,
                    status: "failed",
                    progress: 0,
                    error: error instanceof Error ? error.message : "Installation failed"
                }
            }));
        } finally {
            // Clear progress after delay
            setTimeout(() => {
                setInstallationProgress(prev => {
                    const { [extensionId]: _, ...rest } = prev;
                    return rest;
                });
            }, 2000);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="flex items-center gap-3">
                    <div className="w-6 h-6 border-3 border-blue-600 border-t-transparent rounded-full animate-spin" />
                    <span className="text-gray-600">Loading extensions...</span>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="text-center py-12">
                <div className="text-red-600 mb-4">❌ {error}</div>
                <button
                    onClick={loadExtensions}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                    Try Again
                </button>
            </div>
        );
    }

    return (
        <div className="max-w-7xl mx-auto p-6">
            {/* Header */}
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-gray-900 mb-2">
                    Extension Marketplace
                </h1>
                <p className="text-gray-600">
                    Discover and install powerful extensions to enhance your NAVI capabilities
                </p>
            </div>

            {/* Search and Filters */}
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    {/* Search */}
                    <div className="md:col-span-2">
                        <input
                            type="text"
                            placeholder="Search extensions..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        />
                    </div>

                    {/* Category Filter */}
                    <div>
                        <select
                            value={selectedCategory}
                            onChange={(e) => setSelectedCategory(e.target.value as ExtensionCategory | "all")}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                        >
                            {categories.map(({ value, label }) => (
                                <option key={value} value={value}>
                                    {label}
                                </option>
                            ))}
                        </select>
                    </div>

                    {/* Trust Filter */}
                    <div>
                        <select
                            value={selectedTrust}
                            onChange={(e) => setSelectedTrust(e.target.value as TrustLevel | "all")}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                        >
                            {trustLevels.map(({ value, label }) => (
                                <option key={value} value={value}>
                                    {label}
                                </option>
                            ))}
                        </select>
                    </div>
                </div>

                {/* Sort Options */}
                <div className="flex items-center gap-2 mt-4 pt-4 border-t border-gray-100">
                    <span className="text-sm text-gray-600">Sort by:</span>
                    {[
                        { value: "downloads", label: "Downloads" },
                        { value: "rating", label: "Rating" },
                        { value: "name", label: "Name" },
                        { value: "updated", label: "Last Updated" }
                    ].map(({ value, label }) => (
                        <button
                            key={value}
                            onClick={() => setSortBy(value as typeof sortBy)}
                            className={`px-3 py-1 text-sm rounded-full transition-colors ${sortBy === value
                                    ? "bg-blue-600 text-white"
                                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                                }`}
                        >
                            {label}
                        </button>
                    ))}
                </div>
            </div>

            {/* Results Summary */}
            <div className="mb-6">
                <p className="text-sm text-gray-600">
                    {filteredExtensions.length} extension{filteredExtensions.length !== 1 ? "s" : ""} found
                </p>
            </div>

            {/* Extensions Grid */}
            {filteredExtensions.length > 0 ? (
                <div className="space-y-4">
                    {filteredExtensions.map((extension) => (
                        <ExtensionCard
                            key={extension.id}
                            extension={extension}
                            installationProgress={installationProgress[extension.id]}
                            onInstall={handleInstall}
                            onUninstall={onUninstall}
                            onEnable={onEnable}
                            onDisable={onDisable}
                            onViewDetails={onViewDetails}
                        />
                    ))}
                </div>
            ) : (
                <div className="text-center py-12">
                    <div className="text-gray-400 mb-4">🔍</div>
                    <h3 className="text-lg font-medium text-gray-900 mb-2">No extensions found</h3>
                    <p className="text-gray-600">
                        Try adjusting your search criteria or filters
                    </p>
                </div>
            )}
        </div>
    );
}