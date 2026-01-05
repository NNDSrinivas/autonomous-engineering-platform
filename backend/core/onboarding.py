"""
Enterprise Onboarding Flow for NAVI

Provides guided onboarding experience for organizations:
- Step-by-step org setup and configuration
- Integration connection flows (OAuth, API keys)
- Team and user invitation management
- Policy configuration and compliance setup
- Repository selection and enablement
- Success metrics and completion tracking
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid
import logging

from .tenancy import require_tenant, TenantRole, require_role
from .organization import OrganizationConfig, OrgTier, org_service
from .secrets import get_secrets_manager, IntegrationType, OAuthCredentials

logger = logging.getLogger(__name__)


class OnboardingStepType(Enum):
    """Types of onboarding steps"""

    ORG_SETUP = "org_setup"
    INTEGRATION_SETUP = "integration_setup"
    POLICY_CONFIG = "policy_config"
    TEAM_SETUP = "team_setup"
    REPOSITORY_SELECTION = "repository_selection"
    COMPLETION = "completion"


class OnboardingStepStatus(Enum):
    """Status of onboarding steps"""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class OnboardingStep:
    """Individual onboarding step"""

    id: str
    type: OnboardingStepType
    title: str
    description: str
    status: OnboardingStepStatus = OnboardingStepStatus.NOT_STARTED
    required: bool = True
    estimated_minutes: int = 5
    completion_percentage: float = 0.0
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None
    data: Dict[str, Any] = field(default_factory=dict)

    def mark_completed(self, data: Optional[Dict[str, Any]] = None):
        """Mark step as completed"""
        self.status = OnboardingStepStatus.COMPLETED
        self.completion_percentage = 100.0
        self.completed_at = datetime.utcnow()
        if data:
            self.data.update(data)

    def mark_failed(self, error_message: str):
        """Mark step as failed"""
        self.status = OnboardingStepStatus.FAILED
        self.error_message = error_message


@dataclass
class OnboardingFlow:
    """Complete onboarding flow for an organization"""

    org_id: str
    flow_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    current_step_index: int = 0
    steps: List[OnboardingStep] = field(default_factory=list)

    @property
    def is_completed(self) -> bool:
        """Check if onboarding is completed"""
        return all(
            step.status == OnboardingStepStatus.COMPLETED
            or (not step.required and step.status == OnboardingStepStatus.SKIPPED)
            for step in self.steps
        )

    @property
    def current_step(self) -> Optional[OnboardingStep]:
        """Get current active step"""
        if self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    @property
    def progress_percentage(self) -> float:
        """Calculate overall progress percentage"""
        if not self.steps:
            return 0.0

        completed_weight = sum(step.completion_percentage for step in self.steps)
        total_weight = len(self.steps) * 100

        return (completed_weight / total_weight) * 100 if total_weight > 0 else 0.0


class OnboardingFlowBuilder:
    """Builds onboarding flows based on organization needs"""

    def build_enterprise_flow(self, org_config: OrganizationConfig) -> OnboardingFlow:
        """Build complete enterprise onboarding flow"""
        flow = OnboardingFlow(
            org_id=org_config.id,
            flow_id=str(uuid.uuid4()),
            started_at=datetime.utcnow(),
        )

        # Step 1: Organization Setup
        flow.steps.append(
            OnboardingStep(
                id="org_setup",
                type=OnboardingStepType.ORG_SETUP,
                title="Organization Setup",
                description="Configure your organization settings, compliance requirements, and basic preferences",
                required=True,
                estimated_minutes=10,
            )
        )

        # Step 2: Core Integrations
        flow.steps.append(
            OnboardingStep(
                id="core_integrations",
                type=OnboardingStepType.INTEGRATION_SETUP,
                title="Connect Core Tools",
                description="Connect GitHub/GitLab, Jira, and Slack for NAVI to work with your existing workflow",
                required=True,
                estimated_minutes=15,
                data={
                    "required_integrations": [
                        IntegrationType.GITHUB.value,
                        IntegrationType.JIRA.value,
                        IntegrationType.SLACK.value,
                    ]
                },
            )
        )

        # Step 3: CI/CD Integration (optional for enterprise)
        flow.steps.append(
            OnboardingStep(
                id="cicd_integrations",
                type=OnboardingStepType.INTEGRATION_SETUP,
                title="Connect CI/CD Pipeline",
                description="Connect your CI/CD tools so NAVI can automatically fix build failures",
                required=False,
                estimated_minutes=10,
                data={
                    "optional_integrations": [
                        IntegrationType.JENKINS.value,
                        IntegrationType.CIRCLECI.value,
                    ]
                },
            )
        )

        # Step 4: Autonomy Policies
        flow.steps.append(
            OnboardingStep(
                id="autonomy_policies",
                type=OnboardingStepType.POLICY_CONFIG,
                title="Configure Autonomy Policies",
                description="Set up governance rules and approval workflows for different types of changes",
                required=True,
                estimated_minutes=20,
                data={
                    "default_autonomy_level": 0.3,  # Conservative for enterprise
                    "require_approval_for": [
                        "production_changes",
                        "security_updates",
                        "breaking_changes",
                    ],
                },
            )
        )

        # Step 5: Team Setup
        flow.steps.append(
            OnboardingStep(
                id="team_setup",
                type=OnboardingStepType.TEAM_SETUP,
                title="Invite Team Members",
                description="Add team members and assign roles for collaborative development",
                required=False,
                estimated_minutes=15,
            )
        )

        # Step 6: Repository Selection
        flow.steps.append(
            OnboardingStep(
                id="repository_selection",
                type=OnboardingStepType.REPOSITORY_SELECTION,
                title="Select Repositories",
                description="Choose which repositories NAVI should monitor and assist with",
                required=True,
                estimated_minutes=10,
            )
        )

        # Step 7: Completion & First Run
        flow.steps.append(
            OnboardingStep(
                id="completion",
                type=OnboardingStepType.COMPLETION,
                title="Complete Setup",
                description="Review configuration and run your first NAVI initiative",
                required=True,
                estimated_minutes=5,
            )
        )

        return flow

    def build_startup_flow(self, org_config: OrganizationConfig) -> OnboardingFlow:
        """Build simplified flow for startup/small teams"""
        flow = OnboardingFlow(
            org_id=org_config.id,
            flow_id=str(uuid.uuid4()),
            started_at=datetime.utcnow(),
        )

        # Simplified flow with fewer steps
        flow.steps.extend(
            [
                OnboardingStep(
                    id="org_setup",
                    type=OnboardingStepType.ORG_SETUP,
                    title="Quick Setup",
                    description="Set up your organization with smart defaults",
                    estimated_minutes=5,
                ),
                OnboardingStep(
                    id="github_integration",
                    type=OnboardingStepType.INTEGRATION_SETUP,
                    title="Connect GitHub",
                    description="Connect your GitHub repositories",
                    estimated_minutes=5,
                    data={"required_integrations": [IntegrationType.GITHUB.value]},
                ),
                OnboardingStep(
                    id="repository_selection",
                    type=OnboardingStepType.REPOSITORY_SELECTION,
                    title="Choose Repositories",
                    description="Select repositories for NAVI to help with",
                    estimated_minutes=5,
                ),
                OnboardingStep(
                    id="completion",
                    type=OnboardingStepType.COMPLETION,
                    title="Start Using NAVI",
                    description="You're ready! Try asking NAVI to help with a task",
                    estimated_minutes=2,
                ),
            ]
        )

        return flow


class IntegrationConnector:
    """Handles integration connections during onboarding"""

    def __init__(self):
        self.secrets_manager = get_secrets_manager()
        self.oauth_configs = {
            IntegrationType.GITHUB: {
                "name": "GitHub",
                "description": "Connect your GitHub repositories for code analysis and PR automation",
                "scopes": ["repo", "read:user", "read:org", "workflow"],
                "required_for": "Repository access and automated pull requests",
            },
            IntegrationType.JIRA: {
                "name": "Jira",
                "description": "Connect Jira for automated issue tracking and project management",
                "scopes": ["read:jira-work", "write:jira-work"],
                "required_for": "Issue creation and project tracking",
            },
            IntegrationType.SLACK: {
                "name": "Slack",
                "description": "Connect Slack for notifications and interactive communication",
                "scopes": ["chat:write", "channels:read", "users:read"],
                "required_for": "Real-time notifications and team communication",
            },
        }

    async def get_integration_info(
        self, integration: IntegrationType
    ) -> Dict[str, Any]:
        """Get integration connection information"""
        config = self.oauth_configs.get(integration, {})

        # Check if already connected
        existing_creds = await self.secrets_manager.get_oauth_credentials(integration)
        is_connected = existing_creds is not None

        return {
            "type": integration.value,
            "name": config.get("name", integration.value.title()),
            "description": config.get("description", ""),
            "scopes": config.get("scopes", []),
            "required_for": config.get("required_for", ""),
            "is_connected": is_connected,
            "connection_status": "connected" if is_connected else "not_connected",
        }

    async def initiate_oauth_flow(self, integration: IntegrationType) -> Dict[str, str]:
        """Initiate OAuth connection flow"""
        state = str(uuid.uuid4())
        redirect_uri = (
            f"https://your-domain.com/api/onboarding/oauth/callback/{integration.value}"
        )

        auth_url = self.secrets_manager.get_oauth_authorization_url(
            integration, redirect_uri, state
        )

        return {"auth_url": auth_url, "state": state, "integration": integration.value}

    async def complete_oauth_flow(
        self, integration: IntegrationType, auth_code: str, state: str
    ) -> bool:
        """Complete OAuth flow and store credentials"""
        try:
            # Exchange code for tokens (would make actual API call)
            # This is a placeholder implementation
            credentials = OAuthCredentials(
                access_token="fake_access_token",
                refresh_token="fake_refresh_token",
                expires_in=3600,
            )

            # Store credentials
            success = await self.secrets_manager.store_oauth_credentials(
                integration, credentials
            )

            if success:
                logger.info(f"Successfully connected {integration.value}")

            return success

        except Exception as e:
            logger.error(f"Failed to complete OAuth for {integration.value}: {e}")
            return False


class OnboardingService:
    """Main service for managing organization onboarding"""

    def __init__(self):
        self.flow_builder = OnboardingFlowBuilder()
        self.integration_connector = IntegrationConnector()
        self.active_flows: Dict[str, OnboardingFlow] = {}

    @require_role(TenantRole.ORG_ADMIN)
    async def start_onboarding(self, org_tier: OrgTier) -> OnboardingFlow:
        """Start onboarding flow for organization"""
        tenant = require_tenant()

        # Get organization config
        org = await org_service.get_organization_info()
        if not org:
            raise ValueError("Organization not found")

        org_config = OrganizationConfig.from_dict(org["organization"])

        # Build appropriate flow based on tier
        if org_tier in [OrgTier.ENTERPRISE, OrgTier.PROFESSIONAL]:
            flow = self.flow_builder.build_enterprise_flow(org_config)
        else:
            flow = self.flow_builder.build_startup_flow(org_config)

        # Store active flow
        self.active_flows[tenant.org_id] = flow

        logger.info(f"Started onboarding flow {flow.flow_id} for org {tenant.org_id}")
        return flow

    async def get_onboarding_status(self) -> Optional[OnboardingFlow]:
        """Get current onboarding status"""
        tenant = require_tenant()
        return self.active_flows.get(tenant.org_id)

    async def complete_step(
        self, step_id: str, step_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Complete an onboarding step"""
        tenant = require_tenant()
        flow = self.active_flows.get(tenant.org_id)

        if not flow:
            raise ValueError("No active onboarding flow")

        # Find step
        step = next((s for s in flow.steps if s.id == step_id), None)
        if not step:
            raise ValueError(f"Step {step_id} not found")

        # Process step based on type
        try:
            step_payload = step_data or {}
            if step.type == OnboardingStepType.ORG_SETUP:
                await self._complete_org_setup(step, step_payload)
            elif step.type == OnboardingStepType.INTEGRATION_SETUP:
                await self._complete_integration_setup(step, step_payload)
            elif step.type == OnboardingStepType.POLICY_CONFIG:
                await self._complete_policy_config(step, step_payload)
            elif step.type == OnboardingStepType.TEAM_SETUP:
                await self._complete_team_setup(step, step_payload)
            elif step.type == OnboardingStepType.REPOSITORY_SELECTION:
                await self._complete_repository_selection(step, step_payload)
            elif step.type == OnboardingStepType.COMPLETION:
                await self._complete_final_setup(step, step_payload)

            step.mark_completed(step_data)

            # Move to next step
            if flow.current_step and flow.current_step.id == step_id:
                flow.current_step_index += 1

            # Check if flow is completed
            if flow.is_completed:
                flow.completed_at = datetime.utcnow()
                logger.info(f"Onboarding completed for org {tenant.org_id}")

            return True

        except Exception as e:
            step.mark_failed(str(e))
            logger.error(f"Failed to complete step {step_id}: {e}")
            return False

    async def _complete_org_setup(self, step: OnboardingStep, data: Dict[str, Any]):
        """Complete organization setup step"""
        # Update org configuration
        updates = {}
        if "default_autonomy_level" in data:
            updates["default_autonomy_level"] = data["default_autonomy_level"]
        if "compliance_mode" in data:
            updates["compliance_mode"] = data["compliance_mode"]
        if "data_region" in data:
            updates["data_region"] = data["data_region"]

        if updates:
            await org_service.org_repo.update_organization(updates)

    async def _complete_integration_setup(
        self, step: OnboardingStep, data: Dict[str, Any]
    ):
        """Complete integration setup step"""
        # Would handle OAuth flows and API key setup
        # This is a placeholder
        pass

    async def _complete_policy_config(self, step: OnboardingStep, data: Dict[str, Any]):
        """Complete policy configuration step"""
        # Would set up governance policies
        # This is a placeholder
        pass

    async def _complete_team_setup(self, step: OnboardingStep, data: Dict[str, Any]):
        """Complete team setup step"""
        # Would handle user invitations
        # This is a placeholder
        pass

    async def _complete_repository_selection(
        self, step: OnboardingStep, data: Dict[str, Any]
    ):
        """Complete repository selection step"""
        # Would enable repositories for NAVI monitoring
        # This is a placeholder
        pass

    async def _complete_final_setup(self, step: OnboardingStep, data: Dict[str, Any]):
        """Complete final setup step"""
        # Would run initial system checks and setup
        # This is a placeholder
        pass

    async def get_integration_options(self) -> List[Dict[str, Any]]:
        """Get available integrations for setup"""
        integrations = []

        for integration_type in IntegrationType:
            info = await self.integration_connector.get_integration_info(
                integration_type
            )
            integrations.append(info)

        return integrations

    async def connect_integration(self, integration_type: str) -> Dict[str, str]:
        """Initiate integration connection"""
        integration = IntegrationType(integration_type)
        return await self.integration_connector.initiate_oauth_flow(integration)


# Global service instance
onboarding_service = OnboardingService()

__all__ = [
    "OnboardingStep",
    "OnboardingFlow",
    "OnboardingStepType",
    "OnboardingStepStatus",
    "OnboardingFlowBuilder",
    "IntegrationConnector",
    "OnboardingService",
    "onboarding_service",
]
