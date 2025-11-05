import React from 'react'
import { Routes, Route, Link, useLocation } from 'react-router-dom'
import { MemoryGraphPage } from './pages/MemoryGraphPage'
import { PlansListPage } from './pages/PlansListPage'
import { PlanView } from './pages/PlanView'
import ConciergePage from './pages/ConciergePage'

function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center p-8">
      <div className="max-w-2xl w-full bg-white/10 backdrop-blur-lg rounded-2xl shadow-2xl border border-white/20 p-8">
        <h1 className="text-4xl font-bold text-white mb-6 text-center">
          🤖 Autonomous Engineering Platform
        </h1>
        <div className="space-y-4">
          <div className="bg-white/5 rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-3 text-white">Available Features</h2>
            <ul className="space-y-3">
              <li>
                <Link 
                  to="/concierge" 
                  className="block bg-emerald-600 hover:bg-emerald-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors text-center"
                >
                  🌟 Task Concierge
                </Link>
              </li>
              <li>
                <Link 
                  to="/memory/graph" 
                  className="block bg-purple-600 hover:bg-purple-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors text-center"
                >
                  📊 Memory Graph Explorer
                </Link>
              </li>
              <li>
                <Link 
                  to="/plans" 
                  className="block bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors text-center"
                >
                  📋 Live Plan Mode
                </Link>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  
  // Don't show nav on home page
  if (location.pathname === '/') {
    return <>{children}</>
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <Link to="/" className="text-xl font-bold text-gray-900 hover:text-purple-600 transition-colors">
              🤖 AEP
            </Link>
            <div className="flex space-x-6">
              <Link 
                to="/memory/graph" 
                className="text-gray-700 hover:text-purple-600 font-medium transition-colors"
              >
                Memory Graph
              </Link>
              <Link 
                to="/plans" 
                className="text-gray-700 hover:text-indigo-600 font-medium transition-colors"
              >
                📋 Plans
              </Link>
            </div>
          </div>
        </div>
      </nav>
      {children}
    </div>
  )
}

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/concierge" element={<ConciergePage />} />
        <Route path="/memory/graph" element={<MemoryGraphPage />} />
        <Route path="/plans" element={<PlansListPage />} />
        <Route path="/plan/:id" element={<PlanView />} />
      </Routes>
    </Layout>
  )
}

export default App
