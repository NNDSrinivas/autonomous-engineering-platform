# NAVI Kubernetes Diagnostics Extension

**🚀 Staff+ SRE Intelligence for Live Infrastructure**

A production-grade NAVI extension that brings sophisticated Kubernetes diagnostics and remediation capabilities to your autonomous engineering platform. This extension demonstrates NAVI's evolution beyond code analysis into live infrastructure reasoning and operational excellence.

## 🎯 Overview

The Kubernetes Diagnostics Extension elevates NAVI from a coding assistant to a **Staff+ SRE intelligence system**, capable of:

- **Live Infrastructure Analysis**: Real-time inspection of Kubernetes clusters, pods, deployments, services, and events
- **Intelligent Issue Classification**: Deterministic analysis of 8 critical failure patterns with confidence scoring
- **Human + SRE Explanations**: Dual-level explanations for both technical teams and stakeholders
- **Approval-Gated Remediation**: Safe, rollback-enabled fix proposals with mandatory human oversight
- **Security-First Architecture**: All operations validated, destructive actions require explicit approval

This extension serves as the **second pillar** of NAVI's marketplace, proving that extensions can reason about complex, stateful systems beyond static code.

## 🏗️ Architecture

### Core Components

```
navi-k8s-diagnostics/
├── index.ts                 # Main entry point and orchestration
├── types.ts                 # Comprehensive TypeScript definitions
├── manifest.json            # Extension metadata and permissions
├── k8s/                     # Kubernetes inspection layer
│   ├── clusterInfo.ts       # Cluster connectivity and overview
│   ├── podInspector.ts      # Pod health and lifecycle analysis
│   ├── deploymentInspector.ts # Deployment scaling and rollout analysis
│   ├── serviceInspector.ts  # Service connectivity and endpoint analysis
│   ├── events.ts           # Event stream analysis and filtering
│   └── logs.ts             # Log parsing and pattern detection
├── diagnosis/               # Issue classification and remediation engine
│   ├── classifyIssue.ts    # Deterministic issue classification
│   ├── explain.ts          # Human-readable explanations
│   └── remediation.ts      # Safe remediation proposals
└── tests/                  # Comprehensive test suite
    └── index.test.ts       # Unit and integration tests
```

### Issue Classification Types

The extension identifies and classifies **8 critical Kubernetes failure patterns**:

1. **CRASH_LOOP** - CrashLoopBackOff containers requiring immediate attention
2. **DEPLOYMENT_DOWN** - Failed deployments with zero ready replicas
3. **IMAGE_PULL_ERROR** - Registry connectivity and authentication issues
4. **SERVICE_UNREACHABLE** - Service endpoint and connectivity problems
5. **RESOURCE_QUOTA_EXCEEDED** - Resource constraints affecting pod scheduling
6. **CONFIG_ERROR** - ConfigMap/Secret mounting and validation issues
7. **NETWORK_POLICY_BLOCK** - Network policy conflicts preventing communication
8. **NODE_NOT_READY** - Node-level issues affecting workload placement

## 🔐 Security Model

### Trust Level: CORE
This extension operates with **CORE** trust level, requiring cryptographic signing and comprehensive security controls.

### Required Permissions
- **K8S_READ** - Read-only access to Kubernetes cluster resources
- **K8S_LOGS** - Access to pod logs for diagnostic analysis
- **REPO_READ** - Repository access for context-aware analysis
- **REQUEST_APPROVAL** - Ability to request human approval for actions
- **PROPOSE_ACTIONS** - Generate remediation proposals with rollback instructions

### Safety Guarantees
- **Read-Only Operations**: All inspection operations use safe `kubectl get/describe` commands
- **Approval Gates**: Destructive operations require explicit human approval
- **Command Validation**: All kubectl commands validated for safety before execution
- **Timeout Protection**: All operations have 30-second timeouts to prevent hanging
- **Rollback Instructions**: Every remediation proposal includes detailed rollback steps

## 🚀 Quick Start

### Prerequisites
- Kubernetes cluster access with `kubectl` configured
- NAVI autonomous engineering platform v2.0+
- Node.js 18+ for development

### Installation

1. **Clone and Build**
```bash
git clone <repository>
cd extensions/marketplace/navi-k8s-diagnostics
npm install
npm run build
```

2. **Run Tests**
```bash
npm run test
npm run test:coverage
```

3. **Create Signed Bundle**
```bash
npm run package
```

4. **Deploy to NAVI**
```bash
# Copy the .navi-ext bundle to your NAVI installation
cp bundle/navi-k8s-diagnostics-v1.0.0.navi-ext /path/to/navi/extensions/
```

### Usage

Once installed, NAVI automatically detects infrastructure-related intents and invokes the Kubernetes diagnostics extension:

```
User: "My deployment is failing in the production namespace"
NAVI: 🔍 Analyzing Kubernetes cluster health...
      📊 Found 2 critical issues requiring immediate attention
      🚨 CrashLoopBackOff detected in pod auth-service-abc123
      ⚠️ Deployment auth-service has 0/3 ready replicas
      
      🔧 Proposed remediation (requires approval):
      1. Restart failing pods with rollback capability
      2. Check deployment resource constraints
      3. Verify configuration and secrets
```

## 🔧 Development Guide

### Local Development

1. **Start in Watch Mode**
```bash
npm run build:watch  # TypeScript compilation
npm run test:watch   # Test suite
```

