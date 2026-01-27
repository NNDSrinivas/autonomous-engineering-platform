/**
 * Enterprise Components for Web Application
 *
 * These components provide enterprise project management capabilities
 * for team leads and managers to oversee long-running projects.
 */

export {
  EnterpriseProjectDashboard,
  type EnterpriseProject,
  type ProjectTask,
  type ProjectMilestone,
  type PendingGate,
  type ProjectStatus,
  type EnterpriseProjectDashboardProps,
} from './EnterpriseProjectDashboard';

export {
  GateApprovalQueue,
  type HumanGate,
  type GateOption,
  type GateDecision,
  type GateType,
  type GatePriority,
  type GateApprovalQueueProps,
} from './GateApprovalQueue';

export { CreateProjectDialog } from './CreateProjectDialog';
