import { useState } from 'react'
import axios from 'axios'
import { CORE_API } from '../api/client'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || CORE_API

interface SearchResult {
    id: number
    category: string
    scope: string | null
    title: string | null
    content: string
    similarity: number
    importance: number
    meta: Record<string, any> | null
    created_at: string | null
}

interface SearchResponse {
    query: string
    results: SearchResult[]
    total: number
    user_id: string
}

interface StatsResponse {
    user_id: string
    total_memories: number
    by_category: Record<string, number>
}

interface AgentIntentCore {
    family: string
    kind: string
    priority?: string
    confidence?: number
}

interface AgentWorkflowHints {
    autonomy_mode?: string
    max_steps?: number
    auto_run_tests?: boolean
}

interface AgentIntentResponse {
    intent: AgentIntentCore
    workflow?: AgentWorkflowHints
    model_used?: string
    provider_used?: string
    raw_text?: string
}

type ModelOption = {
    value: string
    label: string
    group?: string
}

const MODEL_OPTIONS: ModelOption[] = [
    {
        value: 'smart-auto',
        label: 'Smart Auto (recommended)',
        group: 'AEP',
    },
    { value: 'openai:gpt-4o', label: 'GPT-4o', group: 'OpenAI' },
    { value: 'openai:gpt-4o-mini', label: 'GPT-4o Mini', group: 'OpenAI' },
    {
        value: 'anthropic:claude-3-5-sonnet',
        label: 'Claude 3.5 Sonnet',
        group: 'Anthropic',
    },
    {
        value: 'google:gemini-1.5-pro',
        label: 'Gemini 1.5 Pro',
        group: 'Google Gemini',
    },
    {
        value: 'openai:o1-preview',
        label: 'o1-preview',
        group: 'OpenAI',
    },
]

const CATEGORY_EMOJIS: Record<string, string> = {
    profile: '👤',
    workspace: '🏢',
    task: '✅',
    interaction: '💬',
}

