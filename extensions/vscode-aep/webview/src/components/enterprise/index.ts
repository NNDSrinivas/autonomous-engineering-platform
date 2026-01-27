/**
 * Enterprise Components for VS Code Extension
 *
 * These components provide enterprise project management capabilities
 * within the VS Code webview.
 */

export {
  EnterpriseProjectStatus,
  type EnterpriseProjectData,
  type ProjectMilestone,
  type PendingGate,
} from './EnterpriseProjectStatus';

export {
  HumanGateApproval,
  GateNotification,
  PendingGatesList,
  type HumanGateData,
  type GateOption,
  type GateDecision,
  type GateType,
  type HumanGateApprovalProps,
  type GateNotificationProps,
  type PendingGatesListProps,
} from './HumanGateApproval';
