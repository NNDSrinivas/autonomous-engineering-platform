import React from 'react'
import { Routes, Route, Link, useLocation } from 'react-router-dom'
import {
  Activity,
  ArrowRight,
  Brain,
  Building2,
  ChartNoAxesCombined,
  GitBranch,
  Lock,
  Radar,
  ScrollText,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
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
import NaviRoot from './components/navi/NaviRoot'
import { WorkspaceProvider } from './context/WorkspaceContext'

type HomeModule = {
  title: string
  description: string
  href: string
  status: string
}

const CORE_MODULES: HomeModule[] = [
  {
    title: 'Task Concierge',
    description: 'Plan and execute multi-step engineering workflows with guardrails.',
    href: '/concierge',
    status: 'Core',
  },
  {
    title: 'Memory Graph',
    description: 'Explore persistent repo intelligence and architecture context.',
    href: '/memory/graph',
    status: 'Core',
  },
  {
    title: 'Live Plan Mode',
    description: 'Track active plans, execution checkpoints, and outcomes.',
    href: '/plans',
    status: 'Core',
  },
  {
    title: 'NAVI RAG Search',
    description: 'Query indexed workspace knowledge with retrieval-backed answers.',
    href: '/navi/search',
    status: 'Core',
  },
  {
    title: 'Extension Marketplace',
    description: 'Discover and configure platform integrations and connectors.',
    href: '/extensions',
    status: 'Integrations',
  },
  {
    title: 'Enterprise Projects',
    description: 'Operate project-level controls, approvals, and workspace governance.',
    href: '/enterprise/projects',
    status: 'Governance',
  },
]

const ADMIN_MODULES: HomeModule[] = [
  {
    title: 'Admin Security Console',
    description: 'Manage access posture, controls, and policy enforcement.',
    href: '/admin/security',
    status: 'Admin',
  },
  {
    title: 'Admin Audit Console',
    description: 'Review compliance trails, runtime decisions, and accountability signals.',
    href: '/admin/audit',
    status: 'Admin',
  },
]

function HomePage() {
  const isAdmin = isAdminUser()
  const modules = isAdmin ? [...CORE_MODULES, ...ADMIN_MODULES] : CORE_MODULES

  return (
    <div className="aep-home">
      <div className="aep-home__mesh" aria-hidden="true" />
      <div className="aep-home__grid" aria-hidden="true" />

      <div className="aep-home__container">
        <section className="aep-home__hero">
          <div className="aep-home__hero-copy">
            <p className="aep-home__eyebrow">NAVI Control Center</p>
            <h1>Autonomous engineering infrastructure</h1>
            <p>
              Route tasks, enforce guardrails, and ship with auditable execution
              across your engineering surface.
            </p>
            <div className="aep-home__hero-actions">
              <Link to="/navi" className="aep-btn aep-btn--primary">
                Open NAVI workspace
              </Link>
              <Link to="/enterprise/projects" className="aep-btn aep-btn--ghost">
                View enterprise projects
              </Link>
            </div>
          </div>

          <aside className="aep-home__status-card">
            <h2>Runtime posture</h2>
            <ul>
              <li>
                <ShieldCheck size={16} />
                <span>Policy guardrails active</span>
              </li>
              <li>
                <GitBranch size={16} />
                <span>Branch-aware execution enabled</span>
              </li>
              <li>
                <Activity size={16} />
                <span>Live telemetry stream online</span>
              </li>
            </ul>
          </aside>
        </section>

        <section className="aep-home__metrics" aria-label="Platform metrics">
          <article className="aep-metric">
            <span className="aep-metric__label">Active Runs</span>
            <strong>24</strong>
            <span className="aep-metric__meta">
              <Radar size={14} /> Live
            </span>
          </article>
          <article className="aep-metric">
            <span className="aep-metric__label">Policy Blocks</span>
            <strong>3</strong>
            <span className="aep-metric__meta">
              <Lock size={14} /> Last 24h
            </span>
          </article>
          <article className="aep-metric">
            <span className="aep-metric__label">Model Routes</span>
            <strong>8</strong>
            <span className="aep-metric__meta">
              <Brain size={14} /> Multi-provider
            </span>
          </article>
          <article className="aep-metric">
            <span className="aep-metric__label">Audit Coverage</span>
            <strong>100%</strong>
            <span className="aep-metric__meta">
              <ScrollText size={14} /> Verified
            </span>
          </article>
        </section>

        <section className="aep-home__modules" aria-label="Platform modules">
          <div className="aep-home__modules-header">
            <h2>Operational modules</h2>
            <p>Choose the workflow surface you want to operate.</p>
          </div>
          <div className="aep-home__modules-grid">
            {modules.map((module) => (
              <Link key={module.href} to={module.href} className="aep-module-card">
                <div className="aep-module-card__top">
                  <span>{module.title}</span>
                  <span className="aep-module-card__tag">{module.status}</span>
                </div>
                <p>{module.description}</p>
                <span className="aep-module-card__cta">
                  Open module <ArrowRight size={14} />
                </span>
              </Link>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}

function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const isAdmin = isAdminUser()

  if (location.pathname === '/' || location.pathname === '/navi') {
    return <>{children}</>
  }

  return (
    <div className="min-h-screen bg-[hsl(var(--bg))] text-[hsl(var(--text))]">
      <nav className="border-b border-[hsl(var(--border)/0.75)] bg-[hsl(var(--panel)/0.92)] backdrop-blur-md">
        <div className="mx-auto flex max-w-[1320px] items-center justify-between px-6 py-4">
          <Link to="/" className="flex items-center gap-2 text-[15px] font-semibold tracking-tight text-[hsl(var(--text))]">
            <Sparkles className="h-4 w-4 text-[hsl(var(--brand-cyan))]" />
            NAVI Console
          </Link>
          <div className="flex flex-wrap items-center gap-5 text-[13px] text-[hsl(var(--muted))]">
            <Link to="/memory/graph" className="hover:text-[hsl(var(--text))] transition-colors">Memory Graph</Link>
            <Link to="/plans" className="hover:text-[hsl(var(--text))] transition-colors">Plans</Link>
            <Link to="/navi/search" className="hover:text-[hsl(var(--text))] transition-colors">Search</Link>
            <Link to="/extensions" className="hover:text-[hsl(var(--text))] transition-colors">Extensions</Link>
            <Link to="/enterprise/projects" className="hover:text-[hsl(var(--text))] transition-colors">
              <span className="inline-flex items-center gap-1">
                <Building2 className="h-3.5 w-3.5" />
                Enterprise
              </span>
            </Link>
            {isAdmin ? (
              <>
                <Link to="/admin/security" className="hover:text-[hsl(var(--text))] transition-colors">Admin Security</Link>
                <Link to="/admin/audit" className="hover:text-[hsl(var(--text))] transition-colors">Admin Audit</Link>
              </>
            ) : null}
            <span className="inline-flex items-center gap-1 rounded-full border border-[hsl(var(--border))] px-2 py-0.5 text-[11px] text-[hsl(var(--subtle))]">
              <ChartNoAxesCombined className="h-3 w-3" />
              Staging
            </span>
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
          <Route path="/navi" element={<NaviRoot />} />
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
