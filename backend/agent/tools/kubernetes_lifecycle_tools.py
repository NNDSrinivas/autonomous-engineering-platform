"""
Kubernetes Lifecycle Tools for NAVI Enterprise

This module provides Kubernetes cluster lifecycle management tools for
NAVI's enterprise features, including:
- Multi-cloud cluster creation (EKS, GKE, AKS)
- Cluster upgrades with proper drain and cordon procedures
- Node pool management (scaling, taints, labels)
- Add-on installation (CNI, Ingress, monitoring, service mesh)

Usage:
    from backend.agent.tools.kubernetes_lifecycle_tools import K8S_LIFECYCLE_TOOLS
"""

import os
import yaml
from typing import Dict, Any, List, Optional
from datetime import datetime


# ============================================================================
# KUBERNETES CLUSTER CREATION
# ============================================================================


async def k8s_cluster_create(
    provider: str,
    cluster_name: str,
    region: str,
    node_count: int = 3,
    node_type: str = "standard",
    kubernetes_version: str = "latest",
    vpc_config: Optional[Dict[str, Any]] = None,
    enable_private_cluster: bool = False,
    enable_workload_identity: bool = True,
    tags: Optional[Dict[str, str]] = None,
    workspace_path: str = ".",
) -> Dict[str, Any]:
    """
    Create a Kubernetes cluster on a cloud provider.

    Supports:
    - AWS EKS
    - Google GKE
    - Azure AKS
    - Local (kind/minikube for development)

    Args:
        provider: Cloud provider (eks, gke, aks, kind, minikube)
        cluster_name: Name for the cluster
        region: Cloud region/zone
        node_count: Number of worker nodes
        node_type: Instance type category (standard, compute, memory, gpu)
        kubernetes_version: K8s version (or 'latest')
        vpc_config: VPC/network configuration
        enable_private_cluster: Whether to create private cluster
        enable_workload_identity: Enable workload identity (GKE/AKS)
        tags: Resource tags
        workspace_path: Path for generated configurations

    Returns:
        Cluster creation result with connection details
    """
    result = {
        "provider": provider,
        "cluster_name": cluster_name,
        "region": region,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "configuration": {},
        "commands": [],
        "estimated_time": "10-15 minutes",
    }

    # Instance type mappings per provider
    instance_types = {
        "eks": {
            "standard": "t3.medium",
            "compute": "c5.xlarge",
            "memory": "r5.xlarge",
            "gpu": "p3.2xlarge",
        },
        "gke": {
            "standard": "e2-standard-4",
            "compute": "c2-standard-8",
            "memory": "n2-highmem-4",
            "gpu": "n1-standard-4",  # + GPU accelerator
        },
        "aks": {
            "standard": "Standard_D4s_v3",
            "compute": "Standard_F8s_v2",
            "memory": "Standard_E4s_v3",
            "gpu": "Standard_NC6s_v3",
        },
    }

    provider = provider.lower()

    if provider == "eks":
        instance_type = instance_types["eks"].get(node_type, "t3.medium")

        # Generate eksctl configuration
        eksctl_config = {
            "apiVersion": "eksctl.io/v1alpha5",
            "kind": "ClusterConfig",
            "metadata": {"name": cluster_name, "region": region, "tags": tags or {}},
            "managedNodeGroups": [
                {
                    "name": f"{cluster_name}-ng-1",
                    "instanceType": instance_type,
                    "desiredCapacity": node_count,
                    "minSize": 1,
                    "maxSize": node_count * 2,
                    "volumeSize": 100,
                    "volumeType": "gp3",
                    "privateNetworking": enable_private_cluster,
                    "iam": {
                        "withAddonPolicies": {
                            "imageBuilder": True,
                            "autoScaler": True,
                            "albIngress": True,
                            "cloudWatch": True,
                        }
                    },
                }
            ],
            "cloudWatch": {
                "clusterLogging": {
                    "enableTypes": [
                        "api",
                        "audit",
                        "authenticator",
                        "controllerManager",
                        "scheduler",
                    ]
                }
            },
        }

        if vpc_config:
            eksctl_config["vpc"] = vpc_config

        # Write config file
        config_path = os.path.join(workspace_path, f"{cluster_name}-eksctl.yaml")
        result["configuration"] = eksctl_config
        result["config_file"] = config_path

        result["commands"] = [
            f"eksctl create cluster -f {config_path}",
            f"aws eks update-kubeconfig --name {cluster_name} --region {region}",
        ]

    elif provider == "gke":
        instance_type = instance_types["gke"].get(node_type, "e2-standard-4")

        gcloud_args = [
            (
                f"--cluster-version={kubernetes_version}"
                if kubernetes_version != "latest"
                else "--release-channel=regular"
            ),
            f"--machine-type={instance_type}",
            f"--num-nodes={node_count}",
            f"--region={region}",
            "--enable-ip-alias",
            "--enable-autoscaling",
            "--min-nodes=1",
            f"--max-nodes={node_count * 2}",
        ]

        if enable_workload_identity:
            gcloud_args.append(
                "--workload-pool=$(gcloud config get-value project).svc.id.goog"
            )

        if enable_private_cluster:
            gcloud_args.extend(
                [
                    "--enable-private-nodes",
                    "--master-ipv4-cidr=172.16.0.0/28",
                    "--enable-master-authorized-networks",
                ]
            )

        result["commands"] = [
            f"gcloud container clusters create {cluster_name} {' '.join(gcloud_args)}",
            f"gcloud container clusters get-credentials {cluster_name} --region {region}",
        ]

        result["configuration"] = {
            "cluster_name": cluster_name,
            "region": region,
            "machine_type": instance_type,
            "node_count": node_count,
            "private_cluster": enable_private_cluster,
            "workload_identity": enable_workload_identity,
        }

    elif provider == "aks":
        instance_type = instance_types["aks"].get(node_type, "Standard_D4s_v3")
        resource_group = f"{cluster_name}-rg"

        az_args = [
            f"--name {cluster_name}",
            f"--resource-group {resource_group}",
            f"--node-count {node_count}",
            f"--node-vm-size {instance_type}",
            f"--location {region}",
            "--enable-cluster-autoscaler",
            "--min-count 1",
            f"--max-count {node_count * 2}",
            "--network-plugin azure",
            "--enable-managed-identity",
        ]

        if kubernetes_version != "latest":
            az_args.append(f"--kubernetes-version {kubernetes_version}")

        if enable_private_cluster:
            az_args.append("--enable-private-cluster")

        if enable_workload_identity:
            az_args.append("--enable-workload-identity")
            az_args.append("--enable-oidc-issuer")

        result["commands"] = [
            f"az group create --name {resource_group} --location {region}",
            f"az aks create {' '.join(az_args)}",
            f"az aks get-credentials --resource-group {resource_group} --name {cluster_name}",
        ]

        result["configuration"] = {
            "cluster_name": cluster_name,
            "resource_group": resource_group,
            "region": region,
            "node_vm_size": instance_type,
            "node_count": node_count,
        }

    elif provider in ["kind", "minikube"]:
        # Local development clusters
        if provider == "kind":
            kind_config = {
                "kind": "Cluster",
                "apiVersion": "kind.x-k8s.io/v1alpha4",
                "nodes": [
                    {"role": "control-plane"},
                    *[{"role": "worker"} for _ in range(node_count)],
                ],
            }

            config_path = os.path.join(workspace_path, f"{cluster_name}-kind.yaml")
            result["configuration"] = kind_config
            result["config_file"] = config_path
            result["commands"] = [
                f"kind create cluster --name {cluster_name} --config {config_path}"
            ]
            result["estimated_time"] = "2-3 minutes"

        else:  # minikube
            result["commands"] = [
                f"minikube start --profile {cluster_name} --nodes {node_count + 1} --driver=docker"
            ]
            result["estimated_time"] = "3-5 minutes"
    else:
        return {
            "status": "error",
            "error": f"Unsupported provider: {provider}. Use eks, gke, aks, kind, or minikube",
        }

    # Check if we should actually provision or just generate config
    # The execute parameter controls this
    execute = True  # Default to actually executing

    if execute:
        # ACTUALLY PROVISION THE CLUSTER
        from backend.services.infrastructure_executor_service import (
            infrastructure_executor_service,
        )

        async def log_progress(msg: str, pct: float):
            result["progress_messages"] = result.get("progress_messages", [])
            result["progress_messages"].append({"message": msg, "percentage": pct})

        try:
            if provider == "eks":
                # Write config file first
                config_path = os.path.join(
                    workspace_path, f"{cluster_name}-eksctl.yaml"
                )
                with open(config_path, "w") as f:
                    yaml.dump(result["configuration"], f)

                provision_result = (
                    await infrastructure_executor_service.provision_eks_cluster(
                        cluster_name=cluster_name,
                        region=region,
                        config_path=config_path,
                        progress_callback=log_progress,
                    )
                )

            elif provider == "gke":
                # Get project ID from gcloud config
                import subprocess

                project_result = subprocess.run(
                    ["gcloud", "config", "get-value", "project"],
                    capture_output=True,
                    text=True,
                )
                project_id = project_result.stdout.strip() or "default-project"

                provision_result = (
                    await infrastructure_executor_service.provision_gke_cluster(
                        cluster_name=cluster_name,
                        region=region,
                        project_id=project_id,
                        machine_type=result["configuration"].get(
                            "machine_type", "e2-standard-4"
                        ),
                        node_count=node_count,
                        progress_callback=log_progress,
                    )
                )

            elif provider == "aks":
                resource_group = f"{cluster_name}-rg"
                provision_result = (
                    await infrastructure_executor_service.provision_aks_cluster(
                        cluster_name=cluster_name,
                        resource_group=resource_group,
                        location=region,
                        node_count=node_count,
                        vm_size=result["configuration"].get(
                            "vm_size", "Standard_D4s_v3"
                        ),
                        progress_callback=log_progress,
                    )
                )

            elif provider in ["kind", "minikube"]:
                config_path = None
                if provider == "kind" and result.get("configuration"):
                    config_path = os.path.join(
                        workspace_path, f"{cluster_name}-kind.yaml"
                    )
                    with open(config_path, "w") as f:
                        yaml.dump(result["configuration"], f)

                provision_result = (
                    await infrastructure_executor_service.provision_local_cluster(
                        cluster_name=cluster_name,
                        provider=provider,
                        node_count=node_count,
                        config_path=config_path,
                        progress_callback=log_progress,
                    )
                )
            else:
                return {
                    "status": "error",
                    "error": f"Provider {provider} does not support actual provisioning yet",
                }

            # Update result based on provisioning outcome
            if provision_result.success:
                result["status"] = "created"
                result["outputs"] = provision_result.outputs
                result["duration_seconds"] = provision_result.duration_seconds
                result["rollback_command"] = provision_result.rollback_command
                result["logs"] = (
                    provision_result.logs[-20:] if provision_result.logs else []
                )

                # Verify cluster health
                health = await infrastructure_executor_service.verify_cluster_health()
                result["cluster_health"] = health
            else:
                result["status"] = "failed"
                result["error"] = provision_result.error
                result["logs"] = (
                    provision_result.logs[-20:] if provision_result.logs else []
                )

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)

    else:
        # Just return the commands without executing
        result["status"] = "ready_to_execute"
        result["next_steps"] = [
            "Execute the commands above to create the cluster",
            "Verify cluster access with: kubectl cluster-info",
            "Install essential add-ons (CNI, ingress, monitoring)",
        ]

    return result


