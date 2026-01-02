# Phase 2.1 – Risk-Gated Fix Flow Architecture

## Current State (Snapshot)

### 1. FixProposal Type (extensions/vscode-aep/src/navi-core/planning/FixProposalEngine.ts)

```typescript
export type ProposalConfidence = 'low' | 'medium' | 'high';
export type RiskLevel = 'low' | 'medium' | 'high';

export interface FixProposal {
    id: string;
    filePath: string;
    line: number;
    severity: 'error' | 'warning' | 'info';
    source?: string;
    impact: 'introduced' | 'preExisting';
    issue: string;
    rootCause: string;
    suggestedChange: string;
    confidence: ProposalConfidence;
    canAutoFixLater: boolean;
    // Phase 2.1: Risk-based fix flow (not binary auto/manual)
    riskLevel: RiskLevel;
    requiresChoice?: boolean; // If true, show alternatives for user selection
    alternatives?: FixProposal[]; // Alternative fix options for ambiguous cases
    // Phase 2.1: Safety and application metadata
    originalFileHash?: string;
    rangeStart?: { line: number; character: number };
    rangeEnd?: { line: number; character: number };
    replacementText?: string;
}
```

### 2. Apply Handler Path (extensions/vscode-aep/src/extension.ts:1113)

**Where proposals are captured:**
- Line 1652: `if (kind === 'navi.fix.proposals')`
- Line 1657: `this._fixProposals.set(proposal.id, proposal)`
- Proposals stored in: `private _fixProposals = new Map<string, any>()`

**Apply handler:**
- Line 1113: `case 'navi.fix.apply':`
- Current flow:
  1. Get proposalId from msg
  2. Fetch proposal from `_fixProposals` Map
  3. For high-risk: Show modal (Apply Anyway / Review in Editor / Cancel)
  4. Safety checks: file exists, hash matches
  5. Create WorkspaceEdit (placeholder, not executed yet)
  6. Return `navi.fix.result` event

### 3. Frontend Message Flow (frontend/src/components/navi/NaviChatPanel.tsx)

**Where fix is approved:**
- Line 2925: Approve button sends `vscodeApi.postMessage({ type: 'navi.fix.apply', proposalId })`

**Where result is handled:**
- Line 1378-1391: Listens for `navi.fix.result` event
- Statuses handled: 'deferred', 'cancelled', 'failed', 'pending', 'applied'

---

## What's Missing (Error Context)

The error you're seeing suggests that when sending the message, some properties are undefined or the message shape is wrong. The message payload needs to support:

1. **forceApply flag** - to bypass high-risk confirmation on retry
2. **alternatives selection** - which variant to apply when `requiresChoice=true`
3. **Validation metadata** - post-apply validation hints

---

## Proposed Changes (No Breaking Changes)

### Change 1: Extend navi.fix.apply message format

**Current:**
```typescript
{ type: 'navi.fix.apply', proposalId: string }
```

**Updated:**
```typescript
{
  type: 'navi.fix.apply',
  proposalId: string,
  forceApply?: boolean,           // If true, skip high-risk modal
  selectedAlternativeIndex?: number, // If requiresChoice=true, which option to apply
  skipValidation?: boolean        // If true, apply without post-validation
}
```

### Change 2: Update apply handler to use forceApply

**In extension.ts:1140 (already partially implemented):**
```typescript
if (proposal.riskLevel === 'high' && !msg.forceApply) {
  // Show modal...
}
```

This is already correct! The issue is likely that:
- `msg.forceApply` isn't being passed from frontend
- Or the modal choice needs to send a follow-up message with `forceApply: true`

### Change 3: Handle alternatives (Future - not urgent)

When `proposal.requiresChoice === true`:

```typescript
// If proposal has alternatives, apply the selected one
const proposalToApply = proposal.alternatives?.[msg.selectedAlternativeIndex] || proposal;
```

### Change 4: Add validation framework (Future - optional)

After applying a fix, optionally validate:

```typescript
if (!msg.skipValidation && proposal.riskLevel === 'medium') {
  // Run quick validation (e.g., TypeScript parse check)
  const isValid = await validateFix(proposal.filePath);
  if (!isValid) {
    await vscode.commands.executeCommand('undo');
    return { status: 'failed', reason: 'Fix introduced new errors' };
  }
}
```

---

## Integration Points

### Where to wire forceApply on "Apply Anyway" click

When user clicks "Apply Anyway" in the modal, extension needs to:

```typescript
// Instead of continuing execution, send back to webview:
vscodeApi.postMessage({
  type: 'navi.fix.apply.confirmed',
  proposalId,
  forceApply: true
});

// Then extension listener re-triggers apply with forceApply flag
```

**OR** (simpler): Keep the modal in extension, and when "Apply Anyway" is clicked, set `msg.forceApply = true` and continue to apply logic directly.

---

## Next Steps

1. **Immediate**: Verify that "Apply Anyway" click in modal correctly routes to apply logic
2. **Short term**: Add selectedAlternativeIndex support for alternatives
3. **Medium term**: Implement post-apply validation
4. **Long term**: UI for selecting alternatives (A/B/C tabs)

---

## Error Diagnosis

The error "Cannot read properties of undefined (reading '0')" likely means:

- Accessing `proposal.alternatives[0]` when alternatives is undefined
- OR accessing `event.data?.files[0]` when files array is empty/undefined
- OR trying to access a proposal property that's undefined

**Check the exact error line** in the console to confirm which property access failed.
