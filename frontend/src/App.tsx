import React from 'react'
import { Routes, Route, Link, useLocation } from 'react-router-dom'
import { MemoryGraphPage } from './pages/MemoryGraphPage'
import { PlansListPage } from './pages/PlansListPage'
import { PlanView } from './pages/PlanView'
import ConciergePage from './pages/ConciergePage'
import { NaviSearchPage } from './pages/NaviSearchPage'
import ExtensionMarketplacePage from './pages/ExtensionMarketplacePage'
import EnterpriseProjectsPage from './pages/EnterpriseProjectsPage'
import GateApprovalsPage from './pages/GateApprovalsPage'
import AdminAuditPage from './pages/AdminAuditPage'
import AdminSecurityPage from './pages/AdminSecurityPage'
import { isAdminUser } from './utils/auth'
// import NaviRoot from './components/navi/NaviRoot'
import { WorkspaceProvider } from './context/WorkspaceContext'

function HomePage() {
  const isAdmin = isAdminUser()
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
              <li>
                <Link
                  to="/navi/search"
                  className="block bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors text-center"
                >
                  🔍 NAVI RAG Search
                </Link>
              </li>
              <li>
                <Link
                  to="/extensions"
                  className="block bg-violet-600 hover:bg-violet-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors text-center"
                >
                  🧩 Extension Marketplace
                </Link>
              </li>
              <li>
                <Link
                  to="/enterprise/projects"
                  className="block bg-gradient-to-r from-orange-500 to-red-600 hover:from-orange-600 hover:to-red-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors text-center"
                >
                  🚀 Enterprise Projects
                </Link>
              </li>
              {isAdmin ? (
                <>
                  <li>
                    <Link
                      to="/admin/security"
                      className="block bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors text-center"
                    >
                      🔐 Admin Security Console
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/admin/audit"
                      className="block bg-gradient-to-r from-cyan-500 to-sky-600 hover:from-cyan-600 hover:to-sky-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors text-center"
                    >
                      🛡️ Admin Audit Console
                    </Link>
                  </li>
                </>
              ) : null}
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const isAdmin = isAdminUser()

  // Don't show nav on home page or NAVI webview
  if (location.pathname === '/' || location.pathname === '/navi') {
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
              <Link
                to="/navi/search"
                className="text-gray-700 hover:text-blue-600 font-medium transition-colors"
              >
                🔍 NAVI Search
              </Link>
              <Link
                to="/extensions"
                className="text-gray-700 hover:text-violet-600 font-medium transition-colors"
              >
                🧩 Extensions
              </Link>
              <Link
                to="/enterprise/projects"
                className="text-gray-700 hover:text-orange-600 font-medium transition-colors"
              >
                🚀 Enterprise
              </Link>
              {isAdmin ? (
                <>
                  <Link
                    to="/admin/security"
                    className="text-gray-700 hover:text-emerald-600 font-medium transition-colors"
                  >
                    🔐 Admin Security
                  </Link>
                  <Link
                    to="/admin/audit"
                    className="text-gray-700 hover:text-cyan-600 font-medium transition-colors"
                  >
                    🛡️ Admin Audit
                  </Link>
                </>
              ) : null}
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
    <WorkspaceProvider>
      <Layout>
        <Routes>
          <Route path="/" element={<HomePage />} />
          {/* <Route path="/navi" element={<NaviRoot />} /> */}
          <Route path="/concierge" element={<ConciergePage />} />
          <Route path="/memory/graph" element={<MemoryGraphPage />} />
          <Route path="/plans" element={<PlansListPage />} />
          <Route path="/plan/:id" element={<PlanView />} />
          <Route path="/navi/search" element={<NaviSearchPage />} />
          <Route path="/extensions" element={<ExtensionMarketplacePage />} />
          <Route path="/enterprise/projects" element={<EnterpriseProjectsPage />} />
          <Route path="/enterprise/projects/:id" element={<EnterpriseProjectsPage />} />
          <Route path="/enterprise/approvals" element={<GateApprovalsPage />} />
          <Route path="/admin/audit" element={<AdminAuditPage />} />
          <Route path="/admin/security" element={<AdminSecurityPage />} />
        </Routes>
      </Layout>
    </WorkspaceProvider>
  )
}

export default App