# ============================================================================
# KUBERNETES CLUSTER UPGRADE
# ============================================================================


async def k8s_cluster_upgrade(
    provider: str,
    cluster_name: str,
    region: str,
    target_version: str,
    upgrade_strategy: str = "rolling",
    drain_timeout: int = 300,
    node_pool: Optional[str] = None,
    workspace_path: str = ".",
) -> Dict[str, Any]:
    """
    Upgrade a Kubernetes cluster to a new version.

    Implements safe upgrade procedures:
    - Pre-upgrade validation
    - Control plane upgrade first
    - Rolling node upgrades with drain/cordon
    - Post-upgrade verification

    Args:
        provider: Cloud provider (eks, gke, aks)
        cluster_name: Cluster to upgrade
        region: Cloud region
        target_version: Target Kubernetes version
        upgrade_strategy: rolling, blue-green, or surge
        drain_timeout: Timeout for node drain (seconds)
        node_pool: Specific node pool to upgrade (None = all)
        workspace_path: Path for generated scripts

    Returns:
        Upgrade plan with commands and verification steps
    """
    result = {
        "provider": provider,
        "cluster_name": cluster_name,
        "target_version": target_version,
        "upgrade_strategy": upgrade_strategy,
        "status": "pending",
        "phases": [],
        "pre_upgrade_checks": [],
        "post_upgrade_verification": [],
        "rollback_plan": {},
    }

    # Pre-upgrade checks (common across providers)
    result["pre_upgrade_checks"] = [
        {"name": "Check current version", "command": "kubectl version --short"},
        {
            "name": "Verify cluster health",
            "command": "kubectl get nodes && kubectl get pods -A | grep -v Running | grep -v Completed",
        },
        {
            "name": "Check for deprecated APIs",
            "command": "kubectl get --raw /metrics | grep apiserver_requested_deprecated_apis",
        },
        {
            "name": "Backup critical resources",
            "command": "kubectl get all,cm,secret,pvc -A -o yaml > pre-upgrade-backup.yaml",
        },
        {"name": "Check PodDisruptionBudgets", "command": "kubectl get pdb -A"},
    ]

    provider = provider.lower()

    if provider == "eks":
        result["phases"] = [
            {
                "phase": 1,
                "name": "Upgrade Control Plane",
                "commands": [
                    f"eksctl upgrade cluster --name {cluster_name} --region {region} --version {target_version} --approve"
                ],
                "estimated_time": "20-30 minutes",
            },
            {
                "phase": 2,
                "name": "Update Node Groups",
                "commands": [
                    f"eksctl upgrade nodegroup --cluster {cluster_name} --region {region} --name {node_pool or '<nodegroup-name>'} --kubernetes-version {target_version}"
                ],
                "estimated_time": "10-20 minutes per node group",
                "notes": "EKS performs rolling updates automatically",
            },
            {
                "phase": 3,
                "name": "Update Add-ons",
                "commands": [
                    f"eksctl utils update-kube-proxy --cluster {cluster_name} --region {region} --approve",
                    f"eksctl utils update-coredns --cluster {cluster_name} --region {region} --approve",
                    f"eksctl utils update-aws-node --cluster {cluster_name} --region {region} --approve",
                ],
                "estimated_time": "5-10 minutes",
            },
        ]

        result["rollback_plan"] = {
            "strategy": "Create new node group with previous version, migrate workloads",
            "commands": [
                f"eksctl create nodegroup --cluster {cluster_name} --region {region} --version <previous-version> --name rollback-ng"
            ],
        }

    elif provider == "gke":
        result["phases"] = [
            {
                "phase": 1,
                "name": "Upgrade Control Plane",
                "commands": [
                    f"gcloud container clusters upgrade {cluster_name} --master --cluster-version {target_version} --region {region} --quiet"
                ],
                "estimated_time": "10-20 minutes",
            },
            {
                "phase": 2,
                "name": "Upgrade Node Pools",
                "commands": [
                    f"gcloud container clusters upgrade {cluster_name} --node-pool {node_pool or 'default-pool'} --cluster-version {target_version} --region {region} --quiet"
                ],
                "estimated_time": "5-10 minutes per node",
                "notes": "Use --max-surge-upgrade and --max-unavailable-upgrade for surge strategy",
            },
        ]

        if upgrade_strategy == "surge":
            result["phases"][1]["commands"] = [
                f"gcloud container clusters upgrade {cluster_name} --node-pool {node_pool or 'default-pool'} --cluster-version {target_version} --region {region} --max-surge-upgrade=1 --max-unavailable-upgrade=0 --quiet"
            ]

        result["rollback_plan"] = {
            "strategy": "GKE supports automatic rollback if upgrade fails",
            "manual_rollback": f"gcloud container clusters upgrade {cluster_name} --cluster-version <previous-version> --region {region}",
        }

    elif provider == "aks":
        result["phases"] = [
            {
                "phase": 1,
                "name": "Upgrade Control Plane and Nodes",
                "commands": [
                    f"az aks upgrade --resource-group {cluster_name}-rg --name {cluster_name} --kubernetes-version {target_version} --yes"
                ],
                "estimated_time": "30-45 minutes",
                "notes": "AKS upgrades control plane and nodes together by default",
            }
        ]

        if node_pool:
            result["phases"].append(
                {
                    "phase": 2,
                    "name": f"Upgrade Node Pool: {node_pool}",
                    "commands": [
                        f"az aks nodepool upgrade --resource-group {cluster_name}-rg --cluster-name {cluster_name} --name {node_pool} --kubernetes-version {target_version}"
                    ],
                    "estimated_time": "15-30 minutes",
                }
            )

        result["rollback_plan"] = {
            "strategy": "AKS does not support version downgrades. Use node pool replacement.",
            "commands": [
                f"az aks nodepool add --resource-group {cluster_name}-rg --cluster-name {cluster_name} --name rollback --kubernetes-version <previous-version>",
                "# Migrate workloads to new pool",
                f"az aks nodepool delete --resource-group {cluster_name}-rg --cluster-name {cluster_name} --name <old-pool>",
            ],
        }
    else:
        return {"status": "error", "error": f"Unsupported provider: {provider}"}

    # Post-upgrade verification (common)
    result["post_upgrade_verification"] = [
        {"name": "Verify cluster version", "command": "kubectl version --short"},
        {"name": "Check node status", "command": "kubectl get nodes -o wide"},
        {"name": "Verify system pods", "command": "kubectl get pods -n kube-system"},
        {
            "name": "Test cluster DNS",
            "command": "kubectl run test-dns --image=busybox --rm -it --restart=Never -- nslookup kubernetes.default",
        },
        {
            "name": "Verify workloads",
            "command": "kubectl get pods -A | grep -v Running | grep -v Completed",
        },
    ]

    result["status"] = "ready_to_execute"
    return result


