"""
Infrastructure Executor Service for NAVI
Handles real infrastructure operations: Terraform, Kubernetes, CloudFormation, Helm.
"""

import asyncio
import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class InfrastructureProvider(Enum):
    """Supported infrastructure providers - 100+ tools."""

    # =========================================================================
    # INFRASTRUCTURE AS CODE - DECLARATIVE
    # =========================================================================
    TERRAFORM = "terraform"
    OPENTOFU = "opentofu"
    TERRAGRUNT = "terragrunt"
    PULUMI = "pulumi"
    CROSSPLANE = "crossplane"
    CDKTF = "cdktf"  # CDK for Terraform
    WINGLANG = "winglang"
    SST = "sst"  # Serverless Stack
    NITRIC = "nitric"
    KLOTHO = "klotho"
    ENCORE = "encore"
    AMPT = "ampt"
    DARKLANG = "darklang"

    # =========================================================================
    # AWS INFRASTRUCTURE
    # =========================================================================
    AWS_CDK = "aws_cdk"
    AWS_SAM = "aws_sam"
    CLOUDFORMATION = "cloudformation"
    AWS_COPILOT = "aws_copilot"
    AWS_PROTON = "aws_proton"
    TROPOSPHERE = "troposphere"
    SCEPTRE = "sceptre"
    STACKER = "stacker"
    SERVERLESS_FRAMEWORK = "serverless_framework"
    CHALICE = "chalice"
    ZAPPA = "zappa"
    ARCHITECT = "architect"
    CLAUDIA = "claudia"

    # =========================================================================
    # AZURE INFRASTRUCTURE
    # =========================================================================
    AZURE_BICEP = "azure_bicep"
    AZURE_ARM = "azure_arm"
    AZURE_CLI = "azure_cli"
    FARMER = "farmer"  # F# for Azure
    AZURE_DEVELOPER_CLI = "azure_developer_cli"

    # =========================================================================
    # GCP INFRASTRUCTURE
    # =========================================================================
    GCP_DEPLOYMENT_MANAGER = "gcp_deployment_manager"
    GCP_CONFIG_CONNECTOR = "gcp_config_connector"
    GOOGLE_CLOUD_CLI = "google_cloud_cli"
    GCLOUD = "gcloud"

    # =========================================================================
    # ORACLE/IBM/ALIBABA INFRASTRUCTURE
    # =========================================================================
    ORACLE_RESOURCE_MANAGER = "oracle_resource_manager"
    ORACLE_CLI = "oracle_cli"
    IBM_CLOUD_CLI = "ibm_cloud_cli"
    IBM_SCHEMATICS = "ibm_schematics"
    ALIBABA_ROS = "alibaba_ros"
    ALIBABA_CLI = "alibaba_cli"

    # =========================================================================
    # KUBERNETES ECOSYSTEM
    # =========================================================================
    KUBERNETES = "kubernetes"
    KUBECTL = "kubectl"
    HELM = "helm"
    KUSTOMIZE = "kustomize"
    SKAFFOLD = "skaffold"
    TILT = "tilt"
    GARDEN = "garden"
    DEVSPACE = "devspace"
    OKTETO = "okteto"
    TELEPRESENCE = "telepresence"
    MINIKUBE = "minikube"
    KIND = "kind"
    K3D = "k3d"
    K3S = "k3s"
    MICROK8S = "microk8s"
    RANCHER = "rancher"
    KOPS = "kops"
    KUBEADM = "kubeadm"
    KUBESPRAY = "kubespray"
    CLUSTER_API = "cluster_api"
    TALOS = "talos"
    FLATCAR = "flatcar"

    # =========================================================================
    # GITOPS TOOLS
    # =========================================================================
    ARGOCD = "argocd"
    FLUXCD = "fluxcd"
    JENKINS_X = "jenkins_x"
    WEAVE_GITOPS = "weave_gitops"
    CODEFRESH = "codefresh"
    SPINNAKER = "spinnaker"
    HARNESS = "harness"
    OCTOPUS_DEPLOY = "octopus_deploy"
    GOCD = "gocd"

    # =========================================================================
    # CI/CD TOOLS
    # =========================================================================
    GITHUB_ACTIONS = "github_actions"
    GITLAB_CI = "gitlab_ci"
    JENKINS = "jenkins"
    CIRCLECI = "circleci"
    TRAVIS_CI = "travis_ci"
    BUILDKITE = "buildkite"
    DRONE = "drone"
    TEKTON = "tekton"
    SEMAPHORE = "semaphore"
    AZURE_DEVOPS = "azure_devops"
    AWS_CODEPIPELINE = "aws_codepipeline"
    GCP_CLOUD_BUILD = "gcp_cloud_build"
    BUDDY = "buddy"
    WOODPECKER = "woodpecker"
    DAGGER = "dagger"
    EARTHLY = "earthly"
    TASKFILE = "taskfile"
    MAKE = "make"
    JUST = "just"
    MISE = "mise"

    # =========================================================================
    # CONFIGURATION MANAGEMENT
    # =========================================================================
    ANSIBLE = "ansible"
    CHEF = "chef"
    PUPPET = "puppet"
    SALTSTACK = "saltstack"
    CFENGINE = "cfengine"
    RUDDER = "rudder"
    MGMT = "mgmt"
    PYINFRA = "pyinfra"
    FABRIC = "fabric"
    CAPISTRANO = "capistrano"
    MITOGEN = "mitogen"

    # =========================================================================
    # CONTAINER TOOLS
    # =========================================================================
    DOCKER = "docker"
    DOCKER_COMPOSE = "docker_compose"
    DOCKER_SWARM = "docker_swarm"
    PODMAN = "podman"
    PODMAN_COMPOSE = "podman_compose"
    BUILDAH = "buildah"
    KANIKO = "kaniko"
    BUILDKIT = "buildkit"
    CONTAINERD = "containerd"
    CRI_O = "cri_o"
    LXC = "lxc"
    LXD = "lxd"
    SINGULARITY = "singularity"
    APPTAINER = "apptainer"
    NOMAD = "nomad"
    MESOS = "mesos"
    DOCKER_STACK = "docker_stack"

    # =========================================================================
    # SERVICE MESH
    # =========================================================================
    ISTIO = "istio"
    LINKERD = "linkerd"
    CONSUL = "consul"
    CILIUM = "cilium"
    ENVOY = "envoy"
    TRAEFIK_MESH = "traefik_mesh"
    KUMA = "kuma"
    OSMO = "osmo"
    AWS_APP_MESH = "aws_app_mesh"
    GCP_TRAFFIC_DIRECTOR = "gcp_traffic_director"

    # =========================================================================
    # NETWORKING
    # =========================================================================
    CALICO = "calico"
    FLANNEL = "flannel"
    WEAVE_NET = "weave_net"
    ANTREA = "antrea"
    MULTUS = "multus"
    METALLB = "metallb"
    NGINX_INGRESS = "nginx_ingress"
    TRAEFIK = "traefik"
    KONG = "kong"
    AMBASSADOR = "ambassador"
    EMISSARY = "emissary"
    CONTOUR = "contour"
    HAPROXY = "haproxy"
    CADDY = "caddy"
    CLOUDFLARE_TUNNEL = "cloudflare_tunnel"

    # =========================================================================
    # SECRETS MANAGEMENT
    # =========================================================================
    VAULT = "vault"
    AWS_SECRETS_MANAGER = "aws_secrets_manager"
    AZURE_KEY_VAULT = "azure_key_vault"
    GCP_SECRET_MANAGER = "gcp_secret_manager"
    SEALED_SECRETS = "sealed_secrets"
    EXTERNAL_SECRETS = "external_secrets"
    SOPS = "sops"
    AGE = "age"
    DOPPLER = "doppler"
    INFISICAL = "infisical"
    ONEPASSWORD = "onepassword"
    CYBERARK = "cyberark"
    DELINEA = "delinea"
    AKEYLESS = "akeyless"
    BERGLAS = "berglas"
    CHAMBER = "chamber"
    TELLER = "teller"
    DOTENV_VAULT = "dotenv_vault"

    # =========================================================================
    # SECURITY / COMPLIANCE
    # =========================================================================
    TRIVY = "trivy"
    SNYK = "snyk"
    CHECKOV = "checkov"
    TFSEC = "tfsec"
    TERRASCAN = "terrascan"
    KICS = "kics"
    PROWLER = "prowler"
    SCOUT_SUITE = "scout_suite"
    CLOUDSPLOIT = "cloudsploit"
    FALCO = "falco"
    SYSDIG = "sysdig"
    AQUASEC = "aquasec"
    TWISTLOCK = "twistlock"
    STACKROX = "stackrox"
    NEUVECTOR = "neuvector"
    KUBESCAPE = "kubescape"
    KUBE_BENCH = "kube_bench"
    KUBE_HUNTER = "kube_hunter"
    POLARIS = "polaris"
    DATREE = "datree"
    CONFTEST = "conftest"
    OPA = "opa"  # Open Policy Agent
    KYVERNO = "kyverno"
    GATEKEEPER = "gatekeeper"

    # =========================================================================
    # STORAGE
    # =========================================================================
    ROOK = "rook"
    LONGHORN = "longhorn"
    OPENEBS = "openebs"
    PORTWORX = "portworx"
    STORAGEOS = "storageos"
    MINIO = "minio"
    CEPH = "ceph"
    GLUSTER = "gluster"
    NFS = "nfs"
    CSI_DRIVER = "csi_driver"
    VELERO = "velero"
    KASTEN = "kasten"
    STASH = "stash"

    # =========================================================================
    # MONITORING / OBSERVABILITY
    # =========================================================================
    PROMETHEUS = "prometheus"
    PROMETHEUS_OPERATOR = "prometheus_operator"
    GRAFANA = "grafana"
    GRAFANA_TERRAFORM = "grafana_terraform"
    DATADOG = "datadog"
    DATADOG_TERRAFORM = "datadog_terraform"
    NEWRELIC = "newrelic"
    SPLUNK = "splunk"
    ELASTIC_APM = "elastic_apm"
    DYNATRACE = "dynatrace"
    HONEYCOMB = "honeycomb"
    LIGHTSTEP = "lightstep"
    JAEGER = "jaeger"
    ZIPKIN = "zipkin"
    TEMPO = "tempo"
    LOKI = "loki"
    THANOS = "thanos"
    CORTEX = "cortex"
    MIMIR = "mimir"
    VICTORIAMETRICS_OPERATOR = "victoriametrics_operator"
    SIGNOZ = "signoz"
    UPTRACE = "uptrace"
    HIGHLIGHT = "highlight"
    SENTRY = "sentry"
    ROLLBAR = "rollbar"
    BUGSNAG = "bugsnag"
    LOGDNA = "logdna"
    PAPERTRAIL = "papertrail"
    LOGGLY = "loggly"
    SUMOLOGIC = "sumologic"
    CORALOGIX = "coralogix"
    AXIOM = "axiom"

    # =========================================================================
    # COST MANAGEMENT
    # =========================================================================
    INFRACOST = "infracost"
    KUBECOST = "kubecost"
    OPENCOST = "opencost"
    CLOUDHEALTH = "cloudhealth"
    SPOT_IO = "spot_io"
    CAST_AI = "cast_ai"
    KARPENTER = "karpenter"
    CLUSTER_AUTOSCALER = "cluster_autoscaler"
    GOLDILOCKS = "goldilocks"
    VPA = "vpa"
    RIGHTSIZING = "rightsizing"

    # =========================================================================
    # DATABASES IaC
    # =========================================================================
    ATLAS = "atlas"  # Database schema management
    PRISMA = "prisma"
    PLANETSCALE_CLI = "planetscale_cli"
    FLYWAY = "flyway"
    LIQUIBASE = "liquibase"
    SQITCH = "sqitch"
    BYTEBASE = "bytebase"