2. **Mock Kubernetes Environment**
The extension includes comprehensive mocking for development without requiring a live cluster:
```typescript
// Tests use mock data generators
const mockPod = createMockPod('test-pod', 'default', 'Running', true);
const mockDeployment = createMockDeployment('test-app', 'default', 3, 2);
```

3. **Security Testing**
```bash
npm run lint           # Code quality and security linting
npm run verify-bundle  # Bundle integrity verification
```

### Extension API

The main entry point implements the NAVI extension interface:

```typescript
export async function onInvoke(ctx: ExtensionContext): Promise<DiagnosticsResult> {
    // 1. Verify cluster access
    // 2. Gather comprehensive diagnostic data
    // 3. Classify issues using deterministic analysis  
    // 4. Generate explanations and remediation proposals
    // 5. Return structured diagnostics result
}
```

### Adding New Issue Types

1. **Define Issue Type** in `types.ts`:
```typescript
export enum IssueType {
    CUSTOM_ISSUE = 'CUSTOM_ISSUE'
}
```

2. **Implement Classification** in `diagnosis/classifyIssue.ts`:
```typescript
function detectCustomIssue(data: DiagnosticData): KubernetesIssue | null {
    // Classification logic with confidence scoring
}
```

3. **Add Explanation** in `diagnosis/explain.ts`:
```typescript
case IssueType.CUSTOM_ISSUE:
    return {
        humanExplanation: "...",
        sreExplanation: "...",
        impact: "...",
        urgency: "..."
    };
```

4. **Implement Remediation** in `diagnosis/remediation.ts`:
```typescript
case IssueType.CUSTOM_ISSUE:
    return await proposeCustomRemediation(ctx, issue);
```

## 🧪 Testing Strategy

### Test Coverage Requirements
- **Lines**: 80%+ coverage
- **Functions**: 80%+ coverage  
- **Branches**: 80%+ coverage
- **Statements**: 80%+ coverage

### Test Categories

1. **Unit Tests** - Individual function testing with mocks
2. **Integration Tests** - End-to-end workflow testing
3. **Security Tests** - Permission validation and safety verification
4. **Performance Tests** - Large cluster handling and response times
5. **Bundle Tests** - Cryptographic signing and integrity verification

### Running Tests
```bash
npm run test              # Full test suite
npm run test:watch        # Watch mode for development
npm run test:coverage     # Coverage report
```

## 📋 Deployment Checklist

### Pre-Production
- [ ] All tests passing with 80%+ coverage
- [ ] Security lint scan clean
- [ ] Performance validated on test clusters
- [ ] Bundle integrity verified
- [ ] Cryptographic signature validated

### Production Deployment
- [ ] Bundle deployed to NAVI marketplace
- [ ] Extension permissions verified
- [ ] Cluster connectivity tested
- [ ] Approval workflows functional
- [ ] Rollback procedures documented

### Post-Deployment Monitoring
- [ ] Extension performance metrics tracked
- [ ] User feedback collected and analyzed
- [ ] Error rates and diagnostics accuracy monitored
- [ ] Security audit trail maintained

## 🎯 Production Readiness

This extension demonstrates **production-grade quality** through:

### Code Quality
- **TypeScript**: Full type safety with strict compilation
- **Comprehensive Testing**: 80%+ test coverage with multiple test categories
- **Security Scanning**: ESLint security rules and bundle verification
- **Performance Optimization**: Efficient cluster data gathering and analysis

### Operational Excellence  
- **Monitoring & Observability**: Structured logging and error tracking
- **Security Controls**: Approval gates and command validation
- **Disaster Recovery**: Rollback instructions for all remediation proposals
- **Documentation**: Complete API documentation and runbooks

### Marketplace Standards
- **Cryptographic Signing**: Tamper-proof bundle verification
- **Permission Model**: Least-privilege security with explicit approvals
- **Version Management**: Semantic versioning with backward compatibility
- **User Experience**: Clear explanations and actionable recommendations

## 🤝 Contributing

### Development Workflow
1. Fork the repository and create a feature branch
2. Implement changes with comprehensive tests
3. Run full test suite and security validation
4. Create signed bundle and verify integrity
5. Submit pull request with detailed documentation

### Code Standards
- Follow TypeScript strict mode guidelines
- Maintain 80%+ test coverage for all changes
- Include security impact assessment
- Document all public APIs and interfaces
- Ensure backward compatibility

## 📚 References

- [NAVI Extension Development Guide](../../../docs/extensions.md)
- [Kubernetes API Reference](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.28/)
- [Extension Security Model](../../../docs/security.md)
- [Marketplace Submission Guidelines](../../../docs/marketplace.md)

## 🔮 Roadmap

### Phase 7.5 - Advanced Analytics (Q2 2024)
- Historical trend analysis and predictive failure detection
- Integration with Prometheus/Grafana for metric correlation
- Automated runbook generation from remediation patterns

### Phase 8.0 - Multi-Cluster Intelligence (Q3 2024)  
- Cross-cluster dependency analysis and impact assessment
- Federated diagnostics across development, staging, and production
- Advanced incident response orchestration

### Phase 8.5 - AI-Powered Optimization (Q4 2024)
- Machine learning-based resource optimization recommendations
- Intelligent workload placement and auto-scaling suggestions
- Predictive maintenance and proactive issue prevention

---

**Built with ❤️ by the NAVI Team**

*Elevating autonomous engineering from code to infrastructure, one diagnosis at a time.*