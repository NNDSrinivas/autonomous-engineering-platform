# Webhook Configuration Guide for AEP Platform

## Environment Secrets Setup ✅

The following secrets have been added to your `.env` file:

- **X_ORG_ID**: `org_aep_platform_4538597546e6fec6`
- **JIRA_WEBHOOK_SECRET**: `fmf7qD9fdBvXh-D-XzhdXdUnKOyCl-ttzcb1Pew6bLIfmv_zmmKg66mvcDX8pfES`
- **GITHUB_WEBHOOK_SECRET**: `ID8mdewv8S5jP3Lwj1ndvVGnHCxUL-R5pSKO6JcVXP9XHZbidDBqd2Hz9mEsGZTS`
- **SLACK_SIGNING_SECRET**: `hJNdGcTVUZe2LcFV6uwQ5MiAB-j2PzgG-WGCnWBGkfxPqeTwsyyUHsHkXivBsCm4`
- **TEAMS_WEBHOOK_SECRET**: `wcx8mlG3tzAMxZVgkVO_7fYKnBgKM2q5oolCpz1l29EZUV0AmRMxD80vyE2mYIzT`

## Webhook Endpoints Configuration

Assuming your AEP backend is running on `http://localhost:8787`, configure these webhook URLs in your services:

### 1. Jira Webhooks

**Setup Location**: Jira Admin → System → Webhooks

**Issue Events Webhook**:
- **URL**: `http://localhost:8787/api/webhooks/jira/issue`
- **Events**: Issue created, updated, deleted, transitioned
- **Secret**: `fmf7qD9fdBvXh-D-XzhdXdUnKOyCl-ttzcb1Pew6bLIfmv_zmmKg66mvcDX8pfES`

**General Events Webhook**:
- **URL**: `http://localhost:8787/api/webhooks/jira/event`
- **Events**: Project created, user created, etc.
- **Secret**: `fmf7qD9fdBvXh-D-XzhdXdUnKOyCl-ttzcb1Pew6bLIfmv_zmmKg66mvcDX8pfES`

### 2. GitHub Webhooks

**Setup Location**: GitHub Repository → Settings → Webhooks

- **URL**: `http://localhost:8787/api/webhooks/github`
- **Content Type**: application/json
- **Secret**: `ID8mdewv8S5jP3Lwj1ndvVGnHCxUL-R5pSKO6JcVXP9XHZbidDBqd2Hz9mEsGZTs`
- **Events**: 
  - Push events
  - Pull request events
  - Issue events
  - Release events
  - Status events
  - Review events

### 3. Slack Webhooks

**Setup Location**: Slack App Configuration → Event Subscriptions

- **Request URL**: `http://localhost:8787/api/webhooks/slack`
- **Signing Secret**: `hJNdGcTVUZe2LcFV6uwQ5MiAB-j2PzgG-WGCnWBGkfxPqeTwsyyUHsHkXivBsCm4`
- **Events**:
  - message.channels
  - message.groups
  - message.mpim
  - app_mention

### 4. Microsoft Teams Webhooks

**Setup Location**: Teams App Studio → Bot Framework

- **Messaging Endpoint**: `http://localhost:8787/api/webhooks/teams`
- **Webhook Secret**: `wcx8mlG3tzAMxZVgkVO_7fYKnBgKM2q5oolCpz1l29EZUV0AmRMxD80vyE2mYIzT`

## Production Deployment Notes

For production deployment, replace `http://localhost:8787` with your actual domain:

- `https://your-domain.com/api/webhooks/jira/issue`
- `https://your-domain.com/api/webhooks/jira/event`
- `https://your-domain.com/api/webhooks/github`
- `https://your-domain.com/api/webhooks/slack`
- `https://your-domain.com/api/webhooks/teams`

## Testing Webhooks

1. **Start your backend server**:
   ```bash
   source .venv/bin/activate
   python -m uvicorn main:app --host 0.0.0.0 --port 8787
   ```

2. **Use ngrok for local testing** (if services can't reach localhost):
   ```bash
   ngrok http 8787
   ```
   Then use the ngrok URL (e.g., `https://abc123.ngrok.io`) instead of `localhost:8787`

3. **Verify webhook delivery** in your service admin panels and check the AEP logs.

## Header Requirements

Each webhook endpoint expects these headers:

- **Jira**: `X-Atlassian-Webhook-Identifier` 
- **GitHub**: `X-GitHub-Event`, `X-Hub-Signature-256`
- **Slack**: `X-Slack-Signature`, `X-Slack-Request-Timestamp`
- **Teams**: `Authorization` header with webhook secret

## Next Steps

1. Configure the webhook URLs in your respective service admin panels
2. Start your AEP backend server
3. Test each webhook by performing actions in the services (create issue, push code, send message)
4. Monitor the backend logs to confirm webhooks are being received and processed