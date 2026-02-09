# Threat Model (Draft)

## Scope
- NAVI API
- Command execution
- Repo access and file modification
- External integrations (GitHub, Jira, etc.)

## Assets
- Source code
- Secrets (API keys, tokens)
- Audit logs
- User data

## Threats
- Unauthorized command execution
- Data exfiltration via tool output
- Privilege escalation through integrations
- Prompt injection in repo content

## Mitigations
- Approval gating for dangerous commands
- Allowlist for commands
- Output redaction rules
- Audit logging and access controls

## TODO
- Formal STRIDE analysis
- Threat scoring and remediation plan