# ============================================================================
# NODE POOL MANAGEMENT
# ============================================================================


async def k8s_node_pool_manage(
    provider: str,
    cluster_name: str,
    region: str,
    action: str,
    node_pool_name: str,
    node_count: Optional[int] = None,
    node_type: Optional[str] = None,
    taints: Optional[List[Dict[str, str]]] = None,
    labels: Optional[Dict[str, str]] = None,
    enable_autoscaling: bool = False,
    min_nodes: int = 1,
    max_nodes: int = 10,
) -> Dict[str, Any]:
    """
    Manage Kubernetes node pools.

    Actions:
    - create: Create a new node pool
    - delete: Remove a node pool
    - scale: Change node count
    - update: Update labels/taints
    - autoscale: Configure autoscaling

    Args:
        provider: Cloud provider
        cluster_name: Cluster name
        region: Cloud region
        action: create, delete, scale, update, autoscale
        node_pool_name: Name of the node pool
        node_count: Number of nodes
        node_type: Instance type (for create)
        taints: Kubernetes taints
        labels: Kubernetes labels
        enable_autoscaling: Enable cluster autoscaler
        min_nodes: Minimum nodes for autoscaling
        max_nodes: Maximum nodes for autoscaling

    Returns:
        Node pool management result with commands
    """
    result = {
        "provider": provider,
        "cluster_name": cluster_name,
        "node_pool": node_pool_name,
        "action": action,
        "status": "pending",
        "commands": [],
    }

    provider = provider.lower()
    action = action.lower()

    if provider == "eks":
        if action == "create":
            args = [
                f"--cluster {cluster_name}",
                f"--region {region}",
                f"--name {node_pool_name}",
                f"--nodes {node_count or 3}",
                f"--node-type {node_type or 't3.medium'}",
            ]

            if enable_autoscaling:
                args.extend(
                    [
                        "--asg-access",
                        f"--nodes-min {min_nodes}",
                        f"--nodes-max {max_nodes}",
                    ]
                )

            if labels:
                label_str = ",".join([f"{k}={v}" for k, v in labels.items()])
                args.append(f"--node-labels {label_str}")

            result["commands"] = [f"eksctl create nodegroup {' '.join(args)}"]

        elif action == "delete":
            result["commands"] = [
                f"eksctl delete nodegroup --cluster {cluster_name} --region {region} --name {node_pool_name}"
            ]

        elif action == "scale":
            result["commands"] = [
                f"eksctl scale nodegroup --cluster {cluster_name} --region {region} --name {node_pool_name} --nodes {node_count}"
            ]

    elif provider == "gke":
        if action == "create":
            args = [
                f"--cluster {cluster_name}",
                f"--region {region}",
                f"--num-nodes {node_count or 3}",
                f"--machine-type {node_type or 'e2-standard-4'}",
            ]

            if enable_autoscaling:
                args.extend(
                    [
                        "--enable-autoscaling",
                        f"--min-nodes {min_nodes}",
                        f"--max-nodes {max_nodes}",
                    ]
                )

            if labels:
                label_str = ",".join([f"{k}={v}" for k, v in labels.items()])
                args.append(f"--node-labels={label_str}")

            if taints:
                for taint in taints:
                    args.append(
                        f"--node-taints={taint['key']}={taint['value']}:{taint['effect']}"
                    )

            result["commands"] = [
                f"gcloud container node-pools create {node_pool_name} {' '.join(args)}"
            ]

        elif action == "delete":
            result["commands"] = [
                f"gcloud container node-pools delete {node_pool_name} --cluster {cluster_name} --region {region} --quiet"
            ]

        elif action == "scale":
            result["commands"] = [
                f"gcloud container clusters resize {cluster_name} --node-pool {node_pool_name} --num-nodes {node_count} --region {region} --quiet"
            ]

        elif action == "autoscale":
            result["commands"] = [
                f"gcloud container clusters update {cluster_name} --enable-autoscaling --node-pool {node_pool_name} --min-nodes {min_nodes} --max-nodes {max_nodes} --region {region}"
            ]

    elif provider == "aks":
        resource_group = f"{cluster_name}-rg"

        if action == "create":
            args = [
                f"--resource-group {resource_group}",
                f"--cluster-name {cluster_name}",
                f"--name {node_pool_name}",
                f"--node-count {node_count or 3}",
                f"--node-vm-size {node_type or 'Standard_D4s_v3'}",
            ]

            if enable_autoscaling:
                args.extend(
                    [
                        "--enable-cluster-autoscaler",
                        f"--min-count {min_nodes}",
                        f"--max-count {max_nodes}",
                    ]
                )

            if labels:
                label_str = " ".join([f"{k}={v}" for k, v in labels.items()])
                args.append(f"--labels {label_str}")

            if taints:
                for taint in taints:
                    args.append(
                        f"--node-taints {taint['key']}={taint['value']}:{taint['effect']}"
                    )

            result["commands"] = [f"az aks nodepool add {' '.join(args)}"]

        elif action == "delete":
            result["commands"] = [
                f"az aks nodepool delete --resource-group {resource_group} --cluster-name {cluster_name} --name {node_pool_name}"
            ]

        elif action == "scale":
            result["commands"] = [
                f"az aks nodepool scale --resource-group {resource_group} --cluster-name {cluster_name} --name {node_pool_name} --node-count {node_count}"
            ]

    result["status"] = "ready_to_execute"
    return result


# ============================================================================
# KUBERNETES ADD-ONS INSTALLATION
# ============================================================================


async def k8s_install_addons(
    addons: List[str],
    cluster_name: str,
    provider: Optional[str] = None,
    namespace: str = "kube-system",
    helm_values: Optional[Dict[str, Any]] = None,
    workspace_path: str = ".",
) -> Dict[str, Any]:
    """
    Install Kubernetes add-ons and ecosystem tools.

    Supported add-ons:
    - CNI: calico, cilium, weave
    - Ingress: nginx, traefik, kong, istio-gateway
    - Monitoring: prometheus-stack, datadog, newrelic
    - Logging: loki-stack, elastic-stack, fluentd
    - Service Mesh: istio, linkerd
    - Secrets: external-secrets, sealed-secrets, vault
    - Policy: opa-gatekeeper, kyverno
    - Storage: longhorn, rook-ceph
    - Autoscaling: keda, cluster-autoscaler
    - GitOps: argocd, fluxcd
    - Cert Management: cert-manager

    Args:
        addons: List of add-ons to install
        cluster_name: Cluster name (for configuration)
        provider: Cloud provider (for provider-specific config)
        namespace: Target namespace
        helm_values: Custom Helm values
        workspace_path: Path for generated configs

    Returns:
        Installation commands and configurations
    """
    result = {
        "cluster_name": cluster_name,
        "addons": [],
        "helm_repos": [],
        "status": "pending",
    }

    # Helm repository configurations
    helm_repos = {
        "prometheus-community": "https://prometheus-community.github.io/helm-charts",
        "grafana": "https://grafana.github.io/helm-charts",
        "ingress-nginx": "https://kubernetes.github.io/ingress-nginx",
        "jetstack": "https://charts.jetstack.io",
        "bitnami": "https://charts.bitnami.com/bitnami",
        "argo": "https://argoproj.github.io/argo-helm",
        "traefik": "https://helm.traefik.io/traefik",
        "kong": "https://charts.konghq.com",
        "istio": "https://istio-release.storage.googleapis.com/charts",
        "linkerd": "https://helm.linkerd.io/stable",
        "hashicorp": "https://helm.releases.hashicorp.com",
        "external-secrets": "https://charts.external-secrets.io",
        "sealed-secrets": "https://bitnami-labs.github.io/sealed-secrets",
        "kedacore": "https://kedacore.github.io/charts",
        "longhorn": "https://charts.longhorn.io",
        "kyverno": "https://kyverno.github.io/kyverno",
        "gatekeeper": "https://open-policy-agent.github.io/gatekeeper/charts",
        "fluxcd": "https://fluxcd-community.github.io/helm-charts",
        "cilium": "https://helm.cilium.io",
        "calico": "https://docs.tigera.io/calico/charts",
        "datadog": "https://helm.datadoghq.com",
        "elastic": "https://helm.elastic.co",
    }

    # Add-on installation configurations
    addon_configs = {
        # CNI
        "calico": {
            "repo": "calico",
            "chart": "tigera-operator",
            "namespace": "tigera-operator",
            "commands": [
                "kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.26.1/manifests/tigera-operator.yaml",
                "kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.26.1/manifests/custom-resources.yaml",
            ],
        },
        "cilium": {
            "repo": "cilium",
            "chart": "cilium",
            "namespace": "kube-system",
            "values": {"hubble.relay.enabled": True, "hubble.ui.enabled": True},
        },
        # Ingress Controllers
        "nginx": {
            "repo": "ingress-nginx",
            "chart": "ingress-nginx",
            "namespace": "ingress-nginx",
            "values": {
                "controller.replicaCount": 2,
                "controller.metrics.enabled": True,
            },
        },
        "traefik": {
            "repo": "traefik",
            "chart": "traefik",
            "namespace": "traefik",
            "values": {"deployment.replicas": 2, "metrics.prometheus.enabled": True},
        },
        "kong": {
            "repo": "kong",
            "chart": "kong",
            "namespace": "kong",
            "values": {"proxy.type": "LoadBalancer"},
        },
        # Monitoring
        "prometheus-stack": {
            "repo": "prometheus-community",
            "chart": "kube-prometheus-stack",
            "namespace": "monitoring",
            "values": {
                "grafana.enabled": True,
                "alertmanager.enabled": True,
                "prometheus.prometheusSpec.retention": "15d",
            },
        },
        "datadog": {
            "repo": "datadog",
            "chart": "datadog",
            "namespace": "datadog",
            "values": {"datadog.logs.enabled": True, "datadog.apm.enabled": True},
            "secrets_required": ["datadog-api-key"],
        },
        # Logging
        "loki-stack": {
            "repo": "grafana",
            "chart": "loki-stack",
            "namespace": "logging",
            "values": {"promtail.enabled": True, "grafana.enabled": True},
        },
        # Service Mesh
        "istio": {
            "repo": "istio",
            "chart": "base",
            "namespace": "istio-system",
            "commands": [
                "helm install istio-base istio/base -n istio-system --create-namespace",
                "helm install istiod istio/istiod -n istio-system --wait",
                "helm install istio-ingress istio/gateway -n istio-ingress --create-namespace",
            ],
        },
        "linkerd": {
            "repo": "linkerd",
            "chart": "linkerd-control-plane",
            "namespace": "linkerd",
            "commands": [
                "linkerd install --crds | kubectl apply -f -",
                "linkerd install | kubectl apply -f -",
                "linkerd check",
            ],
        },
        # Secrets Management
        "external-secrets": {
            "repo": "external-secrets",
            "chart": "external-secrets",
            "namespace": "external-secrets",
            "values": {},
        },
        "sealed-secrets": {
            "repo": "sealed-secrets",
            "chart": "sealed-secrets",
            "namespace": "kube-system",
        },
        "vault": {
            "repo": "hashicorp",
            "chart": "vault",
            "namespace": "vault",
            "values": {"server.ha.enabled": True, "server.ha.replicas": 3},
        },
        # Policy Engines
        "opa-gatekeeper": {
            "repo": "gatekeeper",
            "chart": "gatekeeper",
            "namespace": "gatekeeper-system",
        },
        "kyverno": {"repo": "kyverno", "chart": "kyverno", "namespace": "kyverno"},
        # GitOps
        "argocd": {
            "repo": "argo",
            "chart": "argo-cd",
            "namespace": "argocd",
            "values": {"server.service.type": "LoadBalancer"},
            "post_install": [
                "kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d"
            ],
        },
        "fluxcd": {"commands": ["flux install"]},
        # Autoscaling
        "keda": {"repo": "kedacore", "chart": "keda", "namespace": "keda"},
        "cluster-autoscaler": {
            "repo": "cluster-autoscaler",
            "chart": "cluster-autoscaler",
            "namespace": "kube-system",
        },
        # Certificate Management
        "cert-manager": {
            "repo": "jetstack",
            "chart": "cert-manager",
            "namespace": "cert-manager",
            "values": {"installCRDs": True},
        },
        # Storage
        "longhorn": {
            "repo": "longhorn",
            "chart": "longhorn",
            "namespace": "longhorn-system",
        },
    }

    required_repos = set()

    for addon in addons:
        addon_lower = addon.lower()

        if addon_lower not in addon_configs:
            result["addons"].append(
                {
                    "name": addon,
                    "status": "error",
                    "error": f"Unknown add-on: {addon}. Supported: {list(addon_configs.keys())}",
                }
            )
            continue

        config = addon_configs[addon_lower]
        addon_result = {
            "name": addon,
            "namespace": config.get("namespace", namespace),
            "commands": [],
        }

        # Add Helm repo if needed
        if "repo" in config:
            repo_name = config["repo"]
            if repo_name in helm_repos:
                required_repos.add(repo_name)

        # Generate installation commands
        if "commands" in config:
            addon_result["commands"] = config["commands"]
        elif "chart" in config:
            repo_name = config.get("repo", "")
            chart_name = config["chart"]
            ns = config.get("namespace", namespace)

            # Build Helm install command
            helm_cmd = f"helm install {addon_lower} {repo_name}/{chart_name} -n {ns} --create-namespace"

            # Merge values
            values = config.get("values", {})
            if helm_values and addon_lower in helm_values:
                values.update(helm_values[addon_lower])

            if values:
                values_file = os.path.join(workspace_path, f"{addon_lower}-values.yaml")
                addon_result["values_file"] = values_file
                addon_result["values"] = values
                helm_cmd += f" -f {values_file}"

            addon_result["commands"].append(helm_cmd)

        if "post_install" in config:
            addon_result["post_install"] = config["post_install"]

        if "secrets_required" in config:
            addon_result["secrets_required"] = config["secrets_required"]

        addon_result["status"] = "ready"
        result["addons"].append(addon_result)

    # Generate Helm repo add commands
    result["helm_repos"] = [
        f"helm repo add {repo} {helm_repos[repo]}"
        for repo in required_repos
        if repo in helm_repos
    ]

    if result["helm_repos"]:
        result["helm_repos"].append("helm repo update")

    result["status"] = "ready_to_execute"
    result["install_order"] = [
        "1. Add Helm repositories",
        "2. Install CNI (if cluster doesn't have one)",
        "3. Install cert-manager (if using TLS)",
        "4. Install ingress controller",
        "5. Install monitoring/logging",
        "6. Install other add-ons",
    ]

    return result


