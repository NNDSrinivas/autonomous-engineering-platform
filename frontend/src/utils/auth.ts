function decodeJwtPayload(token: string): Record<string, unknown> | null {
  const parts = token.split('.')
  if (parts.length < 2) return null
  try {
    const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const padded = payload.padEnd(payload.length + ((4 - (payload.length % 4)) % 4), '=')
    const decoded = atob(padded)
    return JSON.parse(decoded)
  } catch {
    return null
  }
}

export function getAuthToken(): string | null {
  return localStorage.getItem('access_token')
}

export function getUserRole(): string {
  const token = getAuthToken()
  if (token) {
    const payload = decodeJwtPayload(token)
    const role = typeof payload?.role === 'string' ? payload?.role : undefined
    if (role && role.trim()) {
      return role.trim()
    }
  }

  const envRole = import.meta.env.VITE_USER_ROLE
  if (envRole && envRole.trim()) {
    return envRole.trim()
  }

  return 'viewer'
}

export function isAdminUser(): boolean {
  return getUserRole().toLowerCase() === 'admin'
}