class InfrastructureAction(Enum):
    """Infrastructure actions."""

    PLAN = "plan"
    APPLY = "apply"
    DESTROY = "destroy"
    VALIDATE = "validate"
    IMPORT = "import"
    REFRESH = "refresh"


@dataclass
class InfrastructureChange:
    """Represents a single infrastructure change."""

    action: str  # create, update, delete, no-op
    resource_type: str
    resource_name: str
    resource_address: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InfrastructurePlan:
    """Result of infrastructure planning."""

    provider: InfrastructureProvider
    changes: List[InfrastructureChange]
    summary: Dict[str, int]  # {add: 3, change: 2, destroy: 1}
    plan_file: Optional[str] = None
    raw_output: str = ""
    cost_estimate: Optional[Dict[str, Any]] = None


@dataclass
class InfrastructureResult:
    """Result of infrastructure operation."""

    success: bool
    provider: InfrastructureProvider
    action: InfrastructureAction
    changes_applied: List[InfrastructureChange] = field(default_factory=list)
    outputs: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    state_file: Optional[str] = None
    rollback_command: Optional[str] = None


class InfrastructureExecutorService:
    """
    Service for executing real infrastructure operations.

    Supports:
    - Terraform: plan, apply, destroy, validate, import
    - Kubernetes: apply, delete, rollout
    - Helm: install, upgrade, rollback, uninstall
    - CloudFormation: create-stack, update-stack, delete-stack
    """

    def __init__(self):
        self._operation_history: List[InfrastructureResult] = []
        self._state_backups: Dict[str, str] = {}

    def _get_command_env(self) -> dict:
        """
        Get environment for command execution with nvm compatibility fixes.
        Removes npm_config_prefix which conflicts with nvm.
        """
        env = os.environ.copy()
        env.pop("npm_config_prefix", None)  # Remove to fix nvm compatibility
        env["SHELL"] = env.get("SHELL", "/bin/bash")
        return env

    async def check_prerequisites(
        self, provider: InfrastructureProvider
    ) -> Tuple[bool, str]:
        """Check if prerequisites are met for the provider."""
        checks = {
            InfrastructureProvider.TERRAFORM: self._check_terraform,
            InfrastructureProvider.KUBERNETES: self._check_kubernetes,
            InfrastructureProvider.HELM: self._check_helm,
            InfrastructureProvider.CLOUDFORMATION: self._check_cloudformation,
            InfrastructureProvider.PULUMI: self._check_pulumi,
        }

        checker = checks.get(provider)
        if checker:
            return await checker()
        return False, f"Provider {provider.value} not supported"

    # -------------------------------------------------------------------------
    # Terraform Operations
    # -------------------------------------------------------------------------

    async def terraform_init(
        self,
        workspace_path: str,
        backend_config: Optional[Dict[str, str]] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> InfrastructureResult:
        """Initialize Terraform workspace."""
        result = InfrastructureResult(
            success=False,
            provider=InfrastructureProvider.TERRAFORM,
            action=InfrastructureAction.VALIDATE,
        )

        if progress_callback:
            progress_callback("Initializing Terraform...", 10)

        cmd = ["terraform", "init", "-input=false"]

        if backend_config:
            for key, value in backend_config.items():
                cmd.append(f"-backend-config={key}={value}")

        output = await self._run_command(cmd, cwd=workspace_path)
        result.logs = output.get("logs", [])

        if output["returncode"] == 0:
            result.success = True
            if progress_callback:
                progress_callback("Terraform initialized successfully", 100)
        else:
            result.error = output["stderr"]

        return result

    async def terraform_plan(
        self,
        workspace_path: str,
        variables: Optional[Dict[str, Any]] = None,
        var_file: Optional[str] = None,
        target: Optional[List[str]] = None,
        destroy: bool = False,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> InfrastructurePlan:
        """
        Create a Terraform plan.

        Returns detailed information about what changes would be made.
        """
        plan = InfrastructurePlan(
            provider=InfrastructureProvider.TERRAFORM,
            changes=[],
            summary={"add": 0, "change": 0, "destroy": 0},
        )

        # Ensure initialized
        await self.terraform_init(workspace_path, progress_callback=progress_callback)

        if progress_callback:
            progress_callback("Creating Terraform plan...", 30)

        # Create temp file for plan
        plan_file = tempfile.mktemp(suffix=".tfplan")

        cmd = ["terraform", "plan", "-input=false", "-out", plan_file, "-json"]

        if destroy:
            cmd.append("-destroy")

        if variables:
            for key, value in variables.items():
                cmd.append(f"-var={key}={value}")

        if var_file:
            cmd.append(f"-var-file={var_file}")

        if target:
            for t in target:
                cmd.append(f"-target={t}")

        output = await self._run_command_streaming(
            cmd, cwd=workspace_path, progress_callback=progress_callback
        )
        plan.raw_output = output["stdout"]
        plan.plan_file = plan_file

        # Parse JSON output for changes
        changes = self._parse_terraform_plan_json(output["stdout"])
        plan.changes = changes

        # Calculate summary
        for change in changes:
            if change.action == "create":
                plan.summary["add"] += 1
            elif change.action == "update":
                plan.summary["change"] += 1
            elif change.action == "delete":
                plan.summary["destroy"] += 1

        if progress_callback:
            progress_callback(
                f"Plan complete: +{plan.summary['add']} ~{plan.summary['change']} -{plan.summary['destroy']}",
                100,
            )

        return plan

    async def terraform_apply(
        self,
        workspace_path: str,
        plan_file: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        var_file: Optional[str] = None,
        target: Optional[List[str]] = None,
        auto_approve: bool = False,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> InfrastructureResult:
        """
        Apply Terraform changes.

        WARNING: This makes real changes to infrastructure!
        """
        result = InfrastructureResult(
            success=False,
            provider=InfrastructureProvider.TERRAFORM,
            action=InfrastructureAction.APPLY,
        )

        start_time = datetime.utcnow()

        # Backup state file before apply
        state_file = Path(workspace_path) / "terraform.tfstate"
        if state_file.exists():
            backup_path = (
                f"{state_file}.backup.{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            )
            shutil.copy(state_file, backup_path)
            self._state_backups[workspace_path] = backup_path
            result.rollback_command = (
                f"cp {backup_path} {state_file} && terraform apply -refresh-only"
            )

        if progress_callback:
            progress_callback("Applying Terraform changes...", 20)

        cmd = ["terraform", "apply", "-input=false", "-json"]

        if auto_approve:
            cmd.append("-auto-approve")

        if plan_file:
            cmd.append(plan_file)
        else:
            cmd.append("-auto-approve")  # Required if no plan file

            if variables:
                for key, value in variables.items():
                    cmd.append(f"-var={key}={value}")

            if var_file:
                cmd.append(f"-var-file={var_file}")

            if target:
                for t in target:
                    cmd.append(f"-target={t}")

        output = await self._run_command_streaming(
            cmd, cwd=workspace_path, progress_callback=progress_callback
        )
        result.logs = output.get("logs", [])

        if output["returncode"] == 0:
            result.success = True

            # Parse outputs
            outputs_result = await self._run_command(
                ["terraform", "output", "-json"], cwd=workspace_path
            )
            if outputs_result["returncode"] == 0:
                try:
                    result.outputs = json.loads(outputs_result["stdout"])
                except json.JSONDecodeError:
                    pass

            if progress_callback:
                progress_callback("Terraform apply completed successfully", 100)
        else:
            result.error = output["stderr"]
            if progress_callback:
                progress_callback(f"Terraform apply failed: {result.error}", 100)

        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        self._operation_history.append(result)

        return result

    async def terraform_destroy(
        self,
        workspace_path: str,
        variables: Optional[Dict[str, Any]] = None,
        var_file: Optional[str] = None,
        target: Optional[List[str]] = None,
        auto_approve: bool = False,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> InfrastructureResult:
        """
        Destroy Terraform-managed infrastructure.

        WARNING: This PERMANENTLY DELETES infrastructure!
        """
        result = InfrastructureResult(
            success=False,
            provider=InfrastructureProvider.TERRAFORM,
            action=InfrastructureAction.DESTROY,
        )

        start_time = datetime.utcnow()

        if progress_callback:
            progress_callback("⚠️ DESTROYING infrastructure...", 20)

        cmd = ["terraform", "destroy", "-input=false", "-json"]

        if auto_approve:
            cmd.append("-auto-approve")

        if variables:
            for key, value in variables.items():
                cmd.append(f"-var={key}={value}")

        if var_file:
            cmd.append(f"-var-file={var_file}")

        if target:
            for t in target:
                cmd.append(f"-target={t}")

        output = await self._run_command_streaming(
            cmd, cwd=workspace_path, progress_callback=progress_callback
        )
        result.logs = output.get("logs", [])

        if output["returncode"] == 0:
            result.success = True
            if progress_callback:
                progress_callback("Infrastructure destroyed", 100)
        else:
            result.error = output["stderr"]

        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        self._operation_history.append(result)

        return result

    # -------------------------------------------------------------------------
    # Kubernetes Operations
    # -------------------------------------------------------------------------

    async def kubectl_apply(
        self,
        manifest_path: str,
        namespace: Optional[str] = None,
        dry_run: bool = False,
        server_dry_run: bool = False,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> InfrastructureResult:
        """Apply Kubernetes manifests."""
        result = InfrastructureResult(
            success=False,
            provider=InfrastructureProvider.KUBERNETES,
            action=InfrastructureAction.APPLY,
        )

        start_time = datetime.utcnow()

        if progress_callback:
            progress_callback("Applying Kubernetes manifests...", 20)

        cmd = ["kubectl", "apply", "-f", manifest_path]

        if namespace:
            cmd.extend(["-n", namespace])

        if dry_run:
            cmd.append("--dry-run=client")
        elif server_dry_run:
            cmd.append("--dry-run=server")

        cmd.append("-o=json")

        output = await self._run_command_streaming(
            cmd, progress_callback=progress_callback
        )
        result.logs = output.get("logs", [])

        if output["returncode"] == 0:
            result.success = True

            # Parse applied resources
            try:
                applied = json.loads(output["stdout"])
                if applied.get("kind") == "List":
                    for item in applied.get("items", []):
                        result.changes_applied.append(
                            InfrastructureChange(
                                action="apply",
                                resource_type=item.get("kind", "Unknown"),
                                resource_name=item.get("metadata", {}).get(
                                    "name", "Unknown"
                                ),
                                resource_address=f"{item.get('kind')}/{item.get('metadata', {}).get('name')}",
                            )
                        )
            except json.JSONDecodeError:
                pass

            result.rollback_command = f"kubectl delete -f {manifest_path}"

            if progress_callback:
                progress_callback("Kubernetes manifests applied", 100)
        else:
            result.error = output["stderr"]

        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        self._operation_history.append(result)

        return result

    async def kubectl_delete(
        self,
        manifest_path: str,
        namespace: Optional[str] = None,
        force: bool = False,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> InfrastructureResult:
        """Delete Kubernetes resources."""
        result = InfrastructureResult(
            success=False,
            provider=InfrastructureProvider.KUBERNETES,
            action=InfrastructureAction.DESTROY,
        )

        start_time = datetime.utcnow()

        if progress_callback:
            progress_callback("Deleting Kubernetes resources...", 20)

        cmd = ["kubectl", "delete", "-f", manifest_path]

        if namespace:
            cmd.extend(["-n", namespace])

        if force:
            cmd.append("--force")

        output = await self._run_command_streaming(
            cmd, progress_callback=progress_callback
        )
        result.logs = output.get("logs", [])

        if output["returncode"] == 0:
            result.success = True
            if progress_callback:
                progress_callback("Kubernetes resources deleted", 100)
        else:
            result.error = output["stderr"]

        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        self._operation_history.append(result)

        return result

    async def kubectl_rollout_undo(
        self,
        resource_type: str,
        resource_name: str,
        namespace: Optional[str] = None,
        revision: Optional[int] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> InfrastructureResult:
        """Rollback a Kubernetes deployment."""
        result = InfrastructureResult(
            success=False,
            provider=InfrastructureProvider.KUBERNETES,
            action=InfrastructureAction.APPLY,
        )

        start_time = datetime.utcnow()

        if progress_callback:
            progress_callback(f"Rolling back {resource_type}/{resource_name}...", 20)

        cmd = ["kubectl", "rollout", "undo", f"{resource_type}/{resource_name}"]

        if namespace:
            cmd.extend(["-n", namespace])

        if revision:
            cmd.extend(["--to-revision", str(revision)])

        output = await self._run_command(cmd)
        result.logs = [output["stdout"], output["stderr"]]

        if output["returncode"] == 0:
            result.success = True

            # Wait for rollout
            if progress_callback:
                progress_callback("Waiting for rollout to complete...", 60)

            wait_cmd = [
                "kubectl",
                "rollout",
                "status",
                f"{resource_type}/{resource_name}",
            ]
            if namespace:
                wait_cmd.extend(["-n", namespace])

            wait_output = await self._run_command(wait_cmd)
            result.logs.append(wait_output["stdout"])

            if progress_callback:
                progress_callback("Rollback completed", 100)
        else:
            result.error = output["stderr"]

        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()

        return result

    # -------------------------------------------------------------------------
    # Helm Operations
    # -------------------------------------------------------------------------

    async def helm_install(
        self,
        release_name: str,
        chart: str,
        namespace: Optional[str] = None,
        values_file: Optional[str] = None,
        set_values: Optional[Dict[str, str]] = None,
        create_namespace: bool = True,
        dry_run: bool = False,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> InfrastructureResult:
        """Install a Helm chart."""
        result = InfrastructureResult(
            success=False,
            provider=InfrastructureProvider.HELM,
            action=InfrastructureAction.APPLY,
        )

        start_time = datetime.utcnow()

        if progress_callback:
            progress_callback(f"Installing Helm chart: {chart}...", 20)

        cmd = ["helm", "install", release_name, chart]

        if namespace:
            cmd.extend(["--namespace", namespace])

        if create_namespace:
            cmd.append("--create-namespace")

        if values_file:
            cmd.extend(["-f", values_file])

        if set_values:
            for key, value in set_values.items():
                cmd.extend(["--set", f"{key}={value}"])

        if dry_run:
            cmd.append("--dry-run")

        cmd.append("--output=json")

        output = await self._run_command_streaming(
            cmd, progress_callback=progress_callback
        )
        result.logs = output.get("logs", [])

        if output["returncode"] == 0:
            result.success = True
            result.rollback_command = f"helm uninstall {release_name}" + (
                f" -n {namespace}" if namespace else ""
            )

            if progress_callback:
                progress_callback(f"Helm chart {release_name} installed", 100)
        else:
            result.error = output["stderr"]

        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        self._operation_history.append(result)

        return result

    async def helm_upgrade(
        self,
        release_name: str,
        chart: str,
        namespace: Optional[str] = None,
        values_file: Optional[str] = None,
        set_values: Optional[Dict[str, str]] = None,
        install: bool = True,
        atomic: bool = False,
        dry_run: bool = False,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> InfrastructureResult:
        """Upgrade a Helm release."""
        result = InfrastructureResult(
            success=False,
            provider=InfrastructureProvider.HELM,
            action=InfrastructureAction.APPLY,
        )

        start_time = datetime.utcnow()

        if progress_callback:
            progress_callback(f"Upgrading Helm release: {release_name}...", 20)

        cmd = ["helm", "upgrade", release_name, chart]

        if namespace:
            cmd.extend(["--namespace", namespace])

        if install:
            cmd.append("--install")

        if atomic:
            cmd.append("--atomic")

        if values_file:
            cmd.extend(["-f", values_file])

        if set_values:
            for key, value in set_values.items():
                cmd.extend(["--set", f"{key}={value}"])

        if dry_run:
            cmd.append("--dry-run")

        output = await self._run_command_streaming(
            cmd, progress_callback=progress_callback
        )
        result.logs = output.get("logs", [])

        if output["returncode"] == 0:
            result.success = True
            result.rollback_command = f"helm rollback {release_name}" + (
                f" -n {namespace}" if namespace else ""
            )

            if progress_callback:
                progress_callback(f"Helm release {release_name} upgraded", 100)
        else:
            result.error = output["stderr"]

        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        self._operation_history.append(result)

        return result

    async def helm_rollback(
        self,
        release_name: str,
        revision: Optional[int] = None,
        namespace: Optional[str] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> InfrastructureResult:
        """Rollback a Helm release."""
        result = InfrastructureResult(
            success=False,
            provider=InfrastructureProvider.HELM,
            action=InfrastructureAction.APPLY,
        )

        start_time = datetime.utcnow()

        if progress_callback:
            progress_callback(f"Rolling back Helm release: {release_name}...", 20)

        cmd = ["helm", "rollback", release_name]

        if revision:
            cmd.append(str(revision))

        if namespace:
            cmd.extend(["--namespace", namespace])

        output = await self._run_command(cmd)
        result.logs = [output["stdout"], output["stderr"]]

        if output["returncode"] == 0:
            result.success = True
            if progress_callback:
                progress_callback(f"Helm release {release_name} rolled back", 100)
        else:
            result.error = output["stderr"]

        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()

        return result

    async def helm_uninstall(
        self,
        release_name: str,
        namespace: Optional[str] = None,
        dry_run: bool = False,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> InfrastructureResult:
        """Uninstall a Helm release."""
        result = InfrastructureResult(
            success=False,
            provider=InfrastructureProvider.HELM,
            action=InfrastructureAction.DESTROY,
        )

        start_time = datetime.utcnow()

        if progress_callback:
            progress_callback(f"Uninstalling Helm release: {release_name}...", 20)

        cmd = ["helm", "uninstall", release_name]

        if namespace:
            cmd.extend(["--namespace", namespace])

        if dry_run:
            cmd.append("--dry-run")

        output = await self._run_command(cmd)
        result.logs = [output["stdout"], output["stderr"]]

        if output["returncode"] == 0:
            result.success = True
            if progress_callback:
                progress_callback(f"Helm release {release_name} uninstalled", 100)
        else:
            result.error = output["stderr"]

        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        self._operation_history.append(result)

        return result

    # -------------------------------------------------------------------------
    # CloudFormation Operations
    # -------------------------------------------------------------------------

    async def cfn_deploy(
        self,
        stack_name: str,
        template_file: str,
        parameters: Optional[Dict[str, str]] = None,
        capabilities: Optional[List[str]] = None,
        region: Optional[str] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> InfrastructureResult:
        """Deploy a CloudFormation stack."""
        result = InfrastructureResult(
            success=False,
            provider=InfrastructureProvider.CLOUDFORMATION,
            action=InfrastructureAction.APPLY,
        )

        start_time = datetime.utcnow()

        if progress_callback:
            progress_callback(f"Deploying CloudFormation stack: {stack_name}...", 20)

        cmd = [
            "aws",
            "cloudformation",
            "deploy",
            "--stack-name",
            stack_name,
            "--template-file",
            template_file,
        ]

        if parameters:
            param_overrides = [f"{k}={v}" for k, v in parameters.items()]
            cmd.extend(["--parameter-overrides"] + param_overrides)

        if capabilities:
            cmd.extend(["--capabilities"] + capabilities)
        else:
            cmd.extend(["--capabilities", "CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"])

        if region:
            cmd.extend(["--region", region])

        output = await self._run_command_streaming(
            cmd, progress_callback=progress_callback
        )
        result.logs = output.get("logs", [])

        if output["returncode"] == 0:
            result.success = True
            result.rollback_command = (
                f"aws cloudformation delete-stack --stack-name {stack_name}"
            )

            # Get stack outputs
            outputs_cmd = [
                "aws",
                "cloudformation",
                "describe-stacks",
                "--stack-name",
                stack_name,
                "--query",
                "Stacks[0].Outputs",
                "--output",
                "json",
            ]
            if region:
                outputs_cmd.extend(["--region", region])

            outputs_result = await self._run_command(outputs_cmd)
            if outputs_result["returncode"] == 0:
                try:
                    outputs = json.loads(outputs_result["stdout"])
                    result.outputs = {
                        o["OutputKey"]: o["OutputValue"] for o in (outputs or [])
                    }
                except (json.JSONDecodeError, KeyError):
                    pass

            if progress_callback:
                progress_callback(f"CloudFormation stack {stack_name} deployed", 100)
        else:
            result.error = output["stderr"]

        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        self._operation_history.append(result)

        return result

    async def cfn_delete(
        self,
        stack_name: str,
        region: Optional[str] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> InfrastructureResult:
        """Delete a CloudFormation stack."""
        result = InfrastructureResult(
            success=False,
            provider=InfrastructureProvider.CLOUDFORMATION,
            action=InfrastructureAction.DESTROY,
        )

        start_time = datetime.utcnow()

        if progress_callback:
            progress_callback(f"Deleting CloudFormation stack: {stack_name}...", 20)

        cmd = ["aws", "cloudformation", "delete-stack", "--stack-name", stack_name]

        if region:
            cmd.extend(["--region", region])

        output = await self._run_command(cmd)

        if output["returncode"] == 0:
            # Wait for deletion
            if progress_callback:
                progress_callback("Waiting for stack deletion...", 50)

            wait_cmd = [
                "aws",
                "cloudformation",
                "wait",
                "stack-delete-complete",
                "--stack-name",
                stack_name,
            ]
            if region:
                wait_cmd.extend(["--region", region])

            wait_output = await self._run_command(wait_cmd)

            if wait_output["returncode"] == 0:
                result.success = True
                if progress_callback:
                    progress_callback(f"CloudFormation stack {stack_name} deleted", 100)
            else:
                result.error = wait_output["stderr"]
        else:
            result.error = output["stderr"]

        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        self._operation_history.append(result)

        return result

    # -------------------------------------------------------------------------
    # Prerequisite Checks
    # -------------------------------------------------------------------------

    async def _check_terraform(self) -> Tuple[bool, str]:
        """Check Terraform installation."""
        if not shutil.which("terraform"):
            return (
                False,
                "Terraform not installed. See: https://www.terraform.io/downloads",
            )

        result = await self._run_command(["terraform", "version", "-json"])
        if result["returncode"] == 0:
            try:
                version_info = json.loads(result["stdout"])
                version = version_info.get("terraform_version", "unknown")
                return True, f"Terraform v{version}"
            except json.JSONDecodeError:
                return True, "Terraform installed"
        return False, "Failed to check Terraform version"

    async def _check_kubernetes(self) -> Tuple[bool, str]:
        """Check kubectl installation and cluster connection."""
        if not shutil.which("kubectl"):
            return False, "kubectl not installed"

        result = await self._run_command(["kubectl", "cluster-info"])
        if result["returncode"] == 0:
            return True, "Connected to Kubernetes cluster"
        return False, "Cannot connect to Kubernetes cluster"

    async def _check_helm(self) -> Tuple[bool, str]:
        """Check Helm installation."""
        if not shutil.which("helm"):
            return False, "Helm not installed. See: https://helm.sh/docs/intro/install/"

        result = await self._run_command(["helm", "version", "--short"])
        if result["returncode"] == 0:
            return True, f"Helm {result['stdout'].strip()}"
        return False, "Failed to check Helm version"

    async def _check_cloudformation(self) -> Tuple[bool, str]:
        """Check AWS CLI installation."""
        if not shutil.which("aws"):
            return False, "AWS CLI not installed"

        result = await self._run_command(["aws", "sts", "get-caller-identity"])
        if result["returncode"] == 0:
            return True, "AWS CLI configured"
        return False, "AWS credentials not configured"

    async def _check_pulumi(self) -> Tuple[bool, str]:
        """Check Pulumi installation."""
        if not shutil.which("pulumi"):
            return (
                False,
                "Pulumi not installed. See: https://www.pulumi.com/docs/get-started/install/",
            )

        result = await self._run_command(["pulumi", "version"])
        if result["returncode"] == 0:
            return True, f"Pulumi {result['stdout'].strip()}"
        return False, "Failed to check Pulumi version"

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def _parse_terraform_plan_json(self, output: str) -> List[InfrastructureChange]:
        """Parse Terraform plan JSON output."""
        changes = []

        for line in output.split("\n"):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if (
                    data.get("type") == "resource_drift"
                    or data.get("type") == "planned_change"
                ):
                    change = data.get("change", {})
                    resource = change.get("resource", {})

                    action_map = {
                        "create": "create",
                        "update": "update",
                        "delete": "delete",
                        "replace": "replace",
                        "no-op": "no-op",
                    }

                    actions = change.get("action", "no-op")
                    if isinstance(actions, list):
                        action = actions[0] if actions else "no-op"
                    else:
                        action = actions

                    changes.append(
                        InfrastructureChange(
                            action=action_map.get(action, action),
                            resource_type=resource.get("resource_type", "unknown"),
                            resource_name=resource.get("resource_name", "unknown"),
                            resource_address=resource.get("addr", "unknown"),
                            details=change,
                        )
                    )
            except json.JSONDecodeError:
                continue

        return changes

    async def _run_command(
        self,
        cmd: List[str],
        cwd: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run a command and return the result."""
        try:
            env = self._get_command_env()

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )

            stdout, stderr = await process.communicate()

            return {
                "returncode": process.returncode,
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else "",
            }
        except Exception as e:
            return {
                "returncode": 1,
                "stdout": "",
                "stderr": str(e),
            }

    async def _run_command_streaming(
        self,
        cmd: List[str],
        cwd: Optional[str] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> Dict[str, Any]:
        """Run a command with streaming output."""
        logs = []
        stdout_lines = []
        stderr_lines = []

        try:
            env = self._get_command_env()

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )

            async def read_stream(stream, lines_list, is_stderr=False):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded = line.decode().strip()
                    lines_list.append(decoded)
                    logs.append(decoded)

                    if progress_callback and not is_stderr:
                        progress_callback(decoded, 50)

            await asyncio.gather(
                read_stream(process.stdout, stdout_lines),
                read_stream(process.stderr, stderr_lines, True),
            )

            await process.wait()

            return {
                "returncode": process.returncode,
                "stdout": "\n".join(stdout_lines),
                "stderr": "\n".join(stderr_lines),
                "logs": logs,
            }
        except Exception as e:
            return {
                "returncode": 1,
                "stdout": "",
                "stderr": str(e),
                "logs": logs,
            }

    # -------------------------------------------------------------------------
    # REAL Kubernetes Cluster Provisioning
    # -------------------------------------------------------------------------

    async def provision_eks_cluster(
        self,
        cluster_name: str,
        region: str,
        config_path: str,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        timeout_seconds: int = 1800,  # 30 minutes
    ) -> InfrastructureResult:
        """
        Actually provision an EKS cluster using eksctl.

        This is a REAL provisioning operation that will:
        1. Create the EKS cluster (10-15 minutes)
        2. Wait for cluster to be ready
        3. Update kubeconfig
        4. Verify cluster connectivity

        Args:
            cluster_name: Name for the cluster
            region: AWS region
            config_path: Path to eksctl config file
            progress_callback: Progress callback
            timeout_seconds: Max time to wait

        Returns:
            InfrastructureResult with cluster details
        """
        result = InfrastructureResult(
            success=False,
            provider=InfrastructureProvider.KUBERNETES,
            action=InfrastructureAction.APPLY,
        )

        start_time = datetime.utcnow()

        # Check eksctl is installed
        if not shutil.which("eksctl"):
            result.error = (
                "eksctl not installed. Install: https://eksctl.io/installation/"
            )
            return result

        if progress_callback:
            progress_callback("Creating EKS cluster (this takes 10-15 minutes)...", 5)

        # Create cluster
        cmd = ["eksctl", "create", "cluster", "-f", config_path]

        logger.info(f"Running: {' '.join(cmd)}")

        try:
            env = self._get_command_env()
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            # Stream output while waiting
            logs = []

            async def stream_output():
                while True:
                    if process.stdout:
                        line = await process.stdout.readline()
                        if line:
                            decoded = line.decode().strip()
                            logs.append(decoded)
                            logger.info(f"[eksctl] {decoded}")
                            if progress_callback:
                                # Estimate progress based on output
                                if "creating" in decoded.lower():
                                    progress_callback(decoded[:80], 20)
                                elif "waiting" in decoded.lower():
                                    progress_callback(decoded[:80], 50)
                                elif "nodegroup" in decoded.lower():
                                    progress_callback(decoded[:80], 70)
                        else:
                            break
                    else:
                        break

            # Wait with timeout
            try:
                await asyncio.wait_for(
                    asyncio.gather(stream_output(), process.wait()),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                process.terminate()
                result.error = (
                    f"Cluster creation timed out after {timeout_seconds} seconds"
                )
                result.logs = logs
                return result

            result.logs = logs

            if process.returncode == 0:
                if progress_callback:
                    progress_callback("Updating kubeconfig...", 85)

                # Update kubeconfig
                kubeconfig_cmd = [
                    "aws",
                    "eks",
                    "update-kubeconfig",
                    "--name",
                    cluster_name,
                    "--region",
                    region,
                ]
                kubeconfig_result = await self._run_command(kubeconfig_cmd)

                if kubeconfig_result["returncode"] != 0:
                    result.error = (
                        f"Failed to update kubeconfig: {kubeconfig_result['stderr']}"
                    )
                    return result

                if progress_callback:
                    progress_callback("Verifying cluster connectivity...", 95)

                # Verify connectivity
                verify_cmd = ["kubectl", "cluster-info"]
                verify_result = await self._run_command(verify_cmd)

                if verify_result["returncode"] == 0:
                    result.success = True
                    result.outputs = {
                        "cluster_name": cluster_name,
                        "region": region,
                        "endpoint": await self._get_eks_endpoint(cluster_name, region),
                        "status": "ACTIVE",
                    }
                    result.rollback_command = (
                        f"eksctl delete cluster --name {cluster_name} --region {region}"
                    )

                    if progress_callback:
                        progress_callback("EKS cluster created successfully!", 100)
                else:
                    result.error = f"Cluster created but connectivity failed: {verify_result['stderr']}"
            else:
                stderr = ""
                if process.stderr:
                    stderr = (await process.stderr.read()).decode()
                result.error = f"eksctl failed: {stderr}"

        except Exception as e:
            result.error = str(e)
            logger.error(f"EKS cluster creation failed: {e}")

        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        self._operation_history.append(result)

        return result

    async def provision_gke_cluster(
        self,
        cluster_name: str,
        region: str,
        project_id: str,
        machine_type: str = "e2-standard-4",
        node_count: int = 3,
        enable_autopilot: bool = False,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        timeout_seconds: int = 1200,  # 20 minutes
    ) -> InfrastructureResult:
        """
        Actually provision a GKE cluster using gcloud.

        Args:
            cluster_name: Name for the cluster
            region: GCP region
            project_id: GCP project ID
            machine_type: Machine type for nodes
            node_count: Number of nodes
            enable_autopilot: Use GKE Autopilot
            progress_callback: Progress callback
            timeout_seconds: Max time to wait

        Returns:
            InfrastructureResult with cluster details
        """
        result = InfrastructureResult(
            success=False,
            provider=InfrastructureProvider.KUBERNETES,
            action=InfrastructureAction.APPLY,
        )

        start_time = datetime.utcnow()

        # Check gcloud is installed
        if not shutil.which("gcloud"):
            result.error = "gcloud CLI not installed"
            return result

        if progress_callback:
            progress_callback("Creating GKE cluster (this takes 5-10 minutes)...", 5)

        # Build command
        if enable_autopilot:
            cmd = [
                "gcloud",
                "container",
                "clusters",
                "create-auto",
                cluster_name,
                f"--region={region}",
                f"--project={project_id}",
            ]
        else:
            cmd = [
                "gcloud",
                "container",
                "clusters",
                "create",
                cluster_name,
                f"--region={region}",
                f"--project={project_id}",
                f"--machine-type={machine_type}",
                f"--num-nodes={node_count}",
                "--enable-autoscaling",
                "--min-nodes=1",
                f"--max-nodes={node_count * 2}",
            ]

        logger.info(f"Running: {' '.join(cmd)}")

        output = await self._run_command_streaming(
            cmd,
            progress_callback=lambda msg, pct: (
                progress_callback(msg, 10 + pct * 0.7) if progress_callback else None
            ),
        )

        result.logs = output.get("logs", [])

        if output["returncode"] == 0:
            if progress_callback:
                progress_callback("Getting cluster credentials...", 85)

            # Get credentials
            cred_cmd = [
                "gcloud",
                "container",
                "clusters",
                "get-credentials",
                cluster_name,
                f"--region={region}",
                f"--project={project_id}",
            ]
            cred_result = await self._run_command(cred_cmd)

            if cred_result["returncode"] == 0:
                if progress_callback:
                    progress_callback("Verifying cluster connectivity...", 95)

                # Verify
                verify_cmd = ["kubectl", "cluster-info"]
                verify_result = await self._run_command(verify_cmd)

                if verify_result["returncode"] == 0:
                    result.success = True
                    result.outputs = {
                        "cluster_name": cluster_name,
                        "region": region,
                        "project_id": project_id,
                        "status": "RUNNING",
                    }
                    result.rollback_command = f"gcloud container clusters delete {cluster_name} --region {region} --project {project_id} --quiet"

                    if progress_callback:
                        progress_callback("GKE cluster created successfully!", 100)
                else:
                    result.error = f"Cluster created but connectivity failed: {verify_result['stderr']}"
            else:
                result.error = f"Failed to get credentials: {cred_result['stderr']}"
        else:
            result.error = output["stderr"]

        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        self._operation_history.append(result)

        return result

    async def provision_aks_cluster(
        self,
        cluster_name: str,
        resource_group: str,
        location: str,
        node_count: int = 3,
        vm_size: str = "Standard_D4s_v3",
        progress_callback: Optional[Callable[[str, float], None]] = None,
        timeout_seconds: int = 1200,
    ) -> InfrastructureResult:
        """
        Actually provision an AKS cluster using az CLI.

        Args:
            cluster_name: Name for the cluster
            resource_group: Azure resource group
            location: Azure region
            node_count: Number of nodes
            vm_size: VM size
            progress_callback: Progress callback
            timeout_seconds: Max time to wait

        Returns:
            InfrastructureResult with cluster details
        """
        result = InfrastructureResult(
            success=False,
            provider=InfrastructureProvider.KUBERNETES,
            action=InfrastructureAction.APPLY,
        )

        start_time = datetime.utcnow()

        # Check az is installed
        if not shutil.which("az"):
            result.error = "Azure CLI not installed"
            return result

        if progress_callback:
            progress_callback("Creating resource group...", 5)

        # Create resource group
        rg_cmd = [
            "az",
            "group",
            "create",
            "--name",
            resource_group,
            "--location",
            location,
        ]
        rg_result = await self._run_command(rg_cmd)

        if (
            rg_result["returncode"] != 0
            and "already exists" not in rg_result["stderr"].lower()
        ):
            result.error = f"Failed to create resource group: {rg_result['stderr']}"
            return result

        if progress_callback:
            progress_callback("Creating AKS cluster (this takes 5-10 minutes)...", 10)

        # Create cluster
        cmd = [
            "az",
            "aks",
            "create",
            "--name",
            cluster_name,
            "--resource-group",
            resource_group,
            "--node-count",
            str(node_count),
            "--node-vm-size",
            vm_size,
            "--enable-cluster-autoscaler",
            "--min-count",
            "1",
            "--max-count",
            str(node_count * 2),
            "--generate-ssh-keys",
        ]

        logger.info(f"Running: {' '.join(cmd)}")

        output = await self._run_command_streaming(
            cmd,
            progress_callback=lambda msg, pct: (
                progress_callback(msg, 10 + pct * 0.7) if progress_callback else None
            ),
        )

        result.logs = output.get("logs", [])

        if output["returncode"] == 0:
            if progress_callback:
                progress_callback("Getting cluster credentials...", 85)

            # Get credentials
            cred_cmd = [
                "az",
                "aks",
                "get-credentials",
                "--name",
                cluster_name,
                "--resource-group",
                resource_group,
                "--overwrite-existing",
            ]
            cred_result = await self._run_command(cred_cmd)

            if cred_result["returncode"] == 0:
                if progress_callback:
                    progress_callback("Verifying cluster connectivity...", 95)

                # Verify
                verify_cmd = ["kubectl", "cluster-info"]
                verify_result = await self._run_command(verify_cmd)

                if verify_result["returncode"] == 0:
                    result.success = True
                    result.outputs = {
                        "cluster_name": cluster_name,
                        "resource_group": resource_group,
                        "location": location,
                        "status": "Running",
                    }
                    result.rollback_command = f"az aks delete --name {cluster_name} --resource-group {resource_group} --yes"

                    if progress_callback:
                        progress_callback("AKS cluster created successfully!", 100)
                else:
                    result.error = f"Cluster created but connectivity failed: {verify_result['stderr']}"
            else:
                result.error = f"Failed to get credentials: {cred_result['stderr']}"
        else:
            result.error = output["stderr"]

        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        self._operation_history.append(result)

        return result

    async def provision_local_cluster(
        self,
        cluster_name: str,
        provider: str = "kind",  # kind or minikube
        node_count: int = 1,
        config_path: Optional[str] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> InfrastructureResult:
        """
        Provision a local K8s cluster using kind or minikube.

        Args:
            cluster_name: Name for the cluster
            provider: "kind" or "minikube"
            node_count: Number of nodes (kind only)
            config_path: Path to kind config file
            progress_callback: Progress callback

        Returns:
            InfrastructureResult
        """
        result = InfrastructureResult(
            success=False,
            provider=InfrastructureProvider.KUBERNETES,
            action=InfrastructureAction.APPLY,
        )

        start_time = datetime.utcnow()

        if provider == "kind":
            if not shutil.which("kind"):
                result.error = "kind not installed. Install: https://kind.sigs.k8s.io/docs/user/quick-start/#installation"
                return result

            if progress_callback:
                progress_callback("Creating kind cluster...", 20)

            if config_path:
                cmd = [
                    "kind",
                    "create",
                    "cluster",
                    "--name",
                    cluster_name,
                    "--config",
                    config_path,
                ]
            else:
                cmd = ["kind", "create", "cluster", "--name", cluster_name]

        elif provider == "minikube":
            if not shutil.which("minikube"):
                result.error = "minikube not installed"
                return result

            if progress_callback:
                progress_callback("Creating minikube cluster...", 20)

            cmd = [
                "minikube",
                "start",
                "--profile",
                cluster_name,
                "--nodes",
                str(node_count + 1),
                "--driver=docker",
            ]
        else:
            result.error = f"Unsupported local provider: {provider}"
            return result

        logger.info(f"Running: {' '.join(cmd)}")

        output = await self._run_command_streaming(
            cmd, progress_callback=progress_callback
        )
        result.logs = output.get("logs", [])

        if output["returncode"] == 0:
            if progress_callback:
                progress_callback("Verifying cluster...", 90)

            # Verify
            verify_cmd = ["kubectl", "cluster-info"]
            verify_result = await self._run_command(verify_cmd)

            if verify_result["returncode"] == 0:
                result.success = True
                result.outputs = {
                    "cluster_name": cluster_name,
                    "provider": provider,
                    "status": "Running",
                }

                if provider == "kind":
                    result.rollback_command = (
                        f"kind delete cluster --name {cluster_name}"
                    )
                else:
                    result.rollback_command = (
                        f"minikube delete --profile {cluster_name}"
                    )

                if progress_callback:
                    progress_callback("Local cluster created!", 100)
            else:
                result.error = verify_result["stderr"]
        else:
            result.error = output["stderr"]

        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        self._operation_history.append(result)

        return result

    async def _get_eks_endpoint(self, cluster_name: str, region: str) -> str:
        """Get the EKS cluster endpoint."""
        cmd = [
            "aws",
            "eks",
            "describe-cluster",
            "--name",
            cluster_name,
            "--region",
            region,
            "--query",
            "cluster.endpoint",
            "--output",
            "text",
        ]
        result = await self._run_command(cmd)
        if result["returncode"] == 0:
            return result["stdout"].strip()
        return ""

    async def verify_cluster_health(
        self,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> Dict[str, Any]:
        """
        Verify that the current K8s cluster is healthy.

        Returns:
            Health check results
        """
        health = {
            "connected": False,
            "nodes_ready": 0,
            "nodes_total": 0,
            "system_pods_healthy": False,
            "api_server_healthy": False,
            "details": {},
        }

        if progress_callback:
            progress_callback("Checking cluster connectivity...", 20)

        # Check connectivity
        cluster_info = await self._run_command(["kubectl", "cluster-info"])
        if cluster_info["returncode"] != 0:
            health["details"]["error"] = "Cannot connect to cluster"
            return health

        health["connected"] = True
        health["api_server_healthy"] = True

        if progress_callback:
            progress_callback("Checking node status...", 40)

        # Check nodes
        nodes_result = await self._run_command(
            [
                "kubectl",
                "get",
                "nodes",
                "-o",
                'jsonpath={range .items[*]}{.status.conditions[?(@.type=="Ready")].status} {end}',
            ]
        )

        if nodes_result["returncode"] == 0:
            statuses = nodes_result["stdout"].strip().split()
            health["nodes_total"] = len(statuses)
            health["nodes_ready"] = sum(1 for s in statuses if s == "True")

        if progress_callback:
            progress_callback("Checking system pods...", 60)

        # Check system pods
        pods_result = await self._run_command(
            [
                "kubectl",
                "get",
                "pods",
                "-n",
                "kube-system",
                "-o",
                "jsonpath={range .items[*]}{.status.phase} {end}",
            ]
        )

        if pods_result["returncode"] == 0:
            phases = pods_result["stdout"].strip().split()
            running = sum(1 for p in phases if p in ["Running", "Succeeded"])
            health["system_pods_healthy"] = running == len(phases)
            health["details"]["system_pods"] = f"{running}/{len(phases)} healthy"

        if progress_callback:
            progress_callback("Health check complete", 100)

        return health


# Global instance
infrastructure_executor_service = InfrastructureExecutorService()