export function NaviSearchPage() {
    const [query, setQuery] = useState('')
    const [userId, setUserId] = useState('test-user')
    const [categories, setCategories] = useState<string[]>([
        'profile',
        'workspace',
        'task',
        'interaction',
    ])
    const [limit, setLimit] = useState(8)
    const [minImportance, setMinImportance] = useState(1)
    const [loading, setLoading] = useState(false)
    const [results, setResults] = useState<SearchResponse | null>(null)
    const [stats, setStats] = useState<StatsResponse | null>(null)
    const [error, setError] = useState<string | null>(null)

    const [activeTab, setActiveTab] = useState<'search' | 'stats' | 'intent'>(
        'search',
    )

    // NEW: agent intent classifier state
    const [agentInput, setAgentInput] = useState('')
    const [selectedModel, setSelectedModel] = useState<string>('smart-auto')
    const [intentResult, setIntentResult] = useState<AgentIntentResponse | null>(
        null,
    )

    const handleSearch = async () => {
        if (!query.trim()) {
            setError('Please enter a search query')
            return
        }

        setLoading(true)
        setError(null)

        try {
            const response = await axios.post<SearchResponse>(`${API_BASE_URL}/api/navi/search`, {
                query,
                user_id: userId,
                categories,
                limit,
                min_importance: minImportance,
            })

            setResults(response.data)
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message || 'Search failed')
        } finally {
            setLoading(false)
        }
    }

    const loadStats = async () => {
        setLoading(true)
        setError(null)

        try {
            const response = await axios.get<StatsResponse>(
                `${API_BASE_URL}/api/navi/search/stats?user_id=${userId}`
            )

            setStats(response.data)
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message || 'Failed to load stats')
        } finally {
            setLoading(false)
        }
    }

    // NEW: call /api/agent/intent/preview endpoint
    const handleClassifyIntent = async () => {
        if (!agentInput.trim()) {
            setError('Please describe what you want NAVI to do')
            return
        }

        setLoading(true)
        setError(null)
        setIntentResult(null)

        try {
            const response = await axios.post<AgentIntentResponse>(
                `${API_BASE_URL}/api/agent/intent/preview`,
                {
                    message: agentInput,
                    model_id: selectedModel,
                    session_id: `web-${userId || 'anonymous'}`,
                    source: 'web',
                    metadata: {},
                },
            )

            setIntentResult(response.data)
        } catch (err: any) {
            // For demo purposes: if backend is not available, show a mock response
            if (err.code === 'ECONNREFUSED' || err.message.includes('Network Error')) {
                console.warn('[DEMO] Backend not available, using mock intent classification')

                // Generate realistic mock response based on input
                const mockIntent = generateMockIntent(agentInput, selectedModel)
                setIntentResult(mockIntent)
                return
            }

            setError(
                err.response?.data?.detail || err.message || 'Failed to classify intent',
            )
        } finally {
            setLoading(false)
        }
    }

    // Helper function to generate realistic mock responses for demo
    const generateMockIntent = (message: string, _model: string): AgentIntentResponse => {
        const lowerMessage = message.toLowerCase()

        // Determine intent based on keywords
        let family = 'ENGINEERING'
        let kind = 'ASSISTANCE'
        let priority = 'NORMAL'
        let confidence = 0.85
        let autonomyMode = 'ASSISTED'
        let maxSteps = 3
        let autoRunTests = false

        if (lowerMessage.includes('fix') || lowerMessage.includes('bug') || lowerMessage.includes('error')) {
            kind = 'FIX_BUG'
            priority = 'HIGH'
            confidence = 0.92
            autonomyMode = 'AUTONOMOUS'
            maxSteps = 5
            autoRunTests = true
        } else if (lowerMessage.includes('test') || lowerMessage.includes('ci') || lowerMessage.includes('flaky')) {
            kind = 'IMPROVE_TESTS'
            priority = 'HIGH'
            confidence = 0.89
            autoRunTests = true
            maxSteps = 4
        } else if (lowerMessage.includes('create') || lowerMessage.includes('new') || lowerMessage.includes('add')) {
            kind = 'NEW_FEATURE'
            priority = 'NORMAL'
            confidence = 0.78
            maxSteps = 6
        } else if (lowerMessage.includes('review') || lowerMessage.includes('analyze') || lowerMessage.includes('check')) {
            kind = 'CODE_REVIEW'
            confidence = 0.81
            maxSteps = 2
        } else if (lowerMessage.includes('deploy') || lowerMessage.includes('pipeline') || lowerMessage.includes('ci/cd')) {
            family = 'DEVOPS'
            kind = 'DEPLOYMENT'
            priority = 'HIGH'
            confidence = 0.88
            maxSteps = 4
        }

        return {
            intent: {
                family,
                kind,
                priority,
                confidence
            },
            workflow: {
                autonomy_mode: autonomyMode,
                max_steps: maxSteps,
                auto_run_tests: autoRunTests
            },
            model_used: selectedModel === 'smart-auto' ? 'openai:gpt-4o' : selectedModel,
            provider_used: selectedModel.includes('openai') ? 'OpenAI' :
                selectedModel.includes('anthropic') ? 'Anthropic' :
                    selectedModel.includes('google') ? 'Google' : 'AEP',
            raw_text: `[DEMO] Classified "${message}" as ${family}/${kind}`
        }
    }

    const toggleCategory = (cat: string) => {
        setCategories((prev) =>
            prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]
        )
    }

    const highlightQuery = (text: string) => {
        if (!query) return text
        const parts = text.split(new RegExp(`(${query})`, 'gi'))
        return parts.map((part, i) =>
            part.toLowerCase() === query.toLowerCase() ? (
                <mark key={i} className="bg-yellow-200 px-1 rounded">
                    {part}
                </mark>
            ) : (
                part
            )
        )
    }

    // helper to render model dropdown (grouped)
    const renderModelDropdown = () => {
        const grouped = MODEL_OPTIONS.reduce<Record<string, ModelOption[]>>(
            (acc, opt) => {
                const key = opt.group || 'Other'
                if (!acc[key]) acc[key] = []
                acc[key].push(opt)
                return acc
            },
            {},
        )

        return (
            <div className="flex items-center gap-2 text-xs">
                <span className="text-blue-200/80">Model</span>
                <select
                    className="bg-slate-900/70 border border-blue-500/40 rounded-full px-3 py-1 text-xs text-blue-50 focus:outline-none focus:ring-2 focus:ring-fuchsia-500/70"
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                >
                    {Object.entries(grouped).map(([group, opts]) => (
                        <optgroup key={group} label={group}>
                            {opts.map((opt) => (
                                <option key={opt.value} value={opt.value}>
                                    {opt.label}
                                </option>
                            ))}
                        </optgroup>
                    ))}
                </select>
            </div>
        )
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 p-8">
            <div className="max-w-6xl mx-auto">
                {/* Header */}
                <div className="bg-white/10 backdrop-blur-lg rounded-2xl shadow-2xl border border-white/20 p-8 mb-6 flex items-center justify-between gap-4">
                    <div>
                        <h1 className="text-4xl font-bold text-white mb-2 flex items-center gap-3">
                            🔍 NAVI RAG & Agent Console
                        </h1>
                        <p className="text-blue-200">
                            Step 3: Unified semantic search + NAVI intent classification for autonomous workflows.
                        </p>
                    </div>
                    {/* small "powered by" chip */}
                    <div className="hidden md:flex flex-col items-end text-xs text-blue-200/80">
                        <span className="uppercase tracking-widest text-[0.6rem] text-blue-300/70">
                            NAVRA · AEP
                        </span>
                        <span className="font-mono text-[0.65rem] text-blue-100/80">
                            Smart Auto model routing
                        </span>
                    </div>
                </div>

                {/* Tabs */}
                <div className="flex gap-4 mb-6">
                    <button
                        onClick={() => setActiveTab('search')}
                        className={`px-6 py-3 rounded-lg font-semibold transition-colors ${activeTab === 'search'
                            ? 'bg-blue-600 text-white'
                            : 'bg-white/10 text-white/70 hover:bg-white/20'
                            }`}
                    >
                        RAG Search
                    </button>
                    <button
                        onClick={() => {
                            setActiveTab('stats')
                            loadStats()
                        }}
                        className={`px-6 py-3 rounded-lg font-semibold transition-colors ${activeTab === 'stats'
                            ? 'bg-blue-600 text-white'
                            : 'bg-white/10 text-white/70 hover:bg-white/20'
                            }`}
                    >
                        Memory Stats
                    </button>
                    <button
                        onClick={() => setActiveTab('intent')}
                        className={`px-6 py-3 rounded-lg font-semibold transition-colors ${activeTab === 'intent'
                            ? 'bg-fuchsia-600 text-white'
                            : 'bg-white/10 text-white/70 hover:bg-white/20'
                            }`}
                    >
                        Agent Intent (LLM)
                    </button>
                </div>

                {/* Intent Tab */}
                {activeTab === 'intent' && (
                    <div className="bg-white/10 backdrop-blur-lg rounded-xl shadow-xl border border-fuchsia-500/40 p-6 mb-6 space-y-4">
                        <div className="flex items-center justify-between gap-4 mb-2">
                            <div>
                                <h2 className="text-2xl font-bold text-white">
                                    🧠 NAVI Intent Classifier
                                </h2>
                                <p className="text-blue-200 text-sm">
                                    Describe what you want NAVI to do. AEP will classify the
                                    request and pick the right tools and workflow.
                                </p>
                            </div>
                            {renderModelDropdown()}
                        </div>

                        <div className="space-y-3">
                            <label className="block text-white font-semibold mb-1 text-sm">
                                Instruction to NAVI
                            </label>
                            <textarea
                                value={agentInput}
                                onChange={(e) => setAgentInput(e.target.value)}
                                placeholder="Example: Fix the flaky tests in backend/agent that only fail on CI, and update the deployment pipeline if needed."
                                className="w-full min-h-[140px] px-4 py-3 rounded-lg bg-black/30 border border-white/20 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-fuchsia-500"
                            />

                            <div className="flex items-center justify-between mt-1">
                                <button
                                    onClick={handleClassifyIntent}
                                    disabled={loading}
                                    className="inline-flex items-center justify-center gap-2 bg-fuchsia-600 hover:bg-fuchsia-700 disabled:bg-gray-600 text-white font-bold py-2.5 px-6 rounded-full text-sm transition-colors"
                                >
                                    {loading ? '🌀 Classifying…' : '⚡ Classify Intent'}
                                </button>
                                <span className="text-xs text-blue-200/70">
                                    Session ID:{' '}
                                    <span className="font-mono text-blue-100">
                                        web-{userId || 'anonymous'}
                                    </span>
                                </span>
                            </div>
                        </div>

                        {error && (
                            <div className="bg-red-500/20 border border-red-500 rounded-lg p-4">
                                <p className="text-red-200 text-sm">❌ {error}</p>
                                <p className="text-red-200/70 text-xs mt-1">
                                    💡 If backend is not running, start it with: <code>./start_backend_dev.sh</code>
                                </p>
                            </div>
                        )}

                        {intentResult && (
                            <div className="mt-4 bg-black/30 border border-white/15 rounded-xl p-5 space-y-3">
                                {intentResult.raw_text?.includes('[DEMO]') && (
                                    <div className="bg-blue-500/20 border border-blue-500/40 rounded-lg p-2 text-xs text-blue-200">
                                        🔬 Demo Mode: Using mock classification (start backend for real LLM classification)
                                    </div>
                                )}
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <span className="px-2 py-0.5 rounded-full bg-fuchsia-600/30 text-fuchsia-100 text-[0.65rem] uppercase tracking-wide">
                                            Intent
                                        </span>
                                        <span className="font-mono text-xs text-fuchsia-100">
                                            {intentResult.intent.family} / {intentResult.intent.kind}
                                        </span>
                                    </div>
                                    <div className="flex flex-col items-end text-[0.7rem] text-blue-200/80">
                                        <span>
                                            Model:{' '}
                                            <span className="font-mono text-blue-100">
                                                {intentResult.model_used || selectedModel}
                                            </span>
                                        </span>
                                        {intentResult.provider_used && (
                                            <span>
                                                Provider:{' '}
                                                <span className="font-mono text-blue-100">
                                                    {intentResult.provider_used}
                                                </span>
                                            </span>
                                        )}
                                    </div>
                                </div>

                                <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-[0.7rem] text-blue-100/80 mt-1">
                                    <div>
                                        Priority:{' '}
                                        <span className="font-mono text-blue-50">
                                            {intentResult.intent.priority || 'NORMAL'}
                                        </span>
                                    </div>
                                    <div>
                                        Confidence:{' '}
                                        <span className="font-mono text-blue-50">
                                            {typeof intentResult.intent.confidence === 'number'
                                                ? intentResult.intent.confidence.toFixed(2)
                                                : '—'}
                                        </span>
                                    </div>
                                    {intentResult.workflow && (
                                        <>
                                            <div>
                                                Autonomy:{' '}
                                                <span className="font-mono text-blue-50">
                                                    {intentResult.workflow.autonomy_mode || 'ASSISTED'}
                                                </span>
                                            </div>
                                            <div>
                                                Max steps:{' '}
                                                <span className="font-mono text-blue-50">
                                                    {intentResult.workflow.max_steps ?? '—'}
                                                </span>
                                            </div>
                                            <div>
                                                Auto-run tests:{' '}
                                                <span className="font-mono text-blue-50">
                                                    {intentResult.workflow.auto_run_tests ? 'yes' : 'no'}
                                                </span>
                                            </div>
                                        </>
                                    )}
                                </div>

                                {intentResult.raw_text && (
                                    <div className="mt-3 pt-3 border-t border-white/10 text-xs text-blue-100/80">
                                        <div className="font-semibold mb-1 text-blue-50">
                                            Normalised request:
                                        </div>
                                        <div className="font-mono text-[0.7rem] whitespace-pre-wrap">
                                            {intentResult.raw_text}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}

                {/* Search Tab */}
                {activeTab === 'search' && (
                    <>
                        {/* Search Controls */}
                        <div className="bg-white/10 backdrop-blur-lg rounded-xl shadow-xl border border-white/20 p-6 mb-6">
                            <div className="space-y-4">
                                {/* Query Input */}
                                <div>
                                    <label className="block text-white font-semibold mb-2">Search Query</label>
                                    <input
                                        type="text"
                                        value={query}
                                        onChange={(e) => setQuery(e.target.value)}
                                        onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                                        placeholder="e.g., What's the dev environment URL?"
                                        className="w-full px-4 py-3 rounded-lg bg-white/10 border border-white/20 text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>

                                {/* User ID */}
                                <div>
                                    <label className="block text-white font-semibold mb-2">User ID</label>
                                    <input
                                        type="text"
                                        value={userId}
                                        onChange={(e) => setUserId(e.target.value)}
                                        className="w-full px-4 py-3 rounded-lg bg-white/10 border border-white/20 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>

                                {/* Categories */}
                                <div>
                                    <label className="block text-white font-semibold mb-2">Categories</label>
                                    <div className="flex flex-wrap gap-2">
                                        {['profile', 'workspace', 'task', 'interaction'].map((cat) => (
                                            <button
                                                key={cat}
                                                onClick={() => toggleCategory(cat)}
                                                className={`px-4 py-2 rounded-lg font-medium transition-colors ${categories.includes(cat)
                                                    ? 'bg-blue-600 text-white'
                                                    : 'bg-white/10 text-white/70 hover:bg-white/20'
                                                    }`}
                                            >
                                                {CATEGORY_EMOJIS[cat]} {cat}
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                {/* Advanced Options */}
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="block text-white font-semibold mb-2">
                                            Max Results: {limit}
                                        </label>
                                        <input
                                            type="range"
                                            min="1"
                                            max="20"
                                            value={limit}
                                            onChange={(e) => setLimit(Number(e.target.value))}
                                            className="w-full"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-white font-semibold mb-2">
                                            Min Importance: {minImportance}
                                        </label>
                                        <input
                                            type="range"
                                            min="1"
                                            max="5"
                                            value={minImportance}
                                            onChange={(e) => setMinImportance(Number(e.target.value))}
                                            className="w-full"
                                        />
                                    </div>
                                </div>

                                {/* Search Button */}
                                <button
                                    onClick={handleSearch}
                                    disabled={loading}
                                    className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white font-bold py-3 px-6 rounded-lg transition-colors"
                                >
                                    {loading ? '🔍 Searching...' : '🔍 Search Memory'}
                                </button>
                            </div>
                        </div>

                        {/* Error Display */}
                        {error && (
                            <div className="bg-red-500/20 border border-red-500 rounded-lg p-4 mb-6">
                                <p className="text-red-200">❌ {error}</p>
                            </div>
                        )}

                        {/* Results */}
                        {results && (
                            <div className="bg-white/10 backdrop-blur-lg rounded-xl shadow-xl border border-white/20 p-6">
                                <div className="flex items-center justify-between mb-4">
                                    <h2 className="text-2xl font-bold text-white">
                                        📊 Results ({results.total})
                                    </h2>
                                    <span className="text-blue-200">Query: "{results.query}"</span>
                                </div>

                                {results.total === 0 ? (
                                    <div className="text-center py-12">
                                        <p className="text-white/70 text-lg">
                                            No results found. Try:
                                        </p>
                                        <ul className="text-white/50 mt-4 space-y-2">
                                            <li>• Syncing Jira/Confluence data first (Step 2)</li>
                                            <li>• Adjusting category filters</li>
                                            <li>• Lowering min importance threshold</li>
                                            <li>• Using different search terms</li>
                                        </ul>
                                    </div>
                                ) : (
                                    <div className="space-y-4">
                                        {results.results.map((result, idx) => (
                                            <div
                                                key={result.id}
                                                className="bg-white/5 rounded-lg p-5 border border-white/10 hover:bg-white/10 transition-colors"
                                            >
                                                <div className="flex items-start justify-between mb-2">
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-2xl">
                                                            {CATEGORY_EMOJIS[result.category]}
                                                        </span>
                                                        <span className="text-blue-300 font-semibold">
                                                            [{idx + 1}] {result.category}
                                                        </span>
                                                        {result.scope && (
                                                            <span className="text-white/50 text-sm">
                                                                ({result.scope})
                                                            </span>
                                                        )}
                                                    </div>
                                                    <div className="flex gap-3 text-sm">
                                                        <span className="bg-green-600/30 text-green-200 px-2 py-1 rounded">
                                                            {(result.similarity * 100).toFixed(1)}% match
                                                        </span>
                                                        <span className="bg-purple-600/30 text-purple-200 px-2 py-1 rounded">
                                                            Importance: {result.importance}/5
                                                        </span>
                                                    </div>
                                                </div>

                                                {result.title && (
                                                    <h3 className="text-white font-semibold text-lg mb-2">
                                                        {result.title}
                                                    </h3>
                                                )}

                                                <p className="text-white/80 leading-relaxed">
                                                    {highlightQuery(result.content)}
                                                </p>

                                                {result.meta && Object.keys(result.meta).length > 0 && (
                                                    <div className="mt-3 pt-3 border-t border-white/10">
                                                        <details className="text-white/60 text-sm">
                                                            <summary className="cursor-pointer hover:text-white/80">
                                                                Metadata
                                                            </summary>
                                                            <pre className="mt-2 bg-black/30 p-2 rounded overflow-auto">
                                                                {JSON.stringify(result.meta, null, 2)}
                                                            </pre>
                                                        </details>
                                                    </div>
                                                )}

                                                {result.created_at && (
                                                    <div className="mt-2 text-white/40 text-xs">
                                                        Created: {new Date(result.created_at).toLocaleString()}
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                    </>
                )}

                {/* Stats Tab */}
                {activeTab === 'stats' && (
                    <div className="bg-white/10 backdrop-blur-lg rounded-xl shadow-xl border border-white/20 p-6">
                        <h2 className="text-2xl font-bold text-white mb-6">📈 Memory Statistics</h2>

                        {loading ? (
                            <div className="text-center py-12">
                                <p className="text-white/70 text-lg">Loading stats...</p>
                            </div>
                        ) : stats ? (
                            <div className="space-y-6">
                                <div className="bg-white/5 rounded-lg p-6 border border-white/10">
                                    <div className="text-center">
                                        <div className="text-5xl font-bold text-blue-400 mb-2">
                                            {stats.total_memories}
                                        </div>
                                        <div className="text-white/70">Total Memories</div>
                                    </div>
                                </div>

                                <div className="grid grid-cols-2 gap-4">
                                    {Object.entries(stats.by_category).map(([category, count]) => (
                                        <div
                                            key={category}
                                            className="bg-white/5 rounded-lg p-5 border border-white/10"
                                        >
                                            <div className="flex items-center gap-3 mb-2">
                                                <span className="text-3xl">{CATEGORY_EMOJIS[category]}</span>
                                                <span className="text-white font-semibold capitalize">
                                                    {category}
                                                </span>
                                            </div>
                                            <div className="text-3xl font-bold text-blue-400">{count}</div>
                                        </div>
                                    ))}
                                </div>

                                {stats.total_memories === 0 && (
                                    <div className="bg-yellow-500/20 border border-yellow-500 rounded-lg p-4">
                                        <p className="text-yellow-200">
                                            ⚠️ No memory data found for user "{userId}".
                                            Run org sync to populate memory:
                                        </p>
                                        <ul className="mt-2 text-yellow-200/80 text-sm space-y-1">
                                            <li>• POST /api/org/sync/jira</li>
                                            <li>• POST /api/org/sync/confluence</li>
                                        </ul>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="text-center py-12">
                                <p className="text-white/70">Click "Memory Stats" to load data</p>
                            </div>
                        )}
                    </div>
                )}

                {/* Example Queries */}
                <div className="mt-6 bg-white/5 backdrop-blur-lg rounded-xl border border-white/10 p-6">
                    <h3 className="text-white font-semibold mb-3">💡 Example Queries:</h3>

                    {activeTab === 'search' && (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            {[
                                "What's the dev environment URL?",
                                "Any Confluence pages for LAB-158?",
                                "Where did we discuss barcode overrides?",
                                "Show me my current tasks",
                                "What are my preferences?",
                                "Find documentation about deployment",
                            ].map((example) => (
                                <button
                                    key={example}
                                    onClick={() => setQuery(example)}
                                    className="text-left px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg text-white/80 hover:text-white transition-colors"
                                >
                                    "{example}"
                                </button>
                            ))}
                        </div>
                    )}

                    {activeTab === 'intent' && (
                        <div className="grid grid-cols-1 gap-3">
                            {[
                                "Fix the flaky tests in backend/agent that only fail on CI",
                                "Create a new React component for user authentication",
                                "Review and optimize the database queries in the user service",
                                "Update the deployment pipeline to use the new staging environment",
                                "Debug the memory leak in the web worker threads",
                                "Add comprehensive logging to the payment processing module",
                            ].map((example) => (
                                <button
                                    key={example}
                                    onClick={() => setAgentInput(example)}
                                    className="text-left px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg text-white/80 hover:text-white transition-colors"
                                >
                                    "{example}"
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
