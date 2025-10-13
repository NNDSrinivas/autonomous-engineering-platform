import React, { useState, useEffect } from 'react'

interface PlatformHealth {
  status: string
  service: string
  version: string
  components: {
    llm_service: boolean
    vector_store: boolean
    github_integration: boolean
    jira_integration: boolean
  }
}

const Dashboard: React.FC = () => {
  const [health, setHealth] = useState<PlatformHealth | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchHealth()
  }, [])

  const fetchHealth = async () => {
    try {
      const response = await fetch('http://localhost:8000/health')
      const data = await response.json()
      setHealth(data)
    } catch (error) {
      console.error('Failed to fetch health:', error)
    } finally {
      setLoading(false)
    }
  }

  const stats = [
    { name: 'Active Projects', value: '3', icon: '📁', change: '+2 this week' },
    { name: 'Code Reviews', value: '12', icon: '👀', change: '+4 today' },
    { name: 'AI Suggestions', value: '47', icon: '🤖', change: '+15 today' },
    { name: 'Team Members', value: '8', icon: '👥', change: '2 online now' }
  ]

  return (
    <div className="space-y-6">
      {/* Platform Status */}
      <div className="bg-white overflow-hidden shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
            Platform Status
          </h3>
          {loading ? (
            <div className="animate-pulse">
              <div className="h-4 bg-gray-200 rounded w-1/3 mb-2"></div>
              <div className="h-4 bg-gray-200 rounded w-1/2"></div>
            </div>
          ) : health ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center">
                <div className={`h-3 w-3 rounded-full mx-auto mb-2 ${
                  health.components.llm_service ? 'bg-green-400' : 'bg-red-400'
                }`}></div>
                <p className="text-sm text-gray-600">LLM Service</p>
              </div>
              <div className="text-center">
                <div className={`h-3 w-3 rounded-full mx-auto mb-2 ${
                  health.components.vector_store ? 'bg-green-400' : 'bg-red-400'
                }`}></div>
                <p className="text-sm text-gray-600">Vector Store</p>
              </div>
              <div className="text-center">
                <div className={`h-3 w-3 rounded-full mx-auto mb-2 ${
                  health.components.github_integration ? 'bg-green-400' : 'bg-yellow-400'
                }`}></div>
                <p className="text-sm text-gray-600">GitHub</p>
              </div>
              <div className="text-center">
                <div className={`h-3 w-3 rounded-full mx-auto mb-2 ${
                  health.components.jira_integration ? 'bg-green-400' : 'bg-yellow-400'
                }`}></div>
                <p className="text-sm text-gray-600">JIRA</p>
              </div>
            </div>
          ) : (
            <p className="text-red-600">Failed to load platform status</p>
          )}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat) => (
          <div key={stat.name} className="bg-white overflow-hidden shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <span className="text-2xl">{stat.icon}</span>
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">
                      {stat.name}
                    </dt>
                    <dd className="text-lg font-medium text-gray-900">
                      {stat.value}
                    </dd>
                  </dl>
                </div>
              </div>
              <div className="mt-4">
                <div className="text-sm text-gray-600">{stat.change}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Recent Activity */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
            Recent Activity
          </h3>
          <div className="space-y-3">
            {[
              { action: 'Code analysis completed', project: 'user-auth-service', time: '2 minutes ago', icon: '🔍' },
              { action: 'PR review suggestions generated', project: 'api-gateway', time: '5 minutes ago', icon: '💡' },
              { action: 'Team knowledge updated', project: 'frontend-components', time: '12 minutes ago', icon: '📚' },
              { action: 'Autonomous refactoring proposed', project: 'payment-processor', time: '25 minutes ago', icon: '🤖' }
            ].map((activity, index) => (
              <div key={index} className="flex items-center space-x-3 p-3 rounded-lg hover:bg-gray-50">
                <span className="text-lg">{activity.icon}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900">{activity.action}</p>
                  <p className="text-sm text-gray-500">{activity.project}</p>
                </div>
                <div className="text-sm text-gray-400">{activity.time}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
