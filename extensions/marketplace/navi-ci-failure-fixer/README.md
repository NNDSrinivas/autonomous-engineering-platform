# NAVI CI Failure Fixer Extension

**Reference Implementation for NAVI Marketplace Extensions**

This extension demonstrates the complete NAVI extension architecture, serving as the foundation for all future marketplace extensions.

## 🎯 Purpose

Analyzes CI/CD pipeline failures and proposes safe, approval-gated fixes with automatic rollback capabilities.

## 🔐 Security Model

- **Trust Level**: CORE (highest trust)
- **Cryptographic Signing**: Ed25519 with NAVI root key
- **Permission Enforcement**: Runtime verification of CI_READ, REPO_READ, PROPOSE_CODE_CHANGES, REQUEST_APPROVAL
- **Approval Workflow**: All changes require user approval before execution

## 🧩 Architecture

```
index.ts                 # Main extension entry point
├── ci/
│   ├── fetchRuns.ts     # Fetch CI failure data  
│   ├── analyzeLogs.ts   # Log analysis using NAVI intelligence
│   └── classifyFailure.ts # Deterministic failure classification
├── fixes/
│   ├── dependencyFix.ts # Handle package dependency issues
│   ├── lintFix.ts       # Auto-fix code style issues
│   ├── testFix.ts       # Limited test failure fixes
│   └── typesFix.ts      # TypeScript type error fixes
└── types.ts             # TypeScript definitions
```

## 🚀 Supported Fix Types

| Failure Type | Auto-Fix | Risk Level | Approval Required |
|--------------|----------|------------|-------------------|
| Dependencies | ✅ Yes   | Medium     | ✅ Always        |
| Lint Issues  | ✅ Yes   | Low        | ✅ Always        |
| Type Errors  | ⚠️ Limited | Medium   | ✅ Always        |
| Test Failures| ⚠️ Limited | High     | ✅ Always        |
| Build Errors | ❌ No    | High       | N/A              |
| Unknown      | ❌ No    | High       | N/A              |

## 📋 Extension Interface

```typescript
export async function onInvoke(ctx: ExtensionContext): Promise<ExtensionResult>
```

### Input Context
- Project information (name, path, repo URL)
- User permissions and identity  
- CI provider configuration
- NAVI API access

### Output Result
- Success/failure status
- Human-readable message
- Approval requirement flag
- Detailed change proposals
- Rollback enablement

## 🔄 Execution Flow

1. **Permission Check**: NAVI runtime verifies extension permissions
2. **Fetch Failures**: Query CI provider for latest failing runs
3. **Analyze Logs**: Apply NAVI intelligence to classify failures
4. **Propose Fixes**: Generate approval-gated change proposals
5. **User Approval**: Present changes in NAVI UI for user decision
6. **Apply Changes**: Execute approved changes with rollback tracking

## 🛡️ Safety Features

- **No Direct Writes**: All changes go through approval workflow
- **Confidence Scoring**: Each proposal includes confidence percentage
- **Risk Assessment**: Changes classified by risk level
- **Rollback Hooks**: Automatic rollback capability for all changes
- **Audit Logging**: Complete trail of extension actions

## 🧪 Testing Strategy

- Unit tests for all fix proposal logic
- Integration tests with mock CI providers
- End-to-end tests with real CI failures
- Permission enforcement verification
- Signature tampering detection
- Rollback functionality validation

## 📦 Bundle Format

The extension is packaged as `navi-ci-failure-fixer.navi-ext`:

```
manifest.json     # Extension metadata and permissions
signature.sig     # Ed25519 cryptographic signature  
index.ts         # Compiled main entry point
ci/              # CI integration modules
fixes/           # Fix proposal generators
types.ts         # TypeScript definitions
README.md        # This documentation
```

## 🔐 Security Verification

Before installation, NAVI verifies:
- ✅ Ed25519 signature matches NAVI root key
- ✅ Bundle hash integrity 
- ✅ Manifest permissions are acceptable
- ✅ Trust level is authorized
- ✅ No code tampering detected

## 🎭 Runtime Enforcement

During execution, NAVI enforces:
- ✅ Permission boundaries (cannot exceed declared permissions)
- ✅ Approval requirements (no auto-apply without user consent)
- ✅ Rollback hooks (all changes tracked for reversal)
- ✅ Audit logging (complete activity trail)

## 📈 Extension Metrics

- Execution count and success rate
- User approval/rejection ratios  
- Rollback frequency and reasons
- Performance impact measurement
- Security violation attempts

## 🏗️ Development Notes

This extension serves as the reference implementation for:
- Extension SDK usage patterns
- Security best practices
- Approval workflow integration
- Error handling and logging
- TypeScript structure conventions

All future marketplace extensions should follow this architecture and security model.

---

**Status**: ✅ Production Ready  
**Trust Level**: CORE  
**Signature**: Verified with NAVI Root Key  
**Version**: 1.0.0