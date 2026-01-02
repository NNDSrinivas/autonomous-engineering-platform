import React, { useState, useEffect } from 'react';
import {
    Search,
    Download,
    Star,
    Calendar,
    Shield,
    AlertTriangle,
    CheckCircle,
    Package,
    Trash2,
    RefreshCw
} from 'lucide-react';
import { extensionsAPI, ExtensionManifest, SearchRequest, SearchFilters, InstallationStatus } from '../api/extensions';

interface ExtensionCardProps {
    extension: ExtensionManifest;
    isInstalled: boolean;
    installationStatus?: InstallationStatus;
    onInstall: (extensionId: string) => void;
    onUninstall: (extensionId: string) => void;
    onUpdate: (extensionId: string) => void;
}

const ExtensionCard: React.FC<ExtensionCardProps> = ({
    extension,
    isInstalled,
    installationStatus,
    onInstall,
    onUninstall,
    onUpdate
}) => {
    const getCategoryColor = (category: string) => {
        const colors = {
            development: 'bg-blue-100 text-blue-800',
            productivity: 'bg-green-100 text-green-800',
            integration: 'bg-purple-100 text-purple-800',
            analytics: 'bg-orange-100 text-orange-800',
            security: 'bg-red-100 text-red-800',
            other: 'bg-gray-100 text-gray-800'
        };
        return colors[category as keyof typeof colors] || colors.other;
    };

    const getStatusIcon = () => {
        if (installationStatus?.status === 'installing') {
            return <RefreshCw className="h-4 w-4 animate-spin" />;
        }
        if (isInstalled) {
            return <CheckCircle className="h-4 w-4 text-green-600" />;
        }
        return <Download className="h-4 w-4" />;
    };

    const getActionButton = () => {
        if (installationStatus?.status === 'installing') {
            return (
                <button
                    disabled
                    className="flex items-center gap-2 px-4 py-2 bg-gray-300 text-gray-600 rounded-lg text-sm font-medium cursor-not-allowed"
                >
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    Installing...
                </button>
            );
        }

        if (isInstalled) {
            return (
                <div className="flex gap-2">
                    <button
                        onClick={() => onUpdate(extension.id)}
                        className="flex items-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
                    >
                        <RefreshCw className="h-4 w-4" />
                        Update
                    </button>
                    <button
                        onClick={() => onUninstall(extension.id)}
                        className="flex items-center gap-2 px-3 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium transition-colors"
                    >
                        <Trash2 className="h-4 w-4" />
                        Uninstall
                    </button>
                </div>
            );
        }

        return (
            <button
                onClick={() => onInstall(extension.id)}
                className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
                <Download className="h-4 w-4" />
                Install
            </button>
        );
    };

    return (
        <div className="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow p-6 border border-gray-200">
            <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                    {extension.icon ? (
                        <img
                            src={extension.icon}
                            alt={`${extension.name} icon`}
                            className="w-12 h-12 rounded-lg"
                        />
                    ) : (
                        <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-purple-500 to-blue-600 flex items-center justify-center">
                            <Package className="h-6 w-6 text-white" />
                        </div>
                    )}
                    <div>
                        <h3 className="text-lg font-semibold text-gray-900">{extension.name}</h3>
                        <p className="text-sm text-gray-600">by {extension.author.name}</p>
                    </div>
                </div>
                {getStatusIcon()}
            </div>

            <p className="text-gray-700 mb-4 text-sm line-clamp-3">
                {extension.description}
            </p>

            <div className="flex items-center gap-4 mb-4 text-sm text-gray-600">
                {extension.rating && (
                    <div className="flex items-center gap-1">
                        <Star className="h-4 w-4 fill-yellow-400 text-yellow-400" />
                        <span>{extension.rating.toFixed(1)}</span>
                    </div>
                )}
                {extension.downloadCount && (
                    <div className="flex items-center gap-1">
                        <Download className="h-4 w-4" />
                        <span>{extension.downloadCount.toLocaleString()}</span>
                    </div>
                )}
                <div className="flex items-center gap-1">
                    <Calendar className="h-4 w-4" />
                    <span>{new Date(extension.lastUpdated).toLocaleDateString()}</span>
                </div>
            </div>

            <div className="flex items-center justify-between mb-4">
                <div className="flex gap-2">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getCategoryColor(extension.category)}`}>
                        {extension.category}
                    </span>
                    {extension.tags.slice(0, 2).map(tag => (
                        <span
                            key={tag}
                            className="px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-700"
                        >
                            {tag}
                        </span>
                    ))}
                </div>
                <span className="text-xs text-gray-500">v{extension.version}</span>
            </div>

            <div className="flex items-center justify-between">
                <div className="flex items-center gap-1 text-sm text-gray-600">
                    <Shield className="h-4 w-4" />
                    <span>{extension.capabilities.length} capabilities</span>
                </div>
                {getActionButton()}
            </div>
        </div>
    );
};

const ExtensionMarketplacePage: React.FC = () => {
    const [extensions, setExtensions] = useState<ExtensionManifest[]>([]);
    const [installedExtensions, setInstalledExtensions] = useState<ExtensionManifest[]>([]);
    const [installationStatuses, setInstallationStatuses] = useState<Map<string, InstallationStatus>>(new Map());
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [filters, setFilters] = useState<SearchFilters>({});
    const [activeTab, setActiveTab] = useState<'browse' | 'installed'>('browse');
    const [categories, setCategories] = useState<Array<{ id: string; name: string; description: string; count: number }>>([]);
    const [selectedCategory, setSelectedCategory] = useState<string>('');
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        loadExtensions();
        loadInstalledExtensions();
        loadCategories();
    }, []);

    const loadExtensions = async () => {
        try {
            setLoading(true);
            if (searchQuery || Object.keys(filters).length > 0) {
                const request: SearchRequest = {
                    query: searchQuery || undefined,
                    filters: {
                        ...filters,
                        category: selectedCategory || undefined
                    },
                    page: 1,
                    page_size: 50
                };
                const result = await extensionsAPI.searchMarketplace(request);
                setExtensions(result.extensions);
            } else {
                const featured = await extensionsAPI.getFeaturedExtensions();
                setExtensions(featured);
            }
        } catch (error: any) {
            console.error('Failed to load extensions:', error);
            setError('Failed to load extensions. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const loadInstalledExtensions = async () => {
        try {
            const installed = await extensionsAPI.getInstalledExtensions();
            setInstalledExtensions(installed);
        } catch (error: any) {
            console.error('Failed to load installed extensions:', error);
        }
    };

    const loadCategories = async () => {
        try {
            const cats = await extensionsAPI.getCategories();
            setCategories(cats);
        } catch (error: any) {
            console.error('Failed to load categories:', error);
        }
    };

    const handleInstall = async (extensionId: string) => {
        try {
            const result = await extensionsAPI.installExtension(extensionId);
            if (result.success) {
                setInstallationStatuses(prev => new Map(prev.set(extensionId, {
                    extension_id: extensionId,
                    status: 'installing',
                    progress: 0
                })));

                // Poll for installation status
                pollInstallationStatus(result.installation_id, extensionId);
            }
        } catch (error: any) {
            console.error('Failed to install extension:', error);
            setError(`Failed to install extension: ${error.message}`);
        }
    };

    const handleUninstall = async (extensionId: string) => {
        try {
            const result = await extensionsAPI.uninstallExtension(extensionId);
            if (result.success) {
                await loadInstalledExtensions();
            }
        } catch (error: any) {
            console.error('Failed to uninstall extension:', error);
            setError(`Failed to uninstall extension: ${error.message}`);
        }
    };

    const handleUpdate = async (extensionId: string) => {
        try {
            const result = await extensionsAPI.updateExtension(extensionId);
            if (result.success) {
                await loadInstalledExtensions();
            }
        } catch (error: any) {
            console.error('Failed to update extension:', error);
            setError(`Failed to update extension: ${error.message}`);
        }
    };

    const pollInstallationStatus = async (installationId: string, extensionId: string) => {
        const maxAttempts = 30;
        let attempts = 0;

        const poll = async () => {
            try {
                const status = await extensionsAPI.getInstallationStatus(installationId);
                setInstallationStatuses(prev => new Map(prev.set(extensionId, status)));

                if (status.status === 'installed') {
                    await loadInstalledExtensions();
                    return;
                }

                if (status.status === 'failed') {
                    setError(`Installation failed: ${status.error}`);
                    return;
                }

                if (attempts < maxAttempts && (status.status === 'installing' || status.status === 'updating')) {
                    attempts++;
                    setTimeout(poll, 2000);
                }
            } catch (error) {
                console.error('Failed to poll installation status:', error);
            }
        };

        poll();
    };

    const isExtensionInstalled = (extensionId: string) => {
        return installedExtensions.some(ext => ext.id === extensionId);
    };

    const handleSearch = () => {
        loadExtensions();
    };

    const clearFilters = () => {
        setSearchQuery('');
        setSelectedCategory('');
        setFilters({});
        loadExtensions();
    };

    const filteredExtensions = activeTab === 'installed' ? installedExtensions : extensions;

    return (
        <div className="min-h-screen bg-gray-50">
            <div className="max-w-7xl mx-auto px-6 py-8">
                <div className="mb-8">
                    <h1 className="text-3xl font-bold text-gray-900 mb-2">Extension Marketplace</h1>
                    <p className="text-gray-600">Discover and install extensions to enhance your NAVI experience</p>
                </div>

                {error && (
                    <div className="mb-6 bg-red-50 border-l-4 border-red-400 p-4 rounded-lg">
                        <div className="flex">
                            <AlertTriangle className="h-5 w-5 text-red-400" />
                            <div className="ml-3">
                                <p className="text-red-700">{error}</p>
                                <button
                                    onClick={() => setError(null)}
                                    className="mt-2 text-sm text-red-600 hover:text-red-800 underline"
                                >
                                    Dismiss
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                <div className="mb-6 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <button
                            onClick={() => setActiveTab('browse')}
                            className={`px-4 py-2 rounded-lg font-medium transition-colors ${activeTab === 'browse'
                                    ? 'bg-blue-600 text-white'
                                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                                }`}
                        >
                            Browse Marketplace
                        </button>
                        <button
                            onClick={() => setActiveTab('installed')}
                            className={`px-4 py-2 rounded-lg font-medium transition-colors ${activeTab === 'installed'
                                    ? 'bg-blue-600 text-white'
                                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                                }`}
                        >
                            Installed ({installedExtensions.length})
                        </button>
                    </div>
                </div>

                {activeTab === 'browse' && (
                    <div className="mb-6 space-y-4">
                        <div className="flex gap-4">
                            <div className="flex-1 relative">
                                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-5 w-5" />
                                <input
                                    type="text"
                                    placeholder="Search extensions..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                                    className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                                />
                            </div>
                            <button
                                onClick={handleSearch}
                                className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
                            >
                                Search
                            </button>
                        </div>

                        <div className="flex flex-wrap gap-2">
                            <select
                                value={selectedCategory}
                                onChange={(e) => setSelectedCategory(e.target.value)}
                                className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                            >
                                <option value="">All Categories</option>
                                {categories.map(cat => (
                                    <option key={cat.id} value={cat.id}>
                                        {cat.name} ({cat.count})
                                    </option>
                                ))}
                            </select>

                            {(searchQuery || selectedCategory || Object.keys(filters).length > 0) && (
                                <button
                                    onClick={clearFilters}
                                    className="px-3 py-2 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded-lg text-sm font-medium transition-colors"
                                >
                                    Clear Filters
                                </button>
                            )}
                        </div>
                    </div>
                )}

                {loading ? (
                    <div className="flex items-center justify-center py-12">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                        <span className="ml-3 text-gray-600">Loading extensions...</span>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {filteredExtensions.map(extension => (
                            <ExtensionCard
                                key={extension.id}
                                extension={extension}
                                isInstalled={isExtensionInstalled(extension.id)}
                                installationStatus={installationStatuses.get(extension.id)}
                                onInstall={handleInstall}
                                onUninstall={handleUninstall}
                                onUpdate={handleUpdate}
                            />
                        ))}
                    </div>
                )}

                {!loading && filteredExtensions.length === 0 && (
                    <div className="text-center py-12">
                        <Package className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                        <h3 className="text-lg font-medium text-gray-900 mb-2">
                            {activeTab === 'installed' ? 'No Extensions Installed' : 'No Extensions Found'}
                        </h3>
                        <p className="text-gray-600">
                            {activeTab === 'installed'
                                ? 'Browse the marketplace to find and install extensions.'
                                : 'Try adjusting your search terms or filters.'}
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default ExtensionMarketplacePage;
