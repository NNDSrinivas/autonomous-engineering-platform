export type JiraIssue = { id: string; key: string; summary: string; status: string; url?: string };
export type ProposedStep = { id: string; kind: 'edit'|'run'|'open'; title: string; details?: string; patch?: string };
export type DeviceCodeStart = { device_code: string; user_code: string; verification_uri: string; verification_uri_complete?: string; interval: number };
export type DeviceCodeToken = { access_token: string; expires_in: number };