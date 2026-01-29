"""
Deployment Executor Service for NAVI
Handles real deployment execution to various platforms.

Supports: Vercel, Railway, Fly.io, Netlify, Heroku, Render, AWS, GCP, Azure
"""

import asyncio
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class DeploymentPlatform(Enum):
    """Supported deployment platforms - 150+ platforms across all cloud providers."""

    # =========================================================================
    # MODERN PAAS PLATFORMS
    # =========================================================================
    VERCEL = "vercel"
    RAILWAY = "railway"
    FLY = "fly"
    NETLIFY = "netlify"
    HEROKU = "heroku"
    RENDER = "render"
    DENO_DEPLOY = "deno_deploy"
    CYCLIC = "cyclic"
    ADAPTABLE = "adaptable"
    QOVERY = "qovery"
    NORTHFLANK = "northflank"
    PLATFORM_SH = "platform_sh"
    DIVIO = "divio"
    BEGIN = "begin"
    KOYEB = "koyeb"
    ZEABUR = "zeabur"
    FLEEK = "fleek"
    DETA = "deta"
    VAL_TOWN = "val_town"
    WASP = "wasp"

    # =========================================================================
    # BACKEND-AS-A-SERVICE (BAAS)
    # =========================================================================
    SUPABASE = "supabase"
    FIREBASE = "firebase"
    APPWRITE = "appwrite"
    NHOST = "nhost"
    POCKETBASE = "pocketbase"
    CONVEX = "convex"
    BACK4APP = "back4app"
    PARSE = "parse"
    STRAPI_CLOUD = "strapi_cloud"
    DIRECTUS_CLOUD = "directus_cloud"
    SANITY = "sanity"
    CONTENTFUL = "contentful"
    HYGRAPH = "hygraph"
    PAYLOAD_CLOUD = "payload_cloud"
    KEYSTONEJS_CLOUD = "keystonejs_cloud"
    XATA = "xata"
    TURSO = "turso"
    PLANETSCALE = "planetscale"
    NEON = "neon"
    UPSTASH = "upstash"
    AIVEN = "aiven"
    FAUNA = "fauna"
    HASURA_CLOUD = "hasura_cloud"
    GRAFBASE = "grafbase"

    # =========================================================================
    # AWS - AMAZON WEB SERVICES
    # =========================================================================
    AWS_ECS = "aws_ecs"
    AWS_EKS = "aws_eks"
    AWS_LAMBDA = "aws_lambda"
    AWS_AMPLIFY = "aws_amplify"
    AWS_ELASTIC_BEANSTALK = "aws_elastic_beanstalk"
    AWS_APP_RUNNER = "aws_app_runner"
    AWS_LIGHTSAIL = "aws_lightsail"
    AWS_FARGATE = "aws_fargate"
    AWS_BATCH = "aws_batch"
    AWS_STEP_FUNCTIONS = "aws_step_functions"
    AWS_EVENTBRIDGE = "aws_eventbridge"
    AWS_S3_STATIC = "aws_s3_static"
    AWS_CLOUDFRONT = "aws_cloudfront"
    AWS_EC2 = "aws_ec2"
    AWS_AUTO_SCALING = "aws_auto_scaling"
    AWS_COPILOT = "aws_copilot"
    AWS_PROTON = "aws_proton"
    AWS_CODECATALYST = "aws_codecatalyst"
    LAMBDA_EDGE = "lambda_edge"
    CLOUDFLARE_WORKERS_INTEGRATION = "cloudflare_workers_integration"

    # =========================================================================
    # GOOGLE CLOUD PLATFORM
    # =========================================================================
    GCP_CLOUD_RUN = "gcp_cloud_run"
    GCP_APP_ENGINE = "gcp_app_engine"
    GCP_CLOUD_FUNCTIONS = "gcp_cloud_functions"
    GCP_GKE = "gcp_gke"
    GCP_COMPUTE_ENGINE = "gcp_compute_engine"
    GCP_CLOUD_BUILD = "gcp_cloud_build"
    GCP_ARTIFACT_REGISTRY = "gcp_artifact_registry"
    FIREBASE_HOSTING = "firebase_hosting"
    FIREBASE_FUNCTIONS = "firebase_functions"
    FIREBASE_APP_HOSTING = "firebase_app_hosting"
    GCP_CLOUD_SCHEDULER = "gcp_cloud_scheduler"
    GCP_CLOUD_TASKS = "gcp_cloud_tasks"
    GCP_WORKFLOWS = "gcp_workflows"

    # =========================================================================
    # MICROSOFT AZURE
    # =========================================================================
    AZURE_APP_SERVICE = "azure_app_service"
    AZURE_FUNCTIONS = "azure_functions"
    AZURE_CONTAINER_APPS = "azure_container_apps"
    AZURE_STATIC_WEBAPPS = "azure_static_webapps"
    AZURE_AKS = "azure_aks"
    AZURE_CONTAINER_INSTANCES = "azure_container_instances"
    AZURE_VM = "azure_vm"
    AZURE_VMSS = "azure_vmss"
    AZURE_BATCH = "azure_batch"
    AZURE_SPRING_APPS = "azure_spring_apps"
    AZURE_SERVICE_FABRIC = "azure_service_fabric"
    AZURE_LOGIC_APPS = "azure_logic_apps"
    AZURE_DURABLE_FUNCTIONS = "azure_durable_functions"
    AZURE_CDN = "azure_cdn"
    AZURE_FRONT_DOOR = "azure_front_door"
    AZURE_DEVOPS = "azure_devops"

    # =========================================================================
    # ORACLE CLOUD INFRASTRUCTURE
    # =========================================================================
    ORACLE_CLOUD_FUNCTIONS = "oracle_cloud_functions"
    ORACLE_CONTAINER_ENGINE = "oracle_container_engine"
    ORACLE_CONTAINER_INSTANCES = "oracle_container_instances"
    ORACLE_VM = "oracle_vm"
    ORACLE_AUTONOMOUS = "oracle_autonomous"
    ORACLE_APIGW = "oracle_apigw"
    ORACLE_EVENTS = "oracle_events"

    # =========================================================================
    # IBM CLOUD
    # =========================================================================
    IBM_CODE_ENGINE = "ibm_code_engine"
    IBM_CLOUD_FUNCTIONS = "ibm_cloud_functions"
    IBM_KUBERNETES = "ibm_kubernetes"
    IBM_OPENSHIFT = "ibm_openshift"
    IBM_VIRTUAL_SERVER = "ibm_virtual_server"
    IBM_SATELLITE = "ibm_satellite"

    # =========================================================================
    # ALIBABA CLOUD
    # =========================================================================
    ALIBABA_SERVERLESS = "alibaba_serverless"
    ALIBABA_CONTAINER_SERVICE = "alibaba_container_service"
    ALIBABA_ECS = "alibaba_ecs"
    ALIBABA_FUNCTION_COMPUTE = "alibaba_function_compute"
    ALIBABA_SAE = "alibaba_sae"

    # =========================================================================
    # TENCENT CLOUD
    # =========================================================================
    TENCENT_SCF = "tencent_scf"
    TENCENT_TKE = "tencent_tke"
    TENCENT_CVM = "tencent_cvm"
    TENCENT_LIGHTHOUSE = "tencent_lighthouse"
    TENCENT_CLOUDBASE = "tencent_cloudbase"

    # =========================================================================
    # YANDEX CLOUD
    # =========================================================================
    YANDEX_SERVERLESS = "yandex_serverless"
    YANDEX_KUBERNETES = "yandex_kubernetes"
    YANDEX_COMPUTE = "yandex_compute"
    YANDEX_CONTAINER_REGISTRY = "yandex_container_registry"

    # =========================================================================
    # EUROPEAN CLOUD PROVIDERS
    # =========================================================================
    OVH_CLOUD = "ovh_cloud"
    OVH_MANAGED_KUBERNETES = "ovh_managed_kubernetes"
    SCALEWAY = "scaleway"
    SCALEWAY_SERVERLESS = "scaleway_serverless"
    SCALEWAY_KUBERNETES = "scaleway_kubernetes"
    EXOSCALE = "exoscale"
    EXOSCALE_SKS = "exoscale_sks"
    UPCLOUD = "upcloud"
    GLESYS = "glesys"
    CITYCLOUD = "citycloud"
    IONOS = "ionos"
    IONOS_KUBERNETES = "ionos_kubernetes"
    T_SYSTEMS = "t_systems"
    ORANGE_CLOUD = "orange_cloud"
    OUTSCALE = "outscale"
    CLEURA = "cleura"
    FUGA_CLOUD = "fuga_cloud"
    GRIDSCALE = "gridscale"
    INFOMANIAK = "infomaniak"
    CIVO = "civo"

    # =========================================================================
    # DIGITALOCEAN
    # =========================================================================
    DIGITALOCEAN_APP_PLATFORM = "digitalocean_app_platform"
    DIGITALOCEAN_KUBERNETES = "digitalocean_kubernetes"
    DIGITALOCEAN_DROPLET = "digitalocean_droplet"
    DIGITALOCEAN_FUNCTIONS = "digitalocean_functions"
    DIGITALOCEAN_SPACES = "digitalocean_spaces"

    # =========================================================================
    # CLOUDFLARE
    # =========================================================================
    CLOUDFLARE_WORKERS = "cloudflare_workers"
    CLOUDFLARE_PAGES = "cloudflare_pages"
    CLOUDFLARE_R2 = "cloudflare_r2"
    CLOUDFLARE_D1 = "cloudflare_d1"
    CLOUDFLARE_KV = "cloudflare_kv"
    CLOUDFLARE_QUEUES = "cloudflare_queues"
    CLOUDFLARE_HYPERDRIVE = "cloudflare_hyperdrive"
    CLOUDFLARE_DURABLE_OBJECTS = "cloudflare_durable_objects"
    CLOUDFLARE_WORKFLOWS = "cloudflare_workflows"

    # =========================================================================
    # EDGE/CDN PLATFORMS
    # =========================================================================
    FASTLY_COMPUTE = "fastly_compute"
    AKAMAI_EDGEWORKERS = "akamai_edgeworkers"
    AKAMAI_EDGEKV = "akamai_edgekv"
    BUNNY_CDN = "bunny_cdn"
    BUNNY_EDGE_SCRIPTING = "bunny_edge_scripting"
    KEYCDN = "keycdn"
    STACKPATH = "stackpath"
    LIMELIGHT = "limelight"
    SECTION_IO = "section_io"

    # =========================================================================
    # VPS / BARE METAL PROVIDERS
    # =========================================================================
    LINODE = "linode"
    LINODE_KUBERNETES = "linode_kubernetes"
    VULTR = "vultr"
    VULTR_KUBERNETES = "vultr_kubernetes"
    HETZNER = "hetzner"
    HETZNER_CLOUD = "hetzner_cloud"
    ATLANTIC_NET = "atlantic_net"
    KAMATERA = "kamatera"
    HOSTINGER = "hostinger"
    CONTABO = "contabo"
    VULTRVPS = "vultrvps"
    INTERSERVER = "interserver"
    HOSTWINDS = "hostwinds"
    A2_HOSTING = "a2_hosting"
    DREAMHOST = "dreamhost"
    SITEGROUND = "siteground"
    BLUEHOST = "bluehost"
    GODADDY = "godaddy"
    NAMECHEAP = "namecheap"
    PACKET = "packet"
    EQUINIX_METAL = "equinix_metal"
    PHOENIXNAP = "phoenixnap"
    CHERRY_SERVERS = "cherry_servers"
    WEBDOCK = "webdock"
    TIME4VPS = "time4vps"
    NETCUP = "netcup"
    STRATO = "strato"

    # =========================================================================
    # STATIC HOSTING
    # =========================================================================
    GITHUB_PAGES = "github_pages"
    GITLAB_PAGES = "gitlab_pages"
    BITBUCKET_PAGES = "bitbucket_pages"
    SURGE = "surge"
    NEOCITIES = "neocities"
    NETLIFY_DROP = "netlify_drop"
    TIINY_HOST = "tiiny_host"
    STATIC_LAND = "static_land"
    STORMKIT = "stormkit"
    KINSTA_STATIC = "kinsta_static"
    HOSTMAN = "hostman"

    # =========================================================================
    # DEVELOPER CLOUD IDES / SANDBOXES
    # =========================================================================
    REPLIT = "replit"
    GLITCH = "glitch"
    CODESANDBOX = "codesandbox"
    STACKBLITZ = "stackblitz"
    GITPOD = "gitpod"
    GITHUB_CODESPACES = "github_codespaces"
    CODER = "coder"
    DEVPOD = "devpod"
    CODEANYWHERE = "codeanywhere"
    GOORM = "goorm"
    PAIZA_CLOUD = "paiza_cloud"

    # =========================================================================
    # LANGUAGE-SPECIFIC PLATFORMS
    # =========================================================================
    # Python
    PYTHONANYWHERE = "pythonanywhere"
    STREAMLIT_CLOUD = "streamlit_cloud"
    HUGGING_FACE_SPACES = "hugging_face_spaces"
    GRADIO_SPACES = "gradio_spaces"
    MODAL = "modal"
    BANANA_DEV = "banana_dev"
    REPLICATE = "replicate"

    # Node.js / JavaScript
    GLITCH_NODE = "glitch_node"

    # PHP
    SERVEBOLT = "servebolt"
    CLOUDWAYS = "cloudways"
    RUNCLOUD = "runcloud"
    SPINUPWP = "spinupwp"
    GRIDPANE = "gridpane"
    PLOI = "ploi"
    FORGE = "forge"
    VAPOR = "vapor"

    # Ruby
    HEROKU_RUBY = "heroku_ruby"
    RENDER_RUBY = "render_ruby"

    # Java / JVM
    PIVOTAL_CLOUD_FOUNDRY = "pivotal_cloud_foundry"
    SPRING_CLOUD = "spring_cloud"

    # .NET
    AZURE_DOTNET = "azure_dotnet"

    # WordPress
    WPENGINE = "wpengine"
    KINSTA_WORDPRESS = "kinsta_wordpress"
    FLYWHEEL = "flywheel"
    PANTHEON = "pantheon"
    WORDPRESS_VIP = "wordpress_vip"

    # =========================================================================
    # CONTAINER ORCHESTRATION
    # =========================================================================
    KUBERNETES = "kubernetes"
    DOCKER = "docker"
    DOCKER_SWARM = "docker_swarm"
    NOMAD = "nomad"
    PODMAN = "podman"
    RANCHER = "rancher"
    OPENSHIFT = "openshift"
    TANZU = "tanzu"
    ANTHOS = "anthos"
    EKS_ANYWHERE = "eks_anywhere"
    AKS_HYBRID = "aks_hybrid"
    K0S = "k0s"
    K3S = "k3s"
    MICROK8S = "microk8s"
    MINIKUBE = "minikube"
    KIND = "kind"

    # =========================================================================
    # SELF-HOSTED PAAS
    # =========================================================================
    COOLIFY = "coolify"
    DOKKU = "dokku"
    CAPROVER = "caprover"
    PORTER = "porter"
    KUBERO = "kubero"
    PIKU = "piku"
    FLYNN = "flynn"
    TSURU = "tsuru"
    DEIS = "deis"
    EPINIO = "epinio"
    ACORN = "acorn"
    KNATIVE = "knative"
    OPENFAAS = "openfaas"
    FISSION = "fission"
    KUBELESS = "kubeless"
    NUCLIO = "nuclio"
    OPENWHISK = "openwhisk"
    FN_PROJECT = "fn_project"
    IRON_FUNCTIONS = "iron_functions"
    SEALOS = "sealos"
    RAINBOND = "rainbond"
    OPENFUNCTION = "openfunction"

    # =========================================================================
    # GAMESERVER / SPECIALIZED
    # =========================================================================
    GAMESERVERKINGS = "gameserverkings"
    NODECRAFT = "nodecraft"
    SHOCKBYTE = "shockbyte"
    BISECTHOSTING = "bisecthosting"
    APEX_HOSTING = "apex_hosting"
    HOSTPAPA = "hostpapa"
    MCPROHOSTING = "mcprohosting"

    # =========================================================================
    # IOT / EMBEDDED
    # =========================================================================
    AWS_IOT_GREENGRASS = "aws_iot_greengrass"
    AZURE_IOT_EDGE = "azure_iot_edge"
    GCP_IOT_CORE = "gcp_iot_core"
    BALENA = "balena"
    PARTICLE = "particle"
    RESIN = "resin"

    # =========================================================================
    # ML/AI PLATFORMS
    # =========================================================================
    SAGEMAKER = "sagemaker"
    VERTEX_AI = "vertex_ai"
    AZURE_ML = "azure_ml"
    DATABRICKS = "databricks"
    PAPERSPACE = "paperspace"
    LAMBDALABS = "lambdalabs"
    COREWEAVE = "coreweave"
    RUNPOD = "runpod"
    VAST_AI = "vast_ai"
    TOGETHER_AI = "together_ai"
    ANYSCALE = "anyscale"
    MOSAIC_ML = "mosaic_ml"
    LIGHTNING_AI = "lightning_ai"


