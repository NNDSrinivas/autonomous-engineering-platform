import { useEffect, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { toast } from '@/components/ui/use-toast'
import { getAuthToken, isAdminUser } from '@/utils/auth'

type AuditRetentionStatus = {
  enabled: boolean
  retention_days: number
  overdue_count: number
  cutoff_iso: string
}

type JwtStatus = {
  enabled: boolean
  has_primary_secret: boolean
  has_previous_secrets: boolean
  rotation_ready: boolean
}

type EncryptionStatus = {
  audit_encryption_enabled: boolean
  audit_encryption_key_id: string | null
  token_encryption_configured: boolean
  token_encryption_key_id: string | null
}

type SsoStatus = {
  auth0_domain: string
  auth0_client_configured: boolean
  auth0_audience_configured: boolean
  device_flow_enabled: boolean
}

type SecurityStatus = {
  jwt: JwtStatus
  encryption: EncryptionStatus
  audit_retention: AuditRetentionStatus
  sso: SsoStatus
}

const STATUS_OK = 'bg-emerald-500/10 text-emerald-200 border-emerald-500/30'
const STATUS_WARN = 'bg-amber-500/10 text-amber-200 border-amber-500/30'
const STATUS_ERR = 'bg-rose-500/10 text-rose-200 border-rose-500/30'

function statusBadge(ok: boolean, warn = false) {
  if (ok) return STATUS_OK
  return warn ? STATUS_WARN : STATUS_ERR
}

export default function AdminSecurityPage() {
  const isAdmin = isAdminUser()
  const [status, setStatus] = useState<SecurityStatus | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    loadStatus(controller.signal)
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function loadStatus(signal?: AbortSignal) {
    setLoading(true)
    try {
      const headers = new Headers()
      const token = getAuthToken()
      if (token) headers.set('Authorization', `Bearer ${token}`)
      const response = await fetch('/api/admin/security/status', { headers, signal })
      if (!response.ok) {
        throw new Error(`Failed to load security status (${response.status})`)
      }
      const data = await response.json()
      setStatus(data)
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') return
      toast({
        title: 'Failed to load security status',
        description: 'Check backend connectivity or admin permissions.',
        variant: 'destructive',
      })
    } finally {
      setLoading(false)
    }
  }

  if (!isAdmin) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 p-8">
        <div className="max-w-3xl mx-auto">
          <h1 className="text-3xl font-semibold mb-4">Admin Security Console</h1>
          <p className="text-slate-300">
            This view is restricted to administrators. Please sign in with admin access.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="max-w-6xl mx-auto px-8 py-10 space-y-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-semibold">Enterprise Security Console</h1>
            <p className="text-slate-400 mt-2">
              Live snapshot of auth, encryption, and retention posture.
            </p>
          </div>
          <Button onClick={() => loadStatus()} disabled={loading}>
            {loading ? 'Refreshing...' : 'Refresh'}
          </Button>
        </div>

        {!status ? (
          <div className="text-slate-400">Loading security posture…</div>
        ) : (
          <div className="grid gap-6 md:grid-cols-2">
            <Card className="border-slate-800 bg-slate-900/60">
              <CardHeader>
                <CardTitle className="text-lg">JWT Rotation</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-slate-300">
                <div className="flex items-center justify-between">
                  <span>JWT enabled</span>
                  <Badge className={statusBadge(status.jwt.enabled)}>
                    {status.jwt.enabled ? 'Enabled' : 'Disabled'}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span>Primary secret set</span>
                  <Badge className={statusBadge(status.jwt.has_primary_secret, true)}>
                    {status.jwt.has_primary_secret ? 'Present' : 'Missing'}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span>Previous secrets set</span>
                  <Badge className={statusBadge(status.jwt.has_previous_secrets, true)}>
                    {status.jwt.has_previous_secrets ? 'Configured' : 'None'}
                  </Badge>
                </div>
                <Separator className="bg-slate-800" />
                <div className="flex items-center justify-between">
                  <span>Rotation readiness</span>
                  <Badge className={statusBadge(status.jwt.rotation_ready, true)}>
                    {status.jwt.rotation_ready ? 'Ready' : 'Not ready'}
                  </Badge>
                </div>
                <p className="text-xs text-slate-400">
                  Rotation is ready when both JWT_SECRET and JWT_SECRET_PREVIOUS are configured.
                </p>
              </CardContent>
            </Card>

            <Card className="border-slate-800 bg-slate-900/60">
              <CardHeader>
                <CardTitle className="text-lg">SSO / Device Flow</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-slate-300">
                <div className="flex items-center justify-between">
                  <span>Auth0 domain</span>
                  <span className="text-slate-400">{status.sso.auth0_domain}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Client configured</span>
                  <Badge className={statusBadge(status.sso.auth0_client_configured, true)}>
                    {status.sso.auth0_client_configured ? 'Configured' : 'Missing'}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span>Audience configured</span>
                  <Badge className={statusBadge(status.sso.auth0_audience_configured, true)}>
                    {status.sso.auth0_audience_configured ? 'Configured' : 'Missing'}
                  </Badge>
                </div>
                <Separator className="bg-slate-800" />
                <div className="flex items-center justify-between">
                  <span>Device flow enabled</span>
                  <Badge className={statusBadge(status.sso.device_flow_enabled, true)}>
                    {status.sso.device_flow_enabled ? 'Enabled' : 'Disabled'}
                  </Badge>
                </div>
              </CardContent>
            </Card>

            <Card className="border-slate-800 bg-slate-900/60">
              <CardHeader>
                <CardTitle className="text-lg">Encryption at Rest</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-slate-300">
                <div className="flex items-center justify-between">
                  <span>Audit payload encryption</span>
                  <Badge
                    className={statusBadge(status.encryption.audit_encryption_enabled, true)}
                  >
                    {status.encryption.audit_encryption_enabled ? 'Enabled' : 'Disabled'}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span>Audit key ID</span>
                  <span className="text-slate-400">
                    {status.encryption.audit_encryption_key_id || 'Not set'}
                  </span>
                </div>
                <Separator className="bg-slate-800" />
                <div className="flex items-center justify-between">
                  <span>Token encryption (KMS)</span>
                  <Badge
                    className={statusBadge(status.encryption.token_encryption_configured, true)}
                  >
                    {status.encryption.token_encryption_configured ? 'Configured' : 'Missing'}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span>KMS key ID</span>
                  <span className="text-slate-400">
                    {status.encryption.token_encryption_key_id || 'Not set'}
                  </span>
                </div>
              </CardContent>
            </Card>

            <Card className="border-slate-800 bg-slate-900/60">
              <CardHeader>
                <CardTitle className="text-lg">Audit Retention</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-slate-300">
                <div className="flex items-center justify-between">
                  <span>Retention enabled</span>
                  <Badge className={statusBadge(status.audit_retention.enabled, true)}>
                    {status.audit_retention.enabled ? 'Enabled' : 'Disabled'}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span>Retention days</span>
                  <span className="text-slate-400">
                    {status.audit_retention.retention_days}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Overdue rows</span>
                  <Badge
                    className={statusBadge(status.audit_retention.overdue_count === 0, true)}
                  >
                    {status.audit_retention.overdue_count}
                  </Badge>
                </div>
                <p className="text-xs text-slate-400">
                  Cutoff: {new Date(status.audit_retention.cutoff_iso).toLocaleString()}
                </p>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  )
}
