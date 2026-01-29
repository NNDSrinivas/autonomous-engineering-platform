import { useEffect, useMemo, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { toast } from '@/components/ui/use-toast'
import { getAuthToken, isAdminUser } from '@/utils/auth'

type AuditEntry = {
  id: number
  route: string
  method: string
  event_type: string
  org_key: string | null
  actor_sub: string | null
  actor_email: string | null
  resource_id: string | null
  status_code: number
  created_at: string
}

type AuditPayloadResponse = {
  id: number
  encrypted: boolean
  payload: Record<string, unknown>
}

const STATUS_COLORS: Record<string, string> = {
  ok: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30',
  warn: 'bg-amber-500/10 text-amber-200 border-amber-500/30',
  err: 'bg-rose-500/10 text-rose-200 border-rose-500/30',
}

const METHOD_COLORS: Record<string, string> = {
  POST: 'bg-indigo-500/15 text-indigo-200 border-indigo-400/30',
  PUT: 'bg-sky-500/15 text-sky-200 border-sky-400/30',
  PATCH: 'bg-cyan-500/15 text-cyan-200 border-cyan-400/30',
  DELETE: 'bg-rose-500/15 text-rose-200 border-rose-400/30',
}

function formatTimestamp(value: string) {
  const date = new Date(value)
  return date.toLocaleString()
}

function statusTone(status: number) {
  if (status >= 500) return STATUS_COLORS.err
  if (status >= 400) return STATUS_COLORS.warn
  return STATUS_COLORS.ok
}

function formatJSON(value: Record<string, unknown>) {
  return JSON.stringify(value, null, 2)
}

export default function AdminAuditPage() {
  const isAdmin = isAdminUser()
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<AuditEntry | null>(null)
  const [payload, setPayload] = useState<AuditPayloadResponse | null>(null)
  const [payloadLoading, setPayloadLoading] = useState(false)
  const [orgFilter, setOrgFilter] = useState('')
  const [actorFilter, setActorFilter] = useState('')
  const [routeFilter, setRouteFilter] = useState('')
  const [methodFilter, setMethodFilter] = useState('')
  const [limit] = useState(250)

  useEffect(() => {
    const controller = new AbortController()
    loadAuditEntries(controller.signal)
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orgFilter, actorFilter, limit])

  const filteredEntries = useMemo(() => {
    return entries.filter((entry) => {
      if (routeFilter && !entry.route.toLowerCase().includes(routeFilter.toLowerCase())) {
        return false
      }
      if (methodFilter && entry.method !== methodFilter) {
        return false
      }
      return true
    })
  }, [entries, routeFilter, methodFilter])

  const stats = useMemo(() => {
    const total = filteredEntries.length
    const errors = filteredEntries.filter((entry) => entry.status_code >= 400).length
    const uniqueActors = new Set(filteredEntries.map((entry) => entry.actor_sub || 'unknown')).size
    return { total, errors, uniqueActors }
  }, [filteredEntries])

  async function loadAuditEntries(signal?: AbortSignal) {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (orgFilter) params.append('org', orgFilter)
      if (actorFilter) params.append('actor', actorFilter)
      params.append('limit', String(limit))

      const headers = new Headers()
      const token = getAuthToken()
      if (token) {
        headers.set('Authorization', `Bearer ${token}`)
      }
      const response = await fetch(`/api/audit?${params.toString()}`, {
        signal,
        headers,
      })
      if (!response.ok) {
        throw new Error(`Failed to load audit entries (${response.status})`)
      }
      const data = await response.json()
      setEntries(data || [])
      setSelected(null)
      setPayload(null)
    } catch (error) {
      if ((error as Error).name !== 'AbortError') {
        toast({
          title: 'Audit feed error',
          description: 'Failed to load audit activity.',
          variant: 'destructive',
        })
      }
    } finally {
      setLoading(false)
    }
  }

  async function loadPayload(entry: AuditEntry, decrypt: boolean) {
    setPayloadLoading(true)
    try {
      const headers = new Headers()
      const token = getAuthToken()
      if (token) {
        headers.set('Authorization', `Bearer ${token}`)
      }
      const response = await fetch(
        `/api/audit/${entry.id}/payload?decrypt=${decrypt ? 'true' : 'false'}`,
        { headers }
      )
      if (!response.ok) {
        throw new Error(`Failed to load payload (${response.status})`)
      }
      const data = (await response.json()) as AuditPayloadResponse
      setPayload(data)
    } catch (error) {
      toast({
        title: decrypt ? 'Decrypt failed' : 'Payload load failed',
        description: 'Unable to load audit payload.',
        variant: 'destructive',
      })
    } finally {
      setPayloadLoading(false)
    }
  }

  const handleSelect = (entry: AuditEntry) => {
    setSelected(entry)
    setPayload(null)
    loadPayload(entry, false)
  }

  if (!isAdmin) {
    return (
      <div className="min-h-screen bg-[#0b0f18] text-slate-100 flex items-center justify-center">
        <Card className="bg-slate-900/70 border-slate-800 max-w-lg w-full">
          <CardHeader>
            <CardTitle>Admin access required</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-slate-400">
              The audit console is restricted to administrators. Please sign in with
              an admin account or set the role to access this view.
            </p>
            <div className="mt-4 text-xs text-slate-500">
              Hint: set <code>VITE_USER_ROLE=admin</code> or localStorage key{' '}
              <code>aep_user_role=admin</code> during development.
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#0b0f18] text-slate-100">
      <div className="px-8 py-10 max-w-[1400px] mx-auto">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.4em] text-cyan-400/70">
              Admin Control Plane
            </p>
            <div className="flex flex-wrap items-center gap-3 mt-3">
              <h1 className="text-3xl font-semibold">Security Audit Console</h1>
              <Badge className="bg-rose-500/15 text-rose-200 border-rose-400/40 text-xs tracking-[0.3em] uppercase px-3 py-1">
                Admin-only
              </Badge>
            </div>
            <p className="text-sm text-slate-400 mt-2 max-w-2xl">
              Encrypted audit trail of system actions. Decrypt only when necessary for compliance review.
            </p>
          </div>
          <div className="flex gap-3">
            <Button variant="outline" onClick={() => loadAuditEntries()}>
              Refresh feed
            </Button>
            <Button
              className="bg-cyan-500 hover:bg-cyan-400 text-slate-950"
              onClick={() => loadAuditEntries()}
            >
              Live sync
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-6 mt-8">
          <Card className="bg-slate-900/60 border-slate-800">
            <CardHeader>
              <CardTitle className="text-sm text-slate-400">Events visible</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-semibold">{stats.total}</div>
              <p className="text-xs text-slate-500 mt-2">Filtered view</p>
            </CardContent>
          </Card>
          <Card className="bg-slate-900/60 border-slate-800">
            <CardHeader>
              <CardTitle className="text-sm text-slate-400">Errors flagged</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-semibold">{stats.errors}</div>
              <p className="text-xs text-slate-500 mt-2">HTTP 4xx / 5xx</p>
            </CardContent>
          </Card>
          <Card className="bg-slate-900/60 border-slate-800">
            <CardHeader>
              <CardTitle className="text-sm text-slate-400">Unique actors</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-semibold">{stats.uniqueActors}</div>
              <p className="text-xs text-slate-500 mt-2">By actor_sub</p>
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-[2.2fr_1fr] gap-6 mt-8">
          <Card className="bg-slate-900/50 border-slate-800">
            <CardHeader>
              <CardTitle className="text-lg">Audit feed</CardTitle>
              <div className="grid grid-cols-4 gap-3 mt-4">
                <Input
                  className="bg-slate-950 border-slate-800"
                  placeholder="Org key"
                  value={orgFilter}
                  onChange={(e) => setOrgFilter(e.target.value)}
                />
                <Input
                  className="bg-slate-950 border-slate-800"
                  placeholder="Actor"
                  value={actorFilter}
                  onChange={(e) => setActorFilter(e.target.value)}
                />
                <Input
                  className="bg-slate-950 border-slate-800"
                  placeholder="Route contains"
                  value={routeFilter}
                  onChange={(e) => setRouteFilter(e.target.value)}
                />
                <Input
                  className="bg-slate-950 border-slate-800"
                  placeholder="Method (POST/PUT)"
                  value={methodFilter}
                  onChange={(e) => setMethodFilter(e.target.value.toUpperCase())}
                />
              </div>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[520px] pr-4">
                {loading ? (
                  <div className="text-sm text-slate-400">Loading audit feed...</div>
                ) : filteredEntries.length === 0 ? (
                  <div className="text-sm text-slate-400">No audit events found.</div>
                ) : (
                  <div className="space-y-2">
                    {filteredEntries.map((entry) => (
                      <button
                        key={entry.id}
                        onClick={() => handleSelect(entry)}
                        className={`w-full text-left rounded-xl border px-4 py-3 transition ${
                          selected?.id === entry.id
                            ? 'border-cyan-500/50 bg-cyan-500/10'
                            : 'border-slate-800 bg-slate-950/40 hover:border-slate-700'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Badge className={METHOD_COLORS[entry.method] || METHOD_COLORS.POST}>
                              {entry.method}
                            </Badge>
                            <span className="text-sm font-medium">{entry.route}</span>
                          </div>
                          <Badge className={statusTone(entry.status_code)}>{entry.status_code}</Badge>
                        </div>
                        <div className="flex flex-wrap items-center gap-3 mt-2 text-xs text-slate-400">
                          <span>Actor: {entry.actor_email || entry.actor_sub || 'unknown'}</span>
                          <span>Org: {entry.org_key || 'n/a'}</span>
                          <span>Event: {entry.event_type}</span>
                          <span>{formatTimestamp(entry.created_at)}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>

          <Card className="bg-slate-900/60 border-slate-800">
            <CardHeader>
              <CardTitle className="text-lg">Event detail</CardTitle>
            </CardHeader>
            <CardContent>
              {!selected ? (
                <div className="text-sm text-slate-400">Select an audit event to inspect.</div>
              ) : (
                <div className="space-y-5">
                  <div className="space-y-1 text-sm">
                    <div className="text-xs uppercase tracking-[0.3em] text-slate-500">
                      Meta
                    </div>
                    <div>Route: {selected.route}</div>
                    <div>Method: {selected.method}</div>
                    <div>Org: {selected.org_key || 'n/a'}</div>
                    <div>Actor: {selected.actor_email || selected.actor_sub || 'unknown'}</div>
                    <div>Resource: {selected.resource_id || 'n/a'}</div>
                    <div>Event: {selected.event_type}</div>
                    <div>Timestamp: {formatTimestamp(selected.created_at)}</div>
                  </div>
                  <Separator className="bg-slate-800" />
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="text-xs uppercase tracking-[0.3em] text-slate-500">
                        Payload
                      </div>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={payloadLoading}
                          onClick={() => selected && loadPayload(selected, false)}
                        >
                          Reload
                        </Button>
                        <Button
                          size="sm"
                          className="bg-emerald-500 hover:bg-emerald-400 text-slate-950"
                          disabled={payloadLoading}
                          onClick={() => selected && loadPayload(selected, true)}
                        >
                          Decrypt
                        </Button>
                      </div>
                    </div>
                    {payloadLoading ? (
                      <div className="text-sm text-slate-400">Loading payload...</div>
                    ) : payload ? (
                      <div className="space-y-3">
                        <div className="flex items-center gap-2 text-xs text-slate-400">
                          <Badge
                            className={
                              payload.encrypted
                                ? 'bg-amber-500/10 text-amber-200 border-amber-400/30'
                                : 'bg-emerald-500/10 text-emerald-200 border-emerald-400/30'
                            }
                          >
                            {payload.encrypted ? 'Encrypted' : 'Plain'}
                          </Badge>
                          <span>Payload ID: {payload.id}</span>
                        </div>
                        <pre className="text-xs bg-black/40 border border-slate-800 rounded-xl p-4 overflow-auto max-h-[260px] whitespace-pre-wrap">
                          {formatJSON(payload.payload)}
                        </pre>
                      </div>
                    ) : (
                      <div className="text-sm text-slate-400">Payload unavailable.</div>
                    )}
                  </div>
                  <Separator className="bg-slate-800" />
                  <div className="text-xs text-slate-500">
                    Audit payloads are encrypted at rest. Decrypt only when required for compliance review.
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