class DeploymentStatus(Enum):
    """Deployment status states."""

    PENDING = "pending"
    BUILDING = "building"
    DEPLOYING = "deploying"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLING_BACK = "rolling_back"


@dataclass
class DeploymentConfig:
    """Configuration for a deployment."""

    platform: DeploymentPlatform
    workspace_path: str
    environment: str = "production"
    branch: Optional[str] = None
    env_vars: Dict[str, str] = field(default_factory=dict)
    build_command: Optional[str] = None
    output_directory: Optional[str] = None
    region: Optional[str] = None
    instance_count: int = 1
    dry_run: bool = False


@dataclass
class DeploymentResult:
    """Result of a deployment operation."""

    success: bool
    platform: DeploymentPlatform
    status: DeploymentStatus
    deployment_id: Optional[str] = None
    deployment_url: Optional[str] = None
    build_logs: List[str] = field(default_factory=list)
    deploy_logs: List[str] = field(default_factory=list)
    error: Optional[str] = None
    duration_seconds: float = 0.0
    rollback_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class DeploymentExecutorService:
    """
    Service for executing real deployments to various platforms.

    This service:
    1. Validates prerequisites (CLI tools, credentials)
    2. Executes deployments with real-time streaming
    3. Handles rollbacks
    4. Tracks deployment history
    """

    def __init__(self):
        self._deployment_history: List[DeploymentResult] = []
        self._active_deployments: Dict[str, DeploymentResult] = {}

    async def check_prerequisites(
        self, platform: DeploymentPlatform
    ) -> Tuple[bool, str]:
        """
        Check if all prerequisites are met for deploying to a platform.

        Returns:
            Tuple of (success, message)
        """
        checks = {
            DeploymentPlatform.VERCEL: self._check_vercel,
            DeploymentPlatform.RAILWAY: self._check_railway,
            DeploymentPlatform.FLY: self._check_fly,
            DeploymentPlatform.NETLIFY: self._check_netlify,
            DeploymentPlatform.HEROKU: self._check_heroku,
            DeploymentPlatform.KUBERNETES: self._check_kubernetes,
            DeploymentPlatform.AWS_ECS: self._check_aws,
            DeploymentPlatform.AWS_LAMBDA: self._check_aws,
            DeploymentPlatform.GCP_CLOUD_RUN: self._check_gcp,
            DeploymentPlatform.GCP_APP_ENGINE: self._check_gcp,
            DeploymentPlatform.AZURE_APP_SERVICE: self._check_azure,
            DeploymentPlatform.DOCKER: self._check_docker,
        }

        checker = checks.get(platform)
        if checker:
            return await checker()
        return False, f"Platform {platform.value} not supported"

    async def execute_deployment(
        self,
        config: DeploymentConfig,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> DeploymentResult:
        """
        Execute a deployment to the specified platform.

        Args:
            config: Deployment configuration
            progress_callback: Optional callback for progress updates (message, percentage)

        Returns:
            DeploymentResult with deployment outcome
        """
        result = DeploymentResult(
            success=False,
            platform=config.platform,
            status=DeploymentStatus.PENDING,
            started_at=datetime.utcnow(),
        )

        # Check prerequisites
        prereq_ok, prereq_msg = await self.check_prerequisites(config.platform)
        if not prereq_ok:
            result.status = DeploymentStatus.FAILED
            result.error = f"Prerequisites not met: {prereq_msg}"
            return result

        # Execute platform-specific deployment
        executors = {
            DeploymentPlatform.VERCEL: self._deploy_vercel,
            DeploymentPlatform.RAILWAY: self._deploy_railway,
            DeploymentPlatform.FLY: self._deploy_fly,
            DeploymentPlatform.NETLIFY: self._deploy_netlify,
            DeploymentPlatform.HEROKU: self._deploy_heroku,
            DeploymentPlatform.KUBERNETES: self._deploy_kubernetes,
            DeploymentPlatform.AWS_ECS: self._deploy_aws_ecs,
            DeploymentPlatform.AWS_LAMBDA: self._deploy_aws_lambda,
            DeploymentPlatform.GCP_CLOUD_RUN: self._deploy_gcp_cloud_run,
            DeploymentPlatform.DOCKER: self._deploy_docker,
        }

        executor = executors.get(config.platform)
        if not executor:
            result.status = DeploymentStatus.FAILED
            result.error = f"Platform {config.platform.value} executor not implemented"
            return result

        try:
            if progress_callback:
                progress_callback(
                    f"Starting deployment to {config.platform.value}...", 0
                )

            result = await executor(config, result, progress_callback)

            result.completed_at = datetime.utcnow()
            if result.started_at:
                result.duration_seconds = (
                    result.completed_at - result.started_at
                ).total_seconds()

            # Store in history
            self._deployment_history.append(result)

            return result

        except Exception as e:
            logger.error("Deployment failed: %s", str(e))
            result.status = DeploymentStatus.FAILED
            result.error = str(e)
            result.completed_at = datetime.utcnow()
            return result

    async def rollback_deployment(
        self,
        platform: DeploymentPlatform,
        deployment_id: str,
        workspace_path: str,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> DeploymentResult:
        """Rollback to a previous deployment."""
        result = DeploymentResult(
            success=False,
            platform=platform,
            status=DeploymentStatus.ROLLING_BACK,
            started_at=datetime.utcnow(),
        )

        try:
            if platform == DeploymentPlatform.VERCEL:
                result = await self._rollback_vercel(
                    deployment_id, result, progress_callback
                )
            elif platform == DeploymentPlatform.RAILWAY:
                result = await self._rollback_railway(
                    deployment_id, result, progress_callback
                )
            elif platform == DeploymentPlatform.FLY:
                result = await self._rollback_fly(
                    deployment_id, workspace_path, result, progress_callback
                )
            elif platform == DeploymentPlatform.KUBERNETES:
                result = await self._rollback_kubernetes(
                    deployment_id, workspace_path, result, progress_callback
                )
            else:
                result.error = f"Rollback not supported for {platform.value}"
                result.status = DeploymentStatus.FAILED

            result.completed_at = datetime.utcnow()
            return result

        except Exception as e:
            logger.error("Rollback failed: %s", str(e))
            result.status = DeploymentStatus.FAILED
            result.error = str(e)
            return result

    async def get_deployment_status(
        self,
        platform: DeploymentPlatform,
        deployment_id: str,
    ) -> Dict[str, Any]:
        """Get the status of a deployment."""
        if platform == DeploymentPlatform.VERCEL:
            return await self._get_vercel_status(deployment_id)
        elif platform == DeploymentPlatform.RAILWAY:
            return await self._get_railway_status(deployment_id)
        elif platform == DeploymentPlatform.FLY:
            return await self._get_fly_status(deployment_id)
        return {"status": "unknown", "error": "Platform not supported"}

    # -------------------------------------------------------------------------
    # Prerequisite Checks
    # -------------------------------------------------------------------------

    async def _check_vercel(self) -> Tuple[bool, str]:
        """Check Vercel CLI and authentication."""
        if not shutil.which("vercel"):
            return False, "Vercel CLI not installed. Run: npm i -g vercel"

        try:
            result = await self._run_command(["vercel", "whoami"])
            if result["returncode"] == 0:
                return True, f"Authenticated as: {result['stdout'].strip()}"
            return False, "Not authenticated. Run: vercel login"
        except Exception as e:
            return False, f"Failed to check Vercel auth: {e}"

    async def _check_railway(self) -> Tuple[bool, str]:
        """Check Railway CLI and authentication."""
        if not shutil.which("railway"):
            return False, "Railway CLI not installed. Run: npm i -g @railway/cli"

        try:
            result = await self._run_command(["railway", "whoami"])
            if result["returncode"] == 0:
                return True, f"Authenticated: {result['stdout'].strip()}"
            return False, "Not authenticated. Run: railway login"
        except Exception as e:
            return False, f"Failed to check Railway auth: {e}"

    async def _check_fly(self) -> Tuple[bool, str]:
        """Check Fly.io CLI and authentication."""
        if not shutil.which("fly") and not shutil.which("flyctl"):
            return (
                False,
                "Fly CLI not installed. Run: curl -L https://fly.io/install.sh | sh",
            )

        try:
            cmd = "fly" if shutil.which("fly") else "flyctl"
            result = await self._run_command([cmd, "auth", "whoami"])
            if result["returncode"] == 0:
                return True, f"Authenticated: {result['stdout'].strip()}"
            return False, "Not authenticated. Run: fly auth login"
        except Exception as e:
            return False, f"Failed to check Fly auth: {e}"

    async def _check_netlify(self) -> Tuple[bool, str]:
        """Check Netlify CLI and authentication."""
        if not shutil.which("netlify"):
            return False, "Netlify CLI not installed. Run: npm i -g netlify-cli"

        try:
            result = await self._run_command(["netlify", "status"])
            if "Logged in" in result["stdout"]:
                return True, "Authenticated with Netlify"
            return False, "Not authenticated. Run: netlify login"
        except Exception as e:
            return False, f"Failed to check Netlify auth: {e}"

    async def _check_heroku(self) -> Tuple[bool, str]:
        """Check Heroku CLI and authentication."""
        if not shutil.which("heroku"):
            return (
                False,
                "Heroku CLI not installed. See: https://devcenter.heroku.com/articles/heroku-cli",
            )

        try:
            result = await self._run_command(["heroku", "auth:whoami"])
            if result["returncode"] == 0:
                return True, f"Authenticated as: {result['stdout'].strip()}"
            return False, "Not authenticated. Run: heroku login"
        except Exception as e:
            return False, f"Failed to check Heroku auth: {e}"

    async def _check_kubernetes(self) -> Tuple[bool, str]:
        """Check kubectl and cluster connection."""
        if not shutil.which("kubectl"):
            return False, "kubectl not installed"

        try:
            result = await self._run_command(["kubectl", "cluster-info"])
            if result["returncode"] == 0:
                return True, "Connected to Kubernetes cluster"
            return False, "Cannot connect to cluster. Check your kubeconfig"
        except Exception as e:
            return False, f"Failed to check Kubernetes: {e}"

    async def _check_aws(self) -> Tuple[bool, str]:
        """Check AWS CLI and credentials."""
        if not shutil.which("aws"):
            return False, "AWS CLI not installed"

        try:
            result = await self._run_command(["aws", "sts", "get-caller-identity"])
            if result["returncode"] == 0:
                identity = json.loads(result["stdout"])
                return True, f"Authenticated as: {identity.get('Arn', 'unknown')}"
            return False, "AWS credentials not configured"
        except Exception as e:
            return False, f"Failed to check AWS auth: {e}"

    async def _check_gcp(self) -> Tuple[bool, str]:
        """Check gcloud CLI and authentication."""
        if not shutil.which("gcloud"):
            return False, "gcloud CLI not installed"

        try:
            result = await self._run_command(
                ["gcloud", "auth", "list", "--format=json"]
            )
            if result["returncode"] == 0:
                accounts = json.loads(result["stdout"])
                active = [a for a in accounts if a.get("status") == "ACTIVE"]
                if active:
                    return (
                        True,
                        f"Authenticated as: {active[0].get('account', 'unknown')}",
                    )
            return False, "Not authenticated. Run: gcloud auth login"
        except Exception as e:
            return False, f"Failed to check GCP auth: {e}"

    async def _check_azure(self) -> Tuple[bool, str]:
        """Check Azure CLI and authentication."""
        if not shutil.which("az"):
            return False, "Azure CLI not installed"

        try:
            result = await self._run_command(["az", "account", "show"])
            if result["returncode"] == 0:
                account = json.loads(result["stdout"])
                return True, f"Authenticated: {account.get('name', 'unknown')}"
            return False, "Not authenticated. Run: az login"
        except Exception as e:
            return False, f"Failed to check Azure auth: {e}"

    async def _check_docker(self) -> Tuple[bool, str]:
        """Check Docker daemon."""
        if not shutil.which("docker"):
            return False, "Docker not installed"

        try:
            result = await self._run_command(["docker", "info"])
            if result["returncode"] == 0:
                return True, "Docker daemon running"
            return False, "Docker daemon not running"
        except Exception as e:
            return False, f"Failed to check Docker: {e}"

    # -------------------------------------------------------------------------
    # Platform-Specific Deployments
    # -------------------------------------------------------------------------

    async def _deploy_vercel(
        self,
        config: DeploymentConfig,
        result: DeploymentResult,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DeploymentResult:
        """Deploy to Vercel."""
        result.status = DeploymentStatus.BUILDING

        cmd = ["vercel", "--yes"]

        if config.environment == "production":
            cmd.append("--prod")

        if config.dry_run:
            cmd.append("--dry-run")

        # Add environment variables
        for key, value in config.env_vars.items():
            cmd.extend(["--env", f"{key}={value}"])

        if progress_callback:
            progress_callback("Building and deploying to Vercel...", 20)

        output = await self._run_command_streaming(
            cmd,
            cwd=config.workspace_path,
            progress_callback=progress_callback,
        )

        result.build_logs = output["logs"]
        result.deploy_logs = output["logs"]

        if output["returncode"] == 0:
            result.status = DeploymentStatus.SUCCESS
            result.success = True

            # Extract deployment URL from output
            url_match = re.search(r"https://[^\s]+\.vercel\.app", output["stdout"])
            if url_match:
                result.deployment_url = url_match.group(0)

            # Extract deployment ID
            id_match = re.search(r"Deployment ID: ([a-zA-Z0-9]+)", output["stdout"])
            if id_match:
                result.deployment_id = id_match.group(1)
                result.rollback_id = id_match.group(1)

            if progress_callback:
                progress_callback(
                    f"Deployed successfully: {result.deployment_url}", 100
                )
        else:
            result.status = DeploymentStatus.FAILED
            result.error = output["stderr"] or "Deployment failed"

        return result

    async def _deploy_railway(
        self,
        config: DeploymentConfig,
        result: DeploymentResult,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DeploymentResult:
        """Deploy to Railway."""
        result.status = DeploymentStatus.BUILDING

        cmd = ["railway", "up", "--detach"]

        if config.environment:
            cmd.extend(["--environment", config.environment])

        if progress_callback:
            progress_callback("Deploying to Railway...", 20)

        output = await self._run_command_streaming(
            cmd,
            cwd=config.workspace_path,
            progress_callback=progress_callback,
        )

        result.deploy_logs = output["logs"]

        if output["returncode"] == 0:
            result.status = DeploymentStatus.SUCCESS
            result.success = True

            # Get deployment URL
            url_result = await self._run_command(
                ["railway", "domain"], cwd=config.workspace_path
            )
            if url_result["returncode"] == 0:
                result.deployment_url = url_result["stdout"].strip()

            if progress_callback:
                progress_callback(
                    f"Deployed successfully: {result.deployment_url}", 100
                )
        else:
            result.status = DeploymentStatus.FAILED
            result.error = output["stderr"] or "Deployment failed"

        return result

    async def _deploy_fly(
        self,
        config: DeploymentConfig,
        result: DeploymentResult,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DeploymentResult:
        """Deploy to Fly.io."""
        result.status = DeploymentStatus.BUILDING

        cmd_name = "fly" if shutil.which("fly") else "flyctl"
        cmd = [cmd_name, "deploy"]

        if config.region:
            cmd.extend(["--region", config.region])

        if config.dry_run:
            cmd.append("--dry-run")

        if progress_callback:
            progress_callback("Building and deploying to Fly.io...", 20)

        output = await self._run_command_streaming(
            cmd,
            cwd=config.workspace_path,
            progress_callback=progress_callback,
        )

        result.build_logs = output["logs"]
        result.deploy_logs = output["logs"]

        if output["returncode"] == 0:
            result.status = DeploymentStatus.SUCCESS
            result.success = True

            # Extract app URL
            url_match = re.search(r"(https://[^\s]+\.fly\.dev)", output["stdout"])
            if url_match:
                result.deployment_url = url_match.group(1)

            if progress_callback:
                progress_callback(
                    f"Deployed successfully: {result.deployment_url}", 100
                )
        else:
            result.status = DeploymentStatus.FAILED
            result.error = output["stderr"] or "Deployment failed"

        return result

    async def _deploy_netlify(
        self,
        config: DeploymentConfig,
        result: DeploymentResult,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DeploymentResult:
        """Deploy to Netlify."""
        result.status = DeploymentStatus.BUILDING

        cmd = ["netlify", "deploy"]

        if config.environment == "production":
            cmd.append("--prod")

        if config.output_directory:
            cmd.extend(["--dir", config.output_directory])

        if progress_callback:
            progress_callback("Deploying to Netlify...", 20)

        output = await self._run_command_streaming(
            cmd,
            cwd=config.workspace_path,
            progress_callback=progress_callback,
        )

        result.deploy_logs = output["logs"]

        if output["returncode"] == 0:
            result.status = DeploymentStatus.SUCCESS
            result.success = True

            # Extract URLs
            url_match = re.search(r"Website URL:\s*(https://[^\s]+)", output["stdout"])
            if url_match:
                result.deployment_url = url_match.group(1)

            if progress_callback:
                progress_callback(
                    f"Deployed successfully: {result.deployment_url}", 100
                )
        else:
            result.status = DeploymentStatus.FAILED
            result.error = output["stderr"] or "Deployment failed"

        return result

    async def _deploy_heroku(
        self,
        config: DeploymentConfig,
        result: DeploymentResult,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DeploymentResult:
        """Deploy to Heroku."""
        result.status = DeploymentStatus.BUILDING

        if progress_callback:
            progress_callback("Pushing to Heroku...", 20)

        # Heroku deploys via git push
        cmd = ["git", "push", "heroku", f"{config.branch or 'main'}:main", "--force"]

        output = await self._run_command_streaming(
            cmd,
            cwd=config.workspace_path,
            progress_callback=progress_callback,
        )

        result.build_logs = output["logs"]
        result.deploy_logs = output["logs"]

        if output["returncode"] == 0:
            result.status = DeploymentStatus.SUCCESS
            result.success = True

            # Get app URL
            app_result = await self._run_command(
                ["heroku", "apps:info", "--json"], cwd=config.workspace_path
            )
            if app_result["returncode"] == 0:
                app_info = json.loads(app_result["stdout"])
                result.deployment_url = app_info.get("web_url")

            if progress_callback:
                progress_callback(
                    f"Deployed successfully: {result.deployment_url}", 100
                )
        else:
            result.status = DeploymentStatus.FAILED
            result.error = output["stderr"] or "Deployment failed"

        return result

    async def _deploy_kubernetes(
        self,
        config: DeploymentConfig,
        result: DeploymentResult,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DeploymentResult:
        """Deploy to Kubernetes."""
        result.status = DeploymentStatus.DEPLOYING

        if progress_callback:
            progress_callback("Applying Kubernetes manifests...", 20)

        # Find and apply all YAML files
        k8s_dir = Path(config.workspace_path) / "k8s"
        if not k8s_dir.exists():
            k8s_dir = Path(config.workspace_path) / "kubernetes"

        if not k8s_dir.exists():
            result.status = DeploymentStatus.FAILED
            result.error = "No k8s or kubernetes directory found"
            return result

        cmd = ["kubectl", "apply", "-f", str(k8s_dir), "--recursive"]

        if config.dry_run:
            cmd.append("--dry-run=client")

        output = await self._run_command_streaming(
            cmd,
            cwd=config.workspace_path,
            progress_callback=progress_callback,
        )

        result.deploy_logs = output["logs"]

        if output["returncode"] == 0:
            if progress_callback:
                progress_callback("Waiting for rollout to complete...", 60)

            # Wait for deployment rollout
            rollout_cmd = [
                "kubectl",
                "rollout",
                "status",
                "deployment",
                "--timeout=300s",
            ]
            rollout_output = await self._run_command(
                rollout_cmd, cwd=config.workspace_path
            )

            if rollout_output["returncode"] == 0:
                result.status = DeploymentStatus.SUCCESS
                result.success = True

                # Get service URL if LoadBalancer
                svc_result = await self._run_command(
                    ["kubectl", "get", "svc", "-o", "json"], cwd=config.workspace_path
                )
                if svc_result["returncode"] == 0:
                    services = json.loads(svc_result["stdout"])
                    for svc in services.get("items", []):
                        if svc.get("spec", {}).get("type") == "LoadBalancer":
                            ingress = (
                                svc.get("status", {})
                                .get("loadBalancer", {})
                                .get("ingress", [])
                            )
                            if ingress:
                                ip = ingress[0].get("ip") or ingress[0].get("hostname")
                                port = svc["spec"]["ports"][0]["port"]
                                result.deployment_url = f"http://{ip}:{port}"
                                break

                if progress_callback:
                    progress_callback(
                        f"Deployed successfully: {result.deployment_url or 'Check kubectl get svc'}",
                        100,
                    )
            else:
                result.status = DeploymentStatus.FAILED
                result.error = rollout_output["stderr"] or "Rollout failed"
        else:
            result.status = DeploymentStatus.FAILED
            result.error = output["stderr"] or "kubectl apply failed"

        return result

    async def _deploy_aws_ecs(
        self,
        config: DeploymentConfig,
        result: DeploymentResult,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DeploymentResult:
        """Deploy to AWS ECS."""
        result.status = DeploymentStatus.BUILDING

        if progress_callback:
            progress_callback("Building Docker image...", 10)

        # Build Docker image
        image_name = f"{config.workspace_path.split('/')[-1]}:latest"
        build_output = await self._run_command(
            ["docker", "build", "-t", image_name, "."], cwd=config.workspace_path
        )

        if build_output["returncode"] != 0:
            result.status = DeploymentStatus.FAILED
            result.error = "Docker build failed"
            return result

        result.build_logs.append(build_output["stdout"])

        if progress_callback:
            progress_callback("Pushing to ECR...", 40)

        # Get ECR login
        ecr_login = await self._run_command(
            [
                "aws",
                "ecr",
                "get-login-password",
                "--region",
                config.region or "us-east-1",
            ]
        )

        if ecr_login["returncode"] != 0:
            result.status = DeploymentStatus.FAILED
            result.error = "Failed to get ECR login"
            return result

        # Tag and push to ECR (assuming ECR repo exists)
        account_id = (
            await self._run_command(
                [
                    "aws",
                    "sts",
                    "get-caller-identity",
                    "--query",
                    "Account",
                    "--output",
                    "text",
                ]
            )
        )["stdout"].strip()
        region = config.region or "us-east-1"
        ecr_repo = f"{account_id}.dkr.ecr.{region}.amazonaws.com/{image_name}"

        # Docker login to ECR
        await self._run_command(
            [
                "docker",
                "login",
                "--username",
                "AWS",
                "--password-stdin",
                f"{account_id}.dkr.ecr.{region}.amazonaws.com",
            ],
            input_data=ecr_login["stdout"],
        )

        # Tag and push
        await self._run_command(["docker", "tag", image_name, ecr_repo])
        push_output = await self._run_command(["docker", "push", ecr_repo])

        if push_output["returncode"] != 0:
            result.status = DeploymentStatus.FAILED
            result.error = "Failed to push to ECR"
            return result

        if progress_callback:
            progress_callback("Updating ECS service...", 70)

        # Update ECS service
        # This assumes a service and task definition already exist
        cluster_name = config.env_vars.get("ECS_CLUSTER", "default")
        service_name = config.env_vars.get("ECS_SERVICE", image_name.split(":")[0])

        update_output = await self._run_command(
            [
                "aws",
                "ecs",
                "update-service",
                "--cluster",
                cluster_name,
                "--service",
                service_name,
                "--force-new-deployment",
                "--region",
                region,
            ]
        )

        if update_output["returncode"] == 0:
            result.status = DeploymentStatus.SUCCESS
            result.success = True
            result.deployment_url = f"Check AWS Console for ECS service: {service_name}"

            if progress_callback:
                progress_callback("ECS deployment initiated successfully", 100)
        else:
            result.status = DeploymentStatus.FAILED
            result.error = update_output["stderr"] or "ECS update failed"

        return result

    async def _deploy_aws_lambda(
        self,
        config: DeploymentConfig,
        result: DeploymentResult,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DeploymentResult:
        """Deploy to AWS Lambda."""
        result.status = DeploymentStatus.BUILDING

        if progress_callback:
            progress_callback("Packaging Lambda function...", 20)

        # Create deployment package
        function_name = config.env_vars.get("LAMBDA_FUNCTION", "navi-function")
        zip_path = f"/tmp/{function_name}.zip"

        # Zip the workspace
        import zipfile

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            workspace = Path(config.workspace_path)
            for file in workspace.rglob("*"):
                if file.is_file() and not any(
                    p in str(file) for p in ["node_modules", ".git", "__pycache__"]
                ):
                    zipf.write(file, file.relative_to(workspace))

        if progress_callback:
            progress_callback("Deploying to Lambda...", 60)

        # Update Lambda function
        region = config.region or "us-east-1"
        update_output = await self._run_command(
            [
                "aws",
                "lambda",
                "update-function-code",
                "--function-name",
                function_name,
                "--zip-file",
                f"fileb://{zip_path}",
                "--region",
                region,
            ]
        )

        if update_output["returncode"] == 0:
            result.status = DeploymentStatus.SUCCESS
            result.success = True
            lambda_info = json.loads(update_output["stdout"])
            result.deployment_id = lambda_info.get("FunctionArn")
            result.deployment_url = (
                f"arn:aws:lambda:{region}:*:function:{function_name}"
            )

            if progress_callback:
                progress_callback("Lambda deployed successfully", 100)
        else:
            result.status = DeploymentStatus.FAILED
            result.error = update_output["stderr"] or "Lambda update failed"

        # Cleanup
        os.remove(zip_path)

        return result

    async def _deploy_gcp_cloud_run(
        self,
        config: DeploymentConfig,
        result: DeploymentResult,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DeploymentResult:
        """Deploy to Google Cloud Run."""
        result.status = DeploymentStatus.BUILDING

        service_name = config.env_vars.get(
            "SERVICE_NAME", config.workspace_path.split("/")[-1]
        )
        region = config.region or "us-central1"

        if progress_callback:
            progress_callback("Deploying to Cloud Run...", 20)

        cmd = [
            "gcloud",
            "run",
            "deploy",
            service_name,
            "--source",
            ".",
            "--region",
            region,
            "--allow-unauthenticated",
            "--quiet",
        ]

        output = await self._run_command_streaming(
            cmd,
            cwd=config.workspace_path,
            progress_callback=progress_callback,
        )

        result.build_logs = output["logs"]
        result.deploy_logs = output["logs"]

        if output["returncode"] == 0:
            result.status = DeploymentStatus.SUCCESS
            result.success = True

            # Extract service URL
            url_match = re.search(r"Service URL: (https://[^\s]+)", output["stdout"])
            if url_match:
                result.deployment_url = url_match.group(1)

            if progress_callback:
                progress_callback(
                    f"Deployed successfully: {result.deployment_url}", 100
                )
        else:
            result.status = DeploymentStatus.FAILED
            result.error = output["stderr"] or "Cloud Run deployment failed"

        return result

    async def _deploy_docker(
        self,
        config: DeploymentConfig,
        result: DeploymentResult,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DeploymentResult:
        """Build and run Docker container locally."""
        result.status = DeploymentStatus.BUILDING

        image_name = config.workspace_path.split("/")[-1].lower()

        if progress_callback:
            progress_callback("Building Docker image...", 20)

        # Build
        build_output = await self._run_command_streaming(
            ["docker", "build", "-t", image_name, "."],
            cwd=config.workspace_path,
            progress_callback=progress_callback,
        )

        result.build_logs = build_output["logs"]

        if build_output["returncode"] != 0:
            result.status = DeploymentStatus.FAILED
            result.error = "Docker build failed"
            return result

        if progress_callback:
            progress_callback("Starting container...", 80)

        # Run container
        port = config.env_vars.get("PORT", "3000")
        run_cmd = [
            "docker",
            "run",
            "-d",
            "-p",
            f"{port}:{port}",
            "--name",
            f"{image_name}-container",
        ]

        # Add environment variables
        for key, value in config.env_vars.items():
            run_cmd.extend(["-e", f"{key}={value}"])

        run_cmd.append(image_name)

        run_output = await self._run_command(run_cmd, cwd=config.workspace_path)

        if run_output["returncode"] == 0:
            result.status = DeploymentStatus.SUCCESS
            result.success = True
            result.deployment_id = run_output["stdout"].strip()[:12]  # Container ID
            result.deployment_url = f"http://localhost:{port}"

            if progress_callback:
                progress_callback(f"Container running at {result.deployment_url}", 100)
        else:
            result.status = DeploymentStatus.FAILED
            result.error = run_output["stderr"] or "Failed to start container"

        return result

    # -------------------------------------------------------------------------
    # Rollback Methods
    # -------------------------------------------------------------------------

    async def _rollback_vercel(
        self,
        deployment_id: str,
        result: DeploymentResult,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DeploymentResult:
        """Rollback Vercel deployment."""
        if progress_callback:
            progress_callback("Rolling back Vercel deployment...", 50)

        output = await self._run_command(["vercel", "rollback", deployment_id, "--yes"])

        if output["returncode"] == 0:
            result.status = DeploymentStatus.SUCCESS
            result.success = True
        else:
            result.status = DeploymentStatus.FAILED
            result.error = output["stderr"]

        return result

    async def _rollback_railway(
        self,
        deployment_id: str,
        result: DeploymentResult,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DeploymentResult:
        """Rollback Railway deployment."""
        if progress_callback:
            progress_callback("Rolling back Railway deployment...", 50)

        output = await self._run_command(["railway", "rollback", deployment_id])

        if output["returncode"] == 0:
            result.status = DeploymentStatus.SUCCESS
            result.success = True
        else:
            result.status = DeploymentStatus.FAILED
            result.error = output["stderr"]

        return result

    async def _rollback_fly(
        self,
        deployment_id: str,
        workspace_path: str,
        result: DeploymentResult,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DeploymentResult:
        """Rollback Fly.io deployment."""
        if progress_callback:
            progress_callback("Rolling back Fly deployment...", 50)

        cmd_name = "fly" if shutil.which("fly") else "flyctl"
        output = await self._run_command(
            [cmd_name, "releases", "rollback", deployment_id], cwd=workspace_path
        )

        if output["returncode"] == 0:
            result.status = DeploymentStatus.SUCCESS
            result.success = True
        else:
            result.status = DeploymentStatus.FAILED
            result.error = output["stderr"]

        return result

    async def _rollback_kubernetes(
        self,
        deployment_name: str,
        workspace_path: str,
        result: DeploymentResult,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DeploymentResult:
        """Rollback Kubernetes deployment."""
        if progress_callback:
            progress_callback("Rolling back Kubernetes deployment...", 50)

        output = await self._run_command(
            ["kubectl", "rollout", "undo", f"deployment/{deployment_name}"],
            cwd=workspace_path,
        )

        if output["returncode"] == 0:
            result.status = DeploymentStatus.SUCCESS
            result.success = True
        else:
            result.status = DeploymentStatus.FAILED
            result.error = output["stderr"]

        return result

    # -------------------------------------------------------------------------
    # Status Methods
    # -------------------------------------------------------------------------

    async def _get_vercel_status(self, deployment_id: str) -> Dict[str, Any]:
        """Get Vercel deployment status."""
        output = await self._run_command(["vercel", "inspect", deployment_id, "--json"])
        if output["returncode"] == 0:
            return json.loads(output["stdout"])
        return {"status": "error", "message": output["stderr"]}

    async def _get_railway_status(self, deployment_id: str) -> Dict[str, Any]:
        """Get Railway deployment status."""
        output = await self._run_command(["railway", "status", "--json"])
        if output["returncode"] == 0:
            return json.loads(output["stdout"])
        return {"status": "error", "message": output["stderr"]}

    async def _get_fly_status(self, app_name: str) -> Dict[str, Any]:
        """Get Fly.io deployment status."""
        cmd_name = "fly" if shutil.which("fly") else "flyctl"
        output = await self._run_command([cmd_name, "status", "--json"])
        if output["returncode"] == 0:
            return json.loads(output["stdout"])
        return {"status": "error", "message": output["stderr"]}

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    async def _run_command(
        self,
        cmd: List[str],
        cwd: Optional[str] = None,
        input_data: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run a command and return the result."""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE if input_data else None,
                cwd=cwd,
            )

            stdout, stderr = await process.communicate(
                input=input_data.encode() if input_data else None
            )

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
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
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
                        # Estimate progress based on common deployment messages
                        progress = 50  # Default middle progress
                        if "Building" in decoded or "build" in decoded.lower():
                            progress = 30
                        elif "Deploying" in decoded or "deploy" in decoded.lower():
                            progress = 60
                        elif "Success" in decoded or "Complete" in decoded:
                            progress = 90
                        progress_callback(decoded, progress)

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
    # Health Verification & Smoke Testing
    # -------------------------------------------------------------------------

    async def verify_deployment_health(
        self,
        url: str,
        health_endpoint: str = "/health",
        expected_status: int = 200,
        timeout_seconds: int = 60,
        retry_count: int = 10,
        retry_delay_seconds: int = 5,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> Dict[str, Any]:
        """
        Verify that a deployment is healthy by checking its health endpoint.

        Args:
            url: Base URL of the deployment
            health_endpoint: Health check endpoint path
            expected_status: Expected HTTP status code
            timeout_seconds: Total timeout for health check
            retry_count: Number of retries
            retry_delay_seconds: Delay between retries
            progress_callback: Progress callback

        Returns:
            Health check result with status, latency, and details
        """
        import aiohttp

        health_result = {
            "healthy": False,
            "url": url,
            "endpoint": health_endpoint,
            "attempts": 0,
            "latency_ms": 0,
            "status_code": None,
            "response_body": None,
            "error": None,
        }

        full_url = f"{url.rstrip('/')}{health_endpoint}"

        if progress_callback:
            progress_callback(f"Checking health at {full_url}...", 10)

        for attempt in range(retry_count):
            health_result["attempts"] = attempt + 1

            try:
                start_time = datetime.utcnow()

                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        full_url,
                        timeout=aiohttp.ClientTimeout(
                            total=timeout_seconds / retry_count
                        ),
                    ) as response:
                        latency = (
                            datetime.utcnow() - start_time
                        ).total_seconds() * 1000
                        health_result["latency_ms"] = latency
                        health_result["status_code"] = response.status

                        try:
                            body = await response.text()
                            health_result["response_body"] = body[:500]  # Limit size
                        except:
                            pass

                        if response.status == expected_status:
                            health_result["healthy"] = True
                            if progress_callback:
                                progress_callback(
                                    f"Health check passed (status: {response.status}, latency: {latency:.0f}ms)",
                                    100,
                                )
                            return health_result

            except asyncio.TimeoutError:
                health_result["error"] = "Timeout waiting for response"
            except aiohttp.ClientError as e:
                health_result["error"] = str(e)
            except Exception as e:
                health_result["error"] = str(e)

            if attempt < retry_count - 1:
                if progress_callback:
                    progress_callback(
                        f"Health check attempt {attempt + 1} failed, retrying...",
                        (attempt + 1) * 100 / retry_count,
                    )
                await asyncio.sleep(retry_delay_seconds)

        if progress_callback:
            progress_callback(f"Health check failed after {retry_count} attempts", 100)

        return health_result

    async def run_smoke_tests(
        self,
        url: str,
        smoke_tests: List[Dict[str, Any]],
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> Dict[str, Any]:
        """
        Run smoke tests against a deployment.

        Args:
            url: Base URL of the deployment
            smoke_tests: List of test configs:
                [
                    {"path": "/api/health", "method": "GET", "expected_status": 200},
                    {"path": "/api/products", "method": "GET", "expected_status": 200},
                    {"path": "/", "method": "GET", "expected_status": 200, "expected_body_contains": "Welcome"},
                ]
            progress_callback: Progress callback

        Returns:
            Smoke test results
        """
        import aiohttp

        results = {
            "passed": 0,
            "failed": 0,
            "total": len(smoke_tests),
            "tests": [],
            "all_passed": False,
        }

        if progress_callback:
            progress_callback("Running smoke tests...", 5)

        async with aiohttp.ClientSession() as session:
            for i, test in enumerate(smoke_tests):
                test_result = {
                    "path": test.get("path", "/"),
                    "method": test.get("method", "GET"),
                    "passed": False,
                    "status_code": None,
                    "error": None,
                    "latency_ms": 0,
                }

                full_url = f"{url.rstrip('/')}{test['path']}"
                expected_status = test.get("expected_status", 200)

                try:
                    start_time = datetime.utcnow()

                    method = test.get("method", "GET").upper()
                    if method == "GET":
                        async with session.get(
                            full_url, timeout=aiohttp.ClientTimeout(total=30)
                        ) as response:
                            test_result["status_code"] = response.status
                            test_result["latency_ms"] = (
                                datetime.utcnow() - start_time
                            ).total_seconds() * 1000

                            body = await response.text()

                            if response.status == expected_status:
                                # Check body if specified
                                expected_body = test.get("expected_body_contains")
                                if expected_body:
                                    if expected_body in body:
                                        test_result["passed"] = True
                                    else:
                                        test_result["error"] = (
                                            f"Expected body to contain: {expected_body}"
                                        )
                                else:
                                    test_result["passed"] = True
                            else:
                                test_result["error"] = (
                                    f"Expected status {expected_status}, got {response.status}"
                                )

                    elif method == "POST":
                        async with session.post(
                            full_url,
                            json=test.get("body", {}),
                            timeout=aiohttp.ClientTimeout(total=30),
                        ) as response:
                            test_result["status_code"] = response.status
                            test_result["latency_ms"] = (
                                datetime.utcnow() - start_time
                            ).total_seconds() * 1000
                            test_result["passed"] = response.status == expected_status

                except Exception as e:
                    test_result["error"] = str(e)

                if test_result["passed"]:
                    results["passed"] += 1
                else:
                    results["failed"] += 1

                results["tests"].append(test_result)

                if progress_callback:
                    progress = ((i + 1) / len(smoke_tests)) * 90 + 5
                    status = "PASS" if test_result["passed"] else "FAIL"
                    progress_callback(f"[{status}] {test['path']}", progress)

        results["all_passed"] = results["failed"] == 0

        if progress_callback:
            progress_callback(
                f"Smoke tests complete: {results['passed']}/{results['total']} passed",
                100,
            )

        return results

    async def deploy_and_verify(
        self,
        config: DeploymentConfig,
        smoke_tests: Optional[List[Dict[str, Any]]] = None,
        health_endpoint: str = "/health",
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> Dict[str, Any]:
        """
        Deploy and verify the deployment with health checks and smoke tests.

        This is the comprehensive deployment method that:
        1. Executes the deployment
        2. Waits for deployment to be ready
        3. Runs health checks
        4. Runs smoke tests (if provided)
        5. Returns comprehensive results

        Args:
            config: Deployment configuration
            smoke_tests: Optional smoke tests to run
            health_endpoint: Health check endpoint
            progress_callback: Progress callback

        Returns:
            Comprehensive deployment and verification results
        """
        result = {
            "deployment": None,
            "health_check": None,
            "smoke_tests": None,
            "success": False,
            "error": None,
            "rollback_command": None,
        }

        # Step 1: Deploy
        if progress_callback:
            progress_callback("Starting deployment...", 5)

        deploy_result = await self.execute_deployment(
            config,
            progress_callback=lambda msg, pct: (
                progress_callback(msg, pct * 0.4) if progress_callback else None
            ),
        )

        result["deployment"] = {
            "success": deploy_result.success,
            "status": deploy_result.status.value if deploy_result.status else None,
            "url": deploy_result.deployment_url,
            "deployment_id": deploy_result.deployment_id,
            "duration_seconds": deploy_result.duration_seconds,
            "error": deploy_result.error,
        }

        if not deploy_result.success:
            result["error"] = f"Deployment failed: {deploy_result.error}"
            return result

        result["rollback_command"] = deploy_result.rollback_command

        # Step 2: Health Check
        if deploy_result.deployment_url:
            if progress_callback:
                progress_callback("Verifying deployment health...", 45)

            health_result = await self.verify_deployment_health(
                url=deploy_result.deployment_url,
                health_endpoint=health_endpoint,
                progress_callback=lambda msg, pct: (
                    progress_callback(msg, 40 + pct * 0.3)
                    if progress_callback
                    else None
                ),
            )
            result["health_check"] = health_result

            if not health_result["healthy"]:
                result["error"] = f"Health check failed: {health_result.get('error')}"
                return result

            # Step 3: Smoke Tests
            if smoke_tests:
                if progress_callback:
                    progress_callback("Running smoke tests...", 75)

                smoke_result = await self.run_smoke_tests(
                    url=deploy_result.deployment_url,
                    smoke_tests=smoke_tests,
                    progress_callback=lambda msg, pct: (
                        progress_callback(msg, 70 + pct * 0.3)
                        if progress_callback
                        else None
                    ),
                )
                result["smoke_tests"] = smoke_result

                if not smoke_result["all_passed"]:
                    result["error"] = (
                        f"Smoke tests failed: {smoke_result['failed']}/{smoke_result['total']} tests failed"
                    )
                    return result

        result["success"] = True

        if progress_callback:
            progress_callback("Deployment verified successfully!", 100)

        return result

    async def auto_rollback_on_failure(
        self,
        config: DeploymentConfig,
        smoke_tests: Optional[List[Dict[str, Any]]] = None,
        health_endpoint: str = "/health",
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> Dict[str, Any]:
        """
        Deploy with automatic rollback on verification failure.

        If health checks or smoke tests fail, automatically rollback.

        Args:
            config: Deployment configuration
            smoke_tests: Smoke tests to run
            health_endpoint: Health check endpoint
            progress_callback: Progress callback

        Returns:
            Deployment result with rollback status if applicable
        """
        result = await self.deploy_and_verify(
            config=config,
            smoke_tests=smoke_tests,
            health_endpoint=health_endpoint,
            progress_callback=progress_callback,
        )

        if not result["success"] and result.get("rollback_command"):
            if progress_callback:
                progress_callback("Verification failed, initiating rollback...", 85)

            try:
                deployment_id = result.get("deployment", {}).get(
                    "deployment_id", "unknown"
                )

                rollback_result = await self.rollback_deployment(
                    platform=config.platform,
                    deployment_id=deployment_id,
                    workspace_path=config.workspace_path,
                    progress_callback=lambda msg, pct: (
                        progress_callback(msg, 85 + pct * 0.15)
                        if progress_callback
                        else None
                    ),
                )

                result["rollback"] = {
                    "success": rollback_result.success,
                    "error": rollback_result.error,
                }

                if progress_callback:
                    if rollback_result.success:
                        progress_callback("Rollback completed successfully", 100)
                    else:
                        progress_callback(
                            f"Rollback failed: {rollback_result.error}", 100
                        )

            except Exception as e:
                result["rollback"] = {
                    "success": False,
                    "error": str(e),
                }

        return result


# Global instance
deployment_executor_service = DeploymentExecutorService()
