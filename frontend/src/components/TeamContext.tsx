import React, { useState } from 'react'

const TeamContext: React.FC = () => {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const searchContext = async () => {
    if (!query.trim()) return
    
    setLoading(true)
    try {
      const response = await fetch('http://localhost:8000/api/team-context', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          project_id: 'demo',
          limit: 5
        })
      })
      const result = await response.json()
      setResults(result)
    } catch (error) {
      console.error('Search failed:', error)
      setResults({ error: 'Failed to search team context' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
            Team Knowledge Search
          </h3>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Search Query
              </label>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && searchContext()}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                placeholder="Search team discussions, decisions, code patterns..."
              />
            </div>
            
            <button
              onClick={searchContext}
              disabled={loading || !query.trim()}
              className="px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50"
            >
              {loading ? '🔍 Searching...' : '🔍 Search Knowledge'}
            </button>
          </div>
        </div>
      </div>

      {results && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
              Search Results
            </h3>
            
            {results.error ? (
              <div className="text-red-600 p-4 bg-red-50 rounded-lg">
                {results.error}
              </div>
            ) : (
              <div className="space-y-4">
                {[
                  { title: 'API Design Guidelines', content: 'Team decision on RESTful API standards...', type: 'decision', date: '2 days ago' },
                  { title: 'Authentication Pattern', content: 'JWT implementation discussion and best practices...', type: 'discussion', date: '1 week ago' },
                  { title: 'Database Schema Changes', content: 'Migration strategy for user table updates...', type: 'code', date: '3 days ago' },
                  { title: 'Performance Optimization', content: 'Caching layer implementation results...', type: 'analysis', date: '5 days ago' }
                ].map((item, index) => (
                  <div key={index} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <h4 className="font-medium text-gray-900">{item.title}</h4>
                        <p className="text-sm text-gray-600 mt-1">{item.content}</p>
                        <div className="flex items-center mt-2 space-x-4">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            item.type === 'decision' ? 'bg-blue-100 text-blue-800' :
                            item.type === 'discussion' ? 'bg-green-100 text-green-800' :
                            item.type === 'code' ? 'bg-purple-100 text-purple-800' :
                            'bg-gray-100 text-gray-800'
                          }`}>
                            {item.type}
                          </span>
                          <span className="text-xs text-gray-500">{item.date}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Quick Access */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
            Quick Access
          </h3>
          
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { name: 'Recent Decisions', icon: '📋', count: 12 },
              { name: 'Code Patterns', icon: '🔧', count: 8 },
              { name: 'Team Discussions', icon: '💬', count: 24 },
              { name: 'Best Practices', icon: '⭐', count: 15 }
            ].map((item) => (
              <div key={item.name} className="text-center p-4 border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer">
                <div className="text-2xl mb-2">{item.icon}</div>
                <div className="text-sm font-medium text-gray-900">{item.name}</div>
                <div className="text-xs text-gray-500">{item.count} items</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export default TeamContext