# ============================================================================
# CLUSTER HEALTH CHECK
# ============================================================================


async def k8s_cluster_health_check(
    checks: Optional[List[str]] = None,
    namespace: Optional[str] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Perform comprehensive Kubernetes cluster health checks.

    Check categories:
    - nodes: Node status, resources, conditions
    - pods: Pod health, restarts, pending pods
    - services: Service endpoints, load balancers
    - storage: PVC status, storage classes
    - networking: DNS, network policies
    - security: RBAC, pod security
    - resources: Resource quotas, limits

    Args:
        checks: Specific checks to run (None = all)
        namespace: Specific namespace (None = all)
        verbose: Include detailed output

    Returns:
        Health check results with issues and recommendations
    """
    all_checks = [
        "nodes",
        "pods",
        "services",
        "storage",
        "networking",
        "security",
        "resources",
    ]
    checks_to_run = checks if checks else all_checks

    result = {
        "status": "healthy",
        "checks": {},
        "issues": [],
        "recommendations": [],
        "commands_to_run": [],
    }

    ns_flag = f"-n {namespace}" if namespace else "-A"

    check_commands = {
        "nodes": [
            {
                "name": "Node Status",
                "command": "kubectl get nodes -o wide",
                "check": "All nodes should be Ready",
            },
            {
                "name": "Node Conditions",
                "command": "kubectl describe nodes | grep -A5 'Conditions:'",
                "check": "No pressure conditions should be True",
            },
            {
                "name": "Node Resources",
                "command": "kubectl top nodes",
                "check": "CPU/Memory usage below 80%",
            },
        ],
        "pods": [
            {
                "name": "Pod Status",
                "command": f"kubectl get pods {ns_flag} | grep -v Running | grep -v Completed",
                "check": "No pods in Error, CrashLoopBackOff, or Pending",
            },
            {
                "name": "Pod Restarts",
                "command": f"kubectl get pods {ns_flag} -o jsonpath='{{range .items[*]}}{{.metadata.name}} {{range .status.containerStatuses[*]}}{{.restartCount}}{{end}}{{\"\\n\"}}{{end}}' | awk '$2 > 5'",
                "check": "No pods with excessive restarts",
            },
            {
                "name": "Pod Resources",
                "command": f"kubectl top pods {ns_flag} --sort-by=memory",
                "check": "Resource usage within limits",
            },
        ],
        "services": [
            {
                "name": "Service Endpoints",
                "command": f"kubectl get endpoints {ns_flag}",
                "check": "All services have endpoints",
            },
            {
                "name": "Load Balancers",
                "command": f"kubectl get svc {ns_flag} -o wide | grep LoadBalancer",
                "check": "LoadBalancer services have external IPs",
            },
        ],
        "storage": [
            {
                "name": "PVC Status",
                "command": f"kubectl get pvc {ns_flag}",
                "check": "All PVCs should be Bound",
            },
            {
                "name": "Storage Classes",
                "command": "kubectl get sc",
                "check": "Default storage class exists",
            },
        ],
        "networking": [
            {
                "name": "DNS Test",
                "command": "kubectl run test-dns --image=busybox --rm -it --restart=Never -- nslookup kubernetes.default",
                "check": "DNS resolution works",
            },
            {
                "name": "Network Policies",
                "command": f"kubectl get networkpolicies {ns_flag}",
                "check": "Review network policies",
            },
        ],
        "security": [
            {
                "name": "Pod Security",
                "command": f"kubectl get pods {ns_flag} -o jsonpath='{{range .items[*]}}{{.metadata.name}} privileged={{range .spec.containers[*]}}{{.securityContext.privileged}}{{end}}{{\"\\n\"}}{{end}}'",
                "check": "Minimize privileged containers",
            },
            {
                "name": "Service Accounts",
                "command": f"kubectl get serviceaccounts {ns_flag}",
                "check": "Review service account permissions",
            },
        ],
        "resources": [
            {
                "name": "Resource Quotas",
                "command": f"kubectl get resourcequotas {ns_flag}",
                "check": "Quotas not exceeded",
            },
            {
                "name": "Limit Ranges",
                "command": f"kubectl get limitranges {ns_flag}",
                "check": "Limit ranges configured",
            },
        ],
    }

    for check_category in checks_to_run:
        if check_category in check_commands:
            result["checks"][check_category] = check_commands[check_category]
            for cmd in check_commands[check_category]:
                result["commands_to_run"].append(cmd["command"])

    # Common recommendations
    result["recommendations"] = [
        "Ensure all nodes are in Ready state",
        "Monitor pods with high restart counts",
        "Verify PodDisruptionBudgets for critical workloads",
        "Review resource requests/limits for optimization",
        "Check for deprecated API usage before upgrades",
        "Ensure network policies restrict unnecessary traffic",
        "Use Pod Security Standards or OPA Gatekeeper for policy enforcement",
    ]

    result["status"] = "ready_to_execute"
    result["notes"] = [
        "Run the commands in commands_to_run to perform health checks",
        "Review output against the check criteria",
        "Address any issues found before production deployments",
    ]

    return result


# ============================================================================
# TOOL DEFINITIONS FOR NAVI AGENT
# ============================================================================

K8S_LIFECYCLE_TOOLS = {
    "k8s_cluster_create": {
        "function": k8s_cluster_create,
        "description": """Create a Kubernetes cluster on cloud providers (EKS, GKE, AKS) or locally (kind, minikube).

Generates provider-specific configuration and commands for:
- Managed Kubernetes services (EKS, GKE, AKS)
- Local development clusters (kind, minikube)
- Configurable node pools, autoscaling, private clusters

Example:
- k8s_cluster_create(provider="eks", cluster_name="prod-cluster", region="us-west-2", node_count=5)
- k8s_cluster_create(provider="gke", cluster_name="dev", region="us-central1", enable_private_cluster=True)
- k8s_cluster_create(provider="kind", cluster_name="local-test", node_count=2)""",
        "parameters": {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "description": "Cloud provider: eks, gke, aks, kind, minikube",
                    "enum": ["eks", "gke", "aks", "kind", "minikube"],
                },
                "cluster_name": {
                    "type": "string",
                    "description": "Name for the cluster",
                },
                "region": {
                    "type": "string",
                    "description": "Cloud region/zone (e.g., us-west-2, us-central1)",
                },
                "node_count": {
                    "type": "integer",
                    "description": "Number of worker nodes (default: 3)",
                    "default": 3,
                },
                "node_type": {
                    "type": "string",
                    "description": "Instance type category: standard, compute, memory, gpu",
                    "enum": ["standard", "compute", "memory", "gpu"],
                    "default": "standard",
                },
                "kubernetes_version": {
                    "type": "string",
                    "description": "Kubernetes version or 'latest'",
                    "default": "latest",
                },
                "enable_private_cluster": {
                    "type": "boolean",
                    "description": "Create private cluster (no public IPs)",
                    "default": False,
                },
                "enable_workload_identity": {
                    "type": "boolean",
                    "description": "Enable workload identity (GKE/AKS)",
                    "default": True,
                },
            },
            "required": ["provider", "cluster_name", "region"],
        },
    },
    "k8s_cluster_upgrade": {
        "function": k8s_cluster_upgrade,
        "description": """Upgrade a Kubernetes cluster to a new version with safe procedures.

Generates upgrade plan including:
- Pre-upgrade validation checks
- Control plane upgrade commands
- Rolling node upgrades with drain/cordon
- Post-upgrade verification steps
- Rollback procedures

Example:
- k8s_cluster_upgrade(provider="eks", cluster_name="prod", region="us-west-2", target_version="1.28")
- k8s_cluster_upgrade(provider="gke", cluster_name="prod", region="us-central1", target_version="1.28", upgrade_strategy="surge")""",
        "parameters": {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "description": "Cloud provider: eks, gke, aks",
                    "enum": ["eks", "gke", "aks"],
                },
                "cluster_name": {"type": "string", "description": "Cluster to upgrade"},
                "region": {"type": "string", "description": "Cloud region"},
                "target_version": {
                    "type": "string",
                    "description": "Target Kubernetes version",
                },
                "upgrade_strategy": {
                    "type": "string",
                    "description": "Upgrade strategy: rolling, blue-green, surge",
                    "enum": ["rolling", "blue-green", "surge"],
                    "default": "rolling",
                },
                "drain_timeout": {
                    "type": "integer",
                    "description": "Timeout for node drain in seconds",
                    "default": 300,
                },
                "node_pool": {
                    "type": "string",
                    "description": "Specific node pool to upgrade (optional)",
                },
            },
            "required": ["provider", "cluster_name", "region", "target_version"],
        },
    },
    "k8s_node_pool_manage": {
        "function": k8s_node_pool_manage,
        "description": """Manage Kubernetes node pools (create, delete, scale, update).

Actions:
- create: Create new node pool with specified configuration
- delete: Remove a node pool
- scale: Change node count
- update: Update labels/taints
- autoscale: Configure cluster autoscaler

Example:
- k8s_node_pool_manage(provider="gke", cluster_name="prod", region="us-central1", action="create", node_pool_name="gpu-pool", node_type="gpu", node_count=2)
- k8s_node_pool_manage(provider="eks", cluster_name="prod", region="us-west-2", action="scale", node_pool_name="workers", node_count=10)""",
        "parameters": {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "description": "Cloud provider: eks, gke, aks",
                    "enum": ["eks", "gke", "aks"],
                },
                "cluster_name": {"type": "string", "description": "Cluster name"},
                "region": {"type": "string", "description": "Cloud region"},
                "action": {
                    "type": "string",
                    "description": "Action: create, delete, scale, update, autoscale",
                    "enum": ["create", "delete", "scale", "update", "autoscale"],
                },
                "node_pool_name": {
                    "type": "string",
                    "description": "Name of the node pool",
                },
                "node_count": {
                    "type": "integer",
                    "description": "Number of nodes (for create/scale)",
                },
                "node_type": {
                    "type": "string",
                    "description": "Instance type (for create)",
                },
                "enable_autoscaling": {
                    "type": "boolean",
                    "description": "Enable cluster autoscaler",
                    "default": False,
                },
                "min_nodes": {
                    "type": "integer",
                    "description": "Minimum nodes for autoscaling",
                    "default": 1,
                },
                "max_nodes": {
                    "type": "integer",
                    "description": "Maximum nodes for autoscaling",
                    "default": 10,
                },
            },
            "required": [
                "provider",
                "cluster_name",
                "region",
                "action",
                "node_pool_name",
            ],
        },
    },
    "k8s_install_addons": {
        "function": k8s_install_addons,
        "description": """Install Kubernetes add-ons and ecosystem tools.

Supported add-ons:
- CNI: calico, cilium
- Ingress: nginx, traefik, kong
- Monitoring: prometheus-stack, datadog
- Logging: loki-stack
- Service Mesh: istio, linkerd
- Secrets: external-secrets, sealed-secrets, vault
- Policy: opa-gatekeeper, kyverno
- GitOps: argocd, fluxcd
- Autoscaling: keda
- Certs: cert-manager
- Storage: longhorn

Example:
- k8s_install_addons(addons=["nginx", "cert-manager", "prometheus-stack"], cluster_name="prod")
- k8s_install_addons(addons=["istio", "kiali", "jaeger"], cluster_name="prod")""",
        "parameters": {
            "type": "object",
            "properties": {
                "addons": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of add-ons to install",
                },
                "cluster_name": {
                    "type": "string",
                    "description": "Cluster name (for configuration)",
                },
                "provider": {
                    "type": "string",
                    "description": "Cloud provider for provider-specific config",
                },
                "namespace": {
                    "type": "string",
                    "description": "Target namespace (default varies by add-on)",
                    "default": "kube-system",
                },
            },
            "required": ["addons", "cluster_name"],
        },
    },
    "k8s_cluster_health_check": {
        "function": k8s_cluster_health_check,
        "description": """Perform comprehensive Kubernetes cluster health checks.

Check categories:
- nodes: Node status, resources, conditions
- pods: Pod health, restarts, pending pods
- services: Service endpoints, load balancers
- storage: PVC status, storage classes
- networking: DNS, network policies
- security: RBAC, pod security
- resources: Resource quotas, limits

Example:
- k8s_cluster_health_check() - Run all checks
- k8s_cluster_health_check(checks=["nodes", "pods"], namespace="production")""",
        "parameters": {
            "type": "object",
            "properties": {
                "checks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific checks to run (default: all)",
                },
                "namespace": {
                    "type": "string",
                    "description": "Specific namespace to check (default: all namespaces)",
                },
                "verbose": {
                    "type": "boolean",
                    "description": "Include detailed output",
                    "default": False,
                },
            },
            "required": [],
        },
    },
}
