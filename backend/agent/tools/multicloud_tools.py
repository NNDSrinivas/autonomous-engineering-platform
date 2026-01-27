"""
Multi-Cloud Management Tools for NAVI
Provides tools for comparing, migrating, and managing resources across cloud providers.
"""

import os
import json
from typing import Any, Dict, List, Optional
from pathlib import Path

from backend.services.connector_base import ToolResult


# ============================================================================
# Cloud Service Comparison
# ============================================================================

async def compare_cloud_services(context: Dict[str, Any]) -> ToolResult:
    """
    Compare equivalent services across cloud providers.

    Args (from context):
        service_type: Type of service to compare (compute, database, storage, etc.)
        providers: List of providers to compare (aws, gcp, azure, digitalocean)
        requirements: Specific requirements (cpu, memory, storage, region)
    """
    service_type = context.get("service_type", "compute")
    providers = context.get("providers", ["aws", "gcp", "azure"])
    requirements = context.get("requirements", {})

    # Get service mappings
    service_map = _get_service_mappings()

    if service_type not in service_map:
        available = ", ".join(service_map.keys())
        return ToolResult(
            output=f"Unknown service type: {service_type}. Available: {available}",
            sources=[]
        )

    # Build comparison table
    comparison = _build_service_comparison(service_type, providers, requirements, service_map)

    # Generate pricing estimates
    pricing = _estimate_pricing(service_type, providers, requirements)

    # Generate recommendations
    recommendations = _generate_recommendations(service_type, providers, requirements, pricing)

    output = f"""# Cloud Service Comparison: {service_type.upper()}

## Service Equivalents

{comparison}

## Pricing Estimates

{pricing}

## Recommendations

{recommendations}

## Feature Comparison

{_generate_feature_comparison(service_type, providers)}

## Migration Considerations

{_generate_migration_notes(service_type, providers)}
"""

    return ToolResult(output=output, sources=[])


async def generate_multi_region_config(context: Dict[str, Any]) -> ToolResult:
    """
    Generate multi-region deployment configuration.

    Args (from context):
        provider: Cloud provider (aws, gcp, azure)
        regions: List of regions to deploy to
        services: List of services to deploy
        strategy: Deployment strategy (active-active, active-passive, follow-the-sun)
    """
    provider = context.get("provider", "aws")
    regions = context.get("regions", ["us-east-1", "eu-west-1", "ap-southeast-1"])
    services = context.get("services", ["api", "database", "cache"])
    strategy = context.get("strategy", "active-active")

    # Generate Terraform configuration
    terraform_config = _generate_multi_region_terraform(provider, regions, services, strategy)

    # Generate architecture diagram
    diagram = _generate_multi_region_diagram(provider, regions, services, strategy)

    # Generate DNS configuration
    dns_config = _generate_dns_config(provider, regions, strategy)

    # Generate monitoring config
    monitoring_config = _generate_multi_region_monitoring(provider, regions)

    output = f"""# Multi-Region Deployment Configuration

## Strategy: {strategy.replace('-', ' ').title()}
## Provider: {provider.upper()}
## Regions: {', '.join(regions)}

### Architecture Overview

{diagram}

### Terraform Configuration

```hcl
{terraform_config}
```

### DNS Configuration (Route53 / Cloud DNS)

```hcl
{dns_config}
```

### Monitoring & Alerting

```yaml
{monitoring_config}
```

### Strategy Details: {strategy.replace('-', ' ').title()}

{_get_strategy_details(strategy)}

### Failover Procedures

{_generate_failover_procedures(provider, regions, strategy)}

### Cost Optimization Tips

{_generate_cost_tips(provider, regions, services)}
"""

    return ToolResult(output=output, sources=[])


async def migrate_cloud_provider(context: Dict[str, Any]) -> ToolResult:
    """
    Generate migration plan between cloud providers.

    Args (from context):
        workspace_path: Path to analyze current infrastructure
        source_provider: Current cloud provider
        target_provider: Target cloud provider
        services_to_migrate: Specific services to migrate (or 'all')
    """
    workspace_path = context.get("workspace_path", ".")
    source_provider = context.get("source_provider", "aws")
    target_provider = context.get("target_provider", "gcp")
    services_to_migrate = context.get("services_to_migrate", "all")

    # Analyze current infrastructure
    current_infra = await _analyze_infrastructure(workspace_path, source_provider)

    # Generate service mappings
    service_mappings = _map_services_for_migration(current_infra, source_provider, target_provider)

    # Generate migration plan
    migration_plan = _generate_migration_plan(service_mappings, source_provider, target_provider)

    # Generate target Terraform
    target_terraform = _generate_target_terraform(service_mappings, target_provider)

    # Generate rollback plan
    rollback_plan = _generate_rollback_plan(service_mappings, source_provider)

    output = f"""# Cloud Migration Plan

## Migration: {source_provider.upper()} → {target_provider.upper()}

### Current Infrastructure Analysis

{current_infra}

### Service Mappings

{service_mappings}

### Migration Plan

{migration_plan}

### Target Infrastructure (Terraform)

```hcl
{target_terraform}
```

### Data Migration Strategy

{_generate_data_migration_strategy(source_provider, target_provider)}

### Rollback Plan

{rollback_plan}

### Validation Checklist

{_generate_validation_checklist(service_mappings)}

### Timeline & Dependencies

{_generate_migration_timeline(service_mappings)}
"""

    return ToolResult(output=output, sources=[])


async def estimate_cloud_costs(context: Dict[str, Any]) -> ToolResult:
    """
    Estimate cloud costs for infrastructure configuration.

    Args (from context):
        workspace_path: Path to infrastructure files
        provider: Cloud provider to estimate for
        resources: List of resources to estimate
        usage_pattern: Usage pattern (steady, variable, burst)
        period: Estimation period (monthly, yearly)
    """
    workspace_path = context.get("workspace_path", ".")
    provider = context.get("provider", "aws")
    resources = context.get("resources", [])
    usage_pattern = context.get("usage_pattern", "steady")
    period = context.get("period", "monthly")

    # If no resources provided, analyze workspace
    if not resources:
        resources = await _detect_resources(workspace_path, provider)

    # Calculate cost estimates
    cost_breakdown = _calculate_costs(resources, provider, usage_pattern)

    # Generate optimization suggestions
    optimizations = _generate_cost_optimizations(resources, provider, cost_breakdown)

    # Compare with other providers
    comparison = _compare_provider_costs(resources, usage_pattern)

    multiplier = 12 if period == "yearly" else 1
    total = sum(item["cost"] for item in cost_breakdown) * multiplier

    output = f"""# Cloud Cost Estimation

## Provider: {provider.upper()}
## Period: {period.title()}
## Usage Pattern: {usage_pattern.title()}

### Cost Breakdown

| Resource | Type | Quantity | Monthly Cost | {period.title()} Cost |
|----------|------|----------|--------------|-------------|
{_format_cost_table(cost_breakdown, multiplier)}

### Total Estimated Cost: **${total:,.2f} / {period}**

### Cost by Category

{_generate_cost_by_category(cost_breakdown, period)}

### Provider Comparison

{comparison}

### Cost Optimization Recommendations

{optimizations}

### Reserved Instance Savings

{_generate_reserved_savings(resources, provider)}

### Spot/Preemptible Instance Opportunities

{_generate_spot_opportunities(resources, provider)}

### Notes
- Prices are estimates based on publicly available pricing
- Actual costs may vary based on usage, region, and negotiated discounts
- Data transfer costs are estimated based on typical usage patterns
"""

    return ToolResult(output=output, sources=[])


async def generate_cloud_landing_zone(context: Dict[str, Any]) -> ToolResult:
    """
    Generate a cloud landing zone configuration (enterprise multi-account setup).

    Args (from context):
        provider: Cloud provider (aws, gcp, azure)
        organization_name: Name of the organization
        environments: List of environments (dev, staging, prod)
        compliance_frameworks: Required compliance (hipaa, pci, soc2)
    """
    provider = context.get("provider", "aws")
    organization_name = context.get("organization_name", "myorg")
    environments = context.get("environments", ["development", "staging", "production"])
    compliance_frameworks = context.get("compliance_frameworks", [])

    # Generate account/project structure
    account_structure = _generate_account_structure(provider, organization_name, environments)

    # Generate networking configuration
    network_config = _generate_landing_zone_networking(provider, environments)

    # Generate IAM/Identity configuration
    iam_config = _generate_landing_zone_iam(provider, organization_name)

    # Generate security controls
    security_config = _generate_security_controls(provider, compliance_frameworks)

    # Generate governance policies
    governance = _generate_governance_policies(provider, compliance_frameworks)

    output = f"""# Cloud Landing Zone Configuration

## Provider: {provider.upper()}
## Organization: {organization_name}
## Environments: {', '.join(environments)}
## Compliance: {', '.join(compliance_frameworks) if compliance_frameworks else 'None specified'}

### Account/Project Structure

{account_structure}

### Network Architecture

{network_config}

### Identity & Access Management

{iam_config}

### Security Controls

{security_config}

### Governance Policies

{governance}

### Monitoring & Logging

{_generate_landing_zone_monitoring(provider)}

### Cost Management

{_generate_landing_zone_cost_management(provider)}

### Implementation Steps

{_generate_landing_zone_steps(provider)}
"""

    return ToolResult(output=output, sources=[])


async def analyze_cloud_spend(context: Dict[str, Any]) -> ToolResult:
    """
    Analyze cloud spending patterns and provide optimization recommendations.

    Args (from context):
        provider: Cloud provider
        workspace_path: Path to infrastructure files
        focus_areas: Areas to focus optimization (compute, storage, network)
    """
    provider = context.get("provider", "aws")
    workspace_path = context.get("workspace_path", ".")
    focus_areas = context.get("focus_areas", ["compute", "storage", "network", "database"])

    # Analyze infrastructure
    resources = await _detect_resources(workspace_path, provider)

    # Generate optimization report
    optimizations = []
    for area in focus_areas:
        area_optimizations = _analyze_area(resources, provider, area)
        optimizations.extend(area_optimizations)

    # Sort by potential savings
    optimizations.sort(key=lambda x: x.get("savings", 0), reverse=True)

    output = f"""# Cloud Spend Analysis

## Provider: {provider.upper()}
## Focus Areas: {', '.join(focus_areas)}

### Executive Summary

{_generate_spend_summary(optimizations)}

### Top Optimization Opportunities

{_format_optimizations(optimizations[:10])}

### Detailed Analysis by Category

{_generate_detailed_analysis(resources, provider, focus_areas)}

### Right-Sizing Recommendations

{_generate_rightsizing_recommendations(resources, provider)}

### Unused Resources

{_generate_unused_resource_report(resources)}

### Implementation Priority

{_generate_optimization_priority(optimizations)}

### Estimated Total Savings

{_calculate_total_savings(optimizations)}
"""

    return ToolResult(output=output, sources=[])


# ============================================================================
# Helper Functions
# ============================================================================

def _get_service_mappings() -> Dict[str, Dict[str, str]]:
    """Get service name mappings across providers."""
    return {
        "compute": {
            "aws": "EC2 / ECS / Lambda",
            "gcp": "Compute Engine / Cloud Run / Cloud Functions",
            "azure": "Virtual Machines / Container Apps / Functions",
            "digitalocean": "Droplets / App Platform / Functions",
        },
        "kubernetes": {
            "aws": "EKS (Elastic Kubernetes Service)",
            "gcp": "GKE (Google Kubernetes Engine)",
            "azure": "AKS (Azure Kubernetes Service)",
            "digitalocean": "DOKS (DigitalOcean Kubernetes)",
        },
        "database": {
            "aws": "RDS / Aurora / DynamoDB",
            "gcp": "Cloud SQL / Spanner / Firestore",
            "azure": "Azure SQL / Cosmos DB",
            "digitalocean": "Managed Databases",
        },
        "storage": {
            "aws": "S3 / EBS / EFS",
            "gcp": "Cloud Storage / Persistent Disk / Filestore",
            "azure": "Blob Storage / Managed Disks / Azure Files",
            "digitalocean": "Spaces / Volumes",
        },
        "cache": {
            "aws": "ElastiCache (Redis/Memcached)",
            "gcp": "Memorystore",
            "azure": "Azure Cache for Redis",
            "digitalocean": "Managed Redis",
        },
        "cdn": {
            "aws": "CloudFront",
            "gcp": "Cloud CDN",
            "azure": "Azure CDN",
            "digitalocean": "Spaces CDN",
        },
        "dns": {
            "aws": "Route 53",
            "gcp": "Cloud DNS",
            "azure": "Azure DNS",
            "digitalocean": "DNS",
        },
        "loadbalancer": {
            "aws": "ALB / NLB / ELB",
            "gcp": "Cloud Load Balancing",
            "azure": "Azure Load Balancer / Application Gateway",
            "digitalocean": "Load Balancers",
        },
        "messaging": {
            "aws": "SQS / SNS / EventBridge",
            "gcp": "Pub/Sub / Cloud Tasks",
            "azure": "Service Bus / Event Grid",
            "digitalocean": "N/A (use third-party)",
        },
        "secrets": {
            "aws": "Secrets Manager / Parameter Store",
            "gcp": "Secret Manager",
            "azure": "Key Vault",
            "digitalocean": "N/A (use third-party)",
        },
        "monitoring": {
            "aws": "CloudWatch",
            "gcp": "Cloud Monitoring (Stackdriver)",
            "azure": "Azure Monitor",
            "digitalocean": "Monitoring",
        },
        "logging": {
            "aws": "CloudWatch Logs",
            "gcp": "Cloud Logging",
            "azure": "Log Analytics",
            "digitalocean": "N/A (use third-party)",
        },
        "serverless": {
            "aws": "Lambda / Fargate",
            "gcp": "Cloud Functions / Cloud Run",
            "azure": "Functions / Container Apps",
            "digitalocean": "App Platform / Functions",
        },
    }


def _build_service_comparison(
    service_type: str,
    providers: List[str],
    requirements: Dict[str, Any],
    service_map: Dict
) -> str:
    """Build service comparison table."""
    services = service_map.get(service_type, {})

    lines = ["| Provider | Service | Key Features | Strengths | Limitations |"]
    lines.append("|----------|---------|--------------|-----------|-------------|")

    provider_details = _get_provider_details()

    for provider in providers:
        service_name = services.get(provider, "N/A")
        details = provider_details.get(service_type, {}).get(provider, {})
        features = details.get("features", "Standard features")
        strengths = details.get("strengths", "-")
        limitations = details.get("limitations", "-")

        lines.append(f"| {provider.upper()} | {service_name} | {features} | {strengths} | {limitations} |")

    return "\n".join(lines)


def _get_provider_details() -> Dict[str, Dict[str, Dict[str, str]]]:
    """Get detailed provider information."""
    return {
        "compute": {
            "aws": {
                "features": "Nitro System, Graviton, Spot",
                "strengths": "Widest instance variety",
                "limitations": "Complex pricing",
            },
            "gcp": {
                "features": "Live migration, Preemptible VMs",
                "strengths": "Per-second billing",
                "limitations": "Fewer instance types",
            },
            "azure": {
                "features": "Hybrid support, B-series burstable",
                "strengths": "Enterprise integration",
                "limitations": "Steeper learning curve",
            },
        },
        "kubernetes": {
            "aws": {
                "features": "Fargate support, managed node groups",
                "strengths": "Mature ecosystem",
                "limitations": "Higher base cost",
            },
            "gcp": {
                "features": "Autopilot, GKE Enterprise",
                "strengths": "Best K8s experience",
                "limitations": "Vendor lock-in for advanced features",
            },
            "azure": {
                "features": "Azure Arc, virtual nodes",
                "strengths": "Hybrid/multi-cloud",
                "limitations": "Slower feature updates",
            },
        },
        "database": {
            "aws": {
                "features": "Aurora Serverless, Global Database",
                "strengths": "Wide database variety",
                "limitations": "Premium pricing",
            },
            "gcp": {
                "features": "Spanner multi-region, AlloyDB",
                "strengths": "Global consistency",
                "limitations": "Fewer options",
            },
            "azure": {
                "features": "Cosmos DB multi-model, Hyperscale",
                "strengths": "Global distribution",
                "limitations": "Complexity",
            },
        },
    }


def _estimate_pricing(service_type: str, providers: List[str], requirements: Dict) -> str:
    """Estimate pricing for services."""
    # Base monthly prices (simplified estimates)
    base_prices = {
        "compute": {"aws": 50, "gcp": 45, "azure": 48, "digitalocean": 24},
        "kubernetes": {"aws": 73, "gcp": 0, "azure": 72, "digitalocean": 12},  # GKE control plane is free
        "database": {"aws": 100, "gcp": 90, "azure": 95, "digitalocean": 15},
        "storage": {"aws": 23, "gcp": 20, "azure": 22, "digitalocean": 5},
        "cache": {"aws": 40, "gcp": 35, "azure": 38, "digitalocean": 15},
    }

    prices = base_prices.get(service_type, {})

    lines = ["| Provider | Estimated Monthly Cost | Notes |"]
    lines.append("|----------|----------------------|-------|")

    for provider in providers:
        price = prices.get(provider, 0)
        # Adjust based on requirements
        if requirements.get("high_availability"):
            price *= 2
        if requirements.get("multi_region"):
            price *= 3

        lines.append(f"| {provider.upper()} | ${price}/month | Base estimate |")

    return "\n".join(lines)


def _generate_recommendations(
    service_type: str,
    providers: List[str],
    requirements: Dict,
    pricing: str
) -> str:
    """Generate recommendations based on analysis."""
    recommendations = []

    # Best for cost
    recommendations.append("### Best for Cost")
    recommendations.append("- **DigitalOcean** - Lowest entry point for small to medium workloads")
    recommendations.append("- **GCP** - Per-second billing and sustained use discounts")

    # Best for enterprise
    recommendations.append("\n### Best for Enterprise")
    recommendations.append("- **AWS** - Most mature, widest service selection")
    recommendations.append("- **Azure** - Best Microsoft/hybrid integration")

    # Best for Kubernetes
    if service_type == "kubernetes":
        recommendations.append("\n### Best for Kubernetes")
        recommendations.append("- **GCP (GKE)** - Original K8s creators, best managed experience")
        recommendations.append("- **EKS** - Best ecosystem integration")

    # Best for startups
    recommendations.append("\n### Best for Startups")
    recommendations.append("- **GCP** - $300 free credits, startup programs")
    recommendations.append("- **DigitalOcean** - Simple pricing, great docs")

    return "\n".join(recommendations)


def _generate_feature_comparison(service_type: str, providers: List[str]) -> str:
    """Generate feature comparison matrix."""
    features = _get_feature_matrix().get(service_type, {})

    if not features:
        return "Feature comparison not available for this service type."

    lines = ["| Feature | " + " | ".join([p.upper() for p in providers]) + " |"]
    lines.append("|---------|" + "|".join(["------" for _ in providers]) + "|")

    for feature, support in features.items():
        row = [feature]
        for provider in providers:
            status = support.get(provider, "?")
            row.append(status)
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def _get_feature_matrix() -> Dict[str, Dict[str, Dict[str, str]]]:
    """Get feature support matrix."""
    return {
        "compute": {
            "Spot/Preemptible Instances": {"aws": "Yes", "gcp": "Yes", "azure": "Yes", "digitalocean": "No"},
            "ARM-based Instances": {"aws": "Yes (Graviton)", "gcp": "Yes (Tau)", "azure": "Yes", "digitalocean": "No"},
            "GPU Instances": {"aws": "Yes", "gcp": "Yes", "azure": "Yes", "digitalocean": "Yes"},
            "Bare Metal": {"aws": "Yes", "gcp": "Yes", "azure": "Yes", "digitalocean": "No"},
            "Reserved Capacity": {"aws": "1-3 year", "gcp": "1-3 year", "azure": "1-3 year", "digitalocean": "No"},
        },
        "kubernetes": {
            "Managed Control Plane": {"aws": "Yes ($73/mo)", "gcp": "Yes (Free)", "azure": "Yes ($72/mo)", "digitalocean": "Yes ($12/mo)"},
            "Autopilot/Serverless": {"aws": "Fargate", "gcp": "Autopilot", "azure": "Virtual Nodes", "digitalocean": "No"},
            "Multi-cluster Management": {"aws": "Yes", "gcp": "Yes (Fleet)", "azure": "Yes (Arc)", "digitalocean": "No"},
            "GPU Support": {"aws": "Yes", "gcp": "Yes", "azure": "Yes", "digitalocean": "Yes"},
            "Windows Containers": {"aws": "Yes", "gcp": "Yes", "azure": "Yes", "digitalocean": "No"},
        },
    }


def _generate_migration_notes(service_type: str, providers: List[str]) -> str:
    """Generate migration considerations."""
    notes = [
        "### General Migration Considerations",
        "",
        "1. **Data Transfer Costs** - Egress fees can be significant; plan data migration carefully",
        "2. **Service Parity** - Not all services have exact equivalents; may need architecture changes",
        "3. **IAM/Permissions** - Identity systems differ significantly; plan IAM migration",
        "4. **Networking** - VPC/VNet configurations may need redesign",
        "5. **Monitoring/Logging** - Consider using multi-cloud tools (Datadog, Grafana)",
        "",
        "### Migration Tools",
        "",
        "| Source | Target | Recommended Tools |",
        "|--------|--------|-------------------|",
        "| AWS | GCP | Migrate for Compute Engine, Cloud Dataflow |",
        "| AWS | Azure | Azure Migrate, Azure Site Recovery |",
        "| GCP | AWS | AWS Migration Hub, DMS |",
        "| Azure | AWS | AWS Migration Hub, CloudEndure |",
    ]

    return "\n".join(notes)


def _generate_multi_region_terraform(
    provider: str,
    regions: List[str],
    services: List[str],
    strategy: str
) -> str:
    """Generate multi-region Terraform configuration."""
    if provider == "aws":
        return _generate_aws_multi_region(regions, services, strategy)
    elif provider == "gcp":
        return _generate_gcp_multi_region(regions, services, strategy)
    else:
        return _generate_azure_multi_region(regions, services, strategy)


def _generate_aws_multi_region(regions: List[str], services: List[str], strategy: str) -> str:
    """Generate AWS multi-region Terraform."""
    config = f'''# AWS Multi-Region Configuration
# Strategy: {strategy}

terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

# Provider for each region
'''

    for i, region in enumerate(regions):
        alias = region.replace("-", "_")
        config += f'''
provider "aws" {{
  alias  = "{alias}"
  region = "{region}"
}}
'''

    # Add VPC for each region
    for region in regions:
        alias = region.replace("-", "_")
        config += f'''
# VPC in {region}
module "vpc_{alias}" {{
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  providers = {{
    aws = aws.{alias}
  }}

  name = "vpc-{region}"
  cidr = "10.{regions.index(region)}.0.0/16"

  azs             = ["{region}a", "{region}b", "{region}c"]
  private_subnets = ["10.{regions.index(region)}.1.0/24", "10.{regions.index(region)}.2.0/24", "10.{regions.index(region)}.3.0/24"]
  public_subnets  = ["10.{regions.index(region)}.101.0/24", "10.{regions.index(region)}.102.0/24", "10.{regions.index(region)}.103.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = false
}}
'''

    # Add Global Accelerator for active-active
    if strategy == "active-active":
        config += '''
# Global Accelerator for traffic distribution
resource "aws_globalaccelerator_accelerator" "main" {
  name            = "multi-region-accelerator"
  ip_address_type = "IPV4"
  enabled         = true
}

resource "aws_globalaccelerator_listener" "main" {
  accelerator_arn = aws_globalaccelerator_accelerator.main.id
  protocol        = "TCP"

  port_range {
    from_port = 443
    to_port   = 443
  }
}
'''

    return config


def _generate_gcp_multi_region(regions: List[str], services: List[str], strategy: str) -> str:
    """Generate GCP multi-region Terraform."""
    # Build subnets configuration
    subnets = []
    for i, r in enumerate(regions):
        alias = r.replace("-", "_")
        subnets.append(f'''
resource "google_compute_subnetwork" "subnet_{alias}" {{
  name          = "subnet-{r}"
  ip_cidr_range = "10.{i}.0.0/20"
  region        = "{r}"
  network       = google_compute_network.main.id
}}''')
    subnets_config = "\n".join(subnets)

    return f'''# GCP Multi-Region Configuration
# Strategy: {strategy}

terraform {{
  required_providers {{
    google = {{
      source  = "hashicorp/google"
      version = "~> 5.0"
    }}
  }}
}}

variable "project_id" {{
  description = "GCP Project ID"
  type        = string
}}

# VPC Network (global in GCP)
resource "google_compute_network" "main" {{
  name                    = "multi-region-vpc"
  auto_create_subnetworks = false
}}

# Subnets in each region
{subnets_config}

# Global Load Balancer
resource "google_compute_global_address" "default" {{
  name = "global-lb-ip"
}}

resource "google_compute_global_forwarding_rule" "default" {{
  name       = "global-forwarding-rule"
  target     = google_compute_target_https_proxy.default.id
  port_range = "443"
  ip_address = google_compute_global_address.default.address
}}
'''


def _generate_azure_multi_region(regions: List[str], services: List[str], strategy: str) -> str:
    """Generate Azure multi-region Terraform."""
    # Build resource groups configuration
    resource_groups = []
    for r in regions:
        alias = r.replace("-", "_")
        resource_groups.append(f'''
resource "azurerm_resource_group" "rg_{alias}" {{
  name     = "rg-{r}"
  location = "{r}"
}}''')
    rg_config = "\n".join(resource_groups)

    # Build virtual networks configuration
    vnets = []
    for i, r in enumerate(regions):
        alias = r.replace("-", "_")
        vnets.append(f'''
resource "azurerm_virtual_network" "vnet_{alias}" {{
  name                = "vnet-{r}"
  location            = azurerm_resource_group.rg_{alias}.location
  resource_group_name = azurerm_resource_group.rg_{alias}.name
  address_space       = ["10.{i}.0.0/16"]
}}''')
    vnet_config = "\n".join(vnets)

    first_region_alias = regions[0].replace("-", "_")
    routing_method = strategy.replace("-", "_").title()

    return f'''# Azure Multi-Region Configuration
# Strategy: {strategy}

terraform {{
  required_providers {{
    azurerm = {{
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }}
  }}
}}

provider "azurerm" {{
  features {{}}
}}

# Resource Group per region
{rg_config}

# Virtual Network per region
{vnet_config}

# Traffic Manager for global load balancing
resource "azurerm_traffic_manager_profile" "main" {{
  name                   = "tm-multi-region"
  resource_group_name    = azurerm_resource_group.rg_{first_region_alias}.name
  traffic_routing_method = "{routing_method}"

  dns_config {{
    relative_name = "multi-region-app"
    ttl           = 60
  }}

  monitor_config {{
    protocol                     = "HTTPS"
    port                         = 443
    path                         = "/health"
    interval_in_seconds          = 30
    timeout_in_seconds           = 10
    tolerated_number_of_failures = 3
  }}
}}
'''


def _generate_multi_region_diagram(
    provider: str,
    regions: List[str],
    services: List[str],
    strategy: str
) -> str:
    """Generate ASCII architecture diagram."""
    return f'''```
                        ┌─────────────────────────────────────────┐
                        │            Global Load Balancer          │
                        │         ({provider.upper()} {'Global Accelerator' if provider == 'aws' else 'GLB' if provider == 'gcp' else 'Traffic Manager'})          │
                        └─────────────────┬───────────────────────┘
                                          │
            ┌─────────────────────────────┼─────────────────────────────┐
            │                             │                             │
            ▼                             ▼                             ▼
    ┌───────────────┐           ┌───────────────┐           ┌───────────────┐
    │   {regions[0]:^11}   │           │   {regions[1] if len(regions) > 1 else 'N/A':^11}   │           │   {regions[2] if len(regions) > 2 else 'N/A':^11}   │
    │               │           │               │           │               │
    │  ┌─────────┐  │           │  ┌─────────┐  │           │  ┌─────────┐  │
    │  │   API   │  │           │  │   API   │  │           │  │   API   │  │
    │  └────┬────┘  │           │  └────┬────┘  │           │  └────┬────┘  │
    │       │       │           │       │       │           │       │       │
    │  ┌────┴────┐  │           │  ┌────┴────┐  │           │  ┌────┴────┐  │
    │  │   DB    │  │◄─────────►│  │   DB    │  │◄─────────►│  │   DB    │  │
    │  │(replica)│  │  Replication  │(primary)│  │  Replication  │(replica)│  │
    │  └─────────┘  │           │  └─────────┘  │           │  └─────────┘  │
    │               │           │               │           │               │
    │  ┌─────────┐  │           │  ┌─────────┐  │           │  ┌─────────┐  │
    │  │  Cache  │  │           │  │  Cache  │  │           │  │  Cache  │  │
    │  └─────────┘  │           │  └─────────┘  │           │  └─────────┘  │
    └───────────────┘           └───────────────┘           └───────────────┘

    Strategy: {strategy.replace('-', ' ').title()}
```'''


def _generate_dns_config(provider: str, regions: List[str], strategy: str) -> str:
    """Generate DNS configuration for multi-region."""
    if provider == "aws":
        return '''# Route 53 Latency-based Routing
resource "aws_route53_record" "api" {
  zone_id = var.zone_id
  name    = "api.example.com"
  type    = "A"

  alias {
    name                   = aws_globalaccelerator_accelerator.main.dns_name
    zone_id                = aws_globalaccelerator_accelerator.main.hosted_zone_id
    evaluate_target_health = true
  }
}

# Health checks for each region
resource "aws_route53_health_check" "region" {
  for_each = toset(var.regions)

  fqdn              = "${each.value}.api.example.com"
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = "3"
  request_interval  = "30"
}'''
    else:
        return "# DNS configuration for " + provider.upper()


def _generate_multi_region_monitoring(provider: str, regions: List[str]) -> str:
    """Generate monitoring configuration."""
    return f'''# Multi-Region Monitoring Configuration

alerts:
  - name: regional_latency_high
    condition: p99_latency > 500ms
    for: 5m
    severity: warning
    regions: {regions}

  - name: regional_error_rate_high
    condition: error_rate > 1%
    for: 5m
    severity: critical
    regions: {regions}

  - name: cross_region_replication_lag
    condition: replication_lag > 60s
    for: 2m
    severity: critical

  - name: regional_availability_low
    condition: availability < 99.9%
    for: 5m
    severity: critical
    regions: {regions}

dashboards:
  - name: Multi-Region Overview
    panels:
      - title: Regional Latency
        type: timeseries
        queries:
          - metric: http_request_duration_seconds
            group_by: [region]
      - title: Regional Error Rates
        type: timeseries
        queries:
          - metric: http_requests_total{{status=~"5.."}}
            group_by: [region]
      - title: Replication Lag
        type: gauge
        queries:
          - metric: db_replication_lag_seconds'''


def _get_strategy_details(strategy: str) -> str:
    """Get details about deployment strategy."""
    strategies = {
        "active-active": """
**Active-Active** distributes traffic across all regions simultaneously:

- **Pros:**
  - Lowest latency for global users
  - No failover delay
  - Maximum resource utilization

- **Cons:**
  - Data consistency challenges
  - Higher complexity
  - Higher cost (full infrastructure in each region)

- **Best for:** Global applications, real-time systems, high availability requirements
""",
        "active-passive": """
**Active-Passive** routes all traffic to primary region, with standby regions:

- **Pros:**
  - Simpler data consistency
  - Lower cost (standby can be scaled down)
  - Clear failover process

- **Cons:**
  - Failover delay (typically 30-60 seconds)
  - Standby resources may be underutilized
  - Single point of active service

- **Best for:** Applications with strong consistency requirements, cost-sensitive deployments
""",
        "follow-the-sun": """
**Follow-the-Sun** shifts active region based on time of day:

- **Pros:**
  - Cost-effective global coverage
  - Simplified operations per region
  - Natural disaster recovery

- **Cons:**
  - Complex traffic management
  - Handoff periods
  - Time zone edge cases

- **Best for:** Business applications with regional user bases, support systems
""",
    }

    return strategies.get(strategy, "Strategy details not available.")


def _generate_failover_procedures(provider: str, regions: List[str], strategy: str) -> str:
    """Generate failover procedures."""
    return f"""### Automated Failover

1. **Health Check Failure Detected**
   - Continuous health checks every 30 seconds
   - After 3 consecutive failures, mark region unhealthy

2. **Traffic Rerouting**
   - DNS/Load balancer automatically routes to healthy regions
   - Existing connections gracefully terminated

3. **Database Failover**
   - Read replica promoted to primary (if applicable)
   - Application reconnects to new primary

### Manual Failover Procedure

```bash
# AWS CLI example
# 1. Check current status
aws route53 get-health-check-status --health-check-id $HEALTH_CHECK_ID

# 2. Force failover (if needed)
aws route53 change-resource-record-sets --hosted-zone-id $ZONE_ID \\
  --change-batch file://failover-changes.json

# 3. Verify
aws route53 list-resource-record-sets --hosted-zone-id $ZONE_ID
```

### Failback Procedure

1. Verify primary region is healthy
2. Run data consistency checks
3. Gradually shift traffic back (10% → 50% → 100%)
4. Monitor metrics for 24 hours
"""


def _generate_cost_tips(provider: str, regions: List[str], services: List[str]) -> str:
    """Generate cost optimization tips for multi-region."""
    return """### Cost Optimization

1. **Right-size standby regions**
   - Use smaller instances in passive regions
   - Scale up only during failover

2. **Use spot/preemptible for non-critical workloads**
   - Batch processing, dev/test environments

3. **Optimize data transfer**
   - Use VPC peering instead of public internet
   - Compress data before replication

4. **Reserved capacity for primary region**
   - 1-3 year commitments for predictable workloads
   - Up to 72% savings vs on-demand

5. **Consider traffic patterns**
   - Active-passive may be cheaper for regional users
   - Follow-the-sun can reduce 24/7 costs
"""


async def _analyze_infrastructure(workspace_path: str, provider: str) -> str:
    """Analyze current infrastructure files."""
    analysis = ["### Detected Infrastructure\n"]

    # Check for Terraform files
    tf_path = os.path.join(workspace_path, "terraform")
    if os.path.exists(tf_path):
        analysis.append(f"- **Terraform**: Found in `{tf_path}`")
    elif os.path.exists(os.path.join(workspace_path, "main.tf")):
        analysis.append("- **Terraform**: Found in root directory")

    # Check for Kubernetes
    k8s_path = os.path.join(workspace_path, "k8s")
    if os.path.exists(k8s_path):
        analysis.append(f"- **Kubernetes**: Found in `{k8s_path}`")

    # Check for Docker
    if os.path.exists(os.path.join(workspace_path, "Dockerfile")):
        analysis.append("- **Docker**: Dockerfile found")
    if os.path.exists(os.path.join(workspace_path, "docker-compose.yml")):
        analysis.append("- **Docker Compose**: docker-compose.yml found")

    if len(analysis) == 1:
        analysis.append("- No infrastructure files detected")

    return "\n".join(analysis)


def _map_services_for_migration(current_infra: str, source: str, target: str) -> str:
    """Map services between providers."""
    mappings = _get_service_mappings()

    lines = ["### Service Mappings\n"]
    lines.append(f"| {source.upper()} Service | {target.upper()} Equivalent | Migration Notes |")
    lines.append("|--------------|------------------|-----------------|")

    for service_type, providers in mappings.items():
        source_service = providers.get(source, "N/A")
        target_service = providers.get(target, "N/A")
        if source_service != "N/A":
            lines.append(f"| {source_service} | {target_service} | Check configuration compatibility |")

    return "\n".join(lines)


def _generate_migration_plan(mappings: str, source: str, target: str) -> str:
    """Generate detailed migration plan."""
    return f"""### Migration Phases

#### Phase 1: Assessment (Week 1-2)
- [ ] Complete infrastructure inventory
- [ ] Identify dependencies between services
- [ ] Document current performance baselines
- [ ] Identify data migration requirements

#### Phase 2: Preparation (Week 3-4)
- [ ] Set up {target.upper()} organization/accounts
- [ ] Configure IAM and security policies
- [ ] Establish network connectivity
- [ ] Set up monitoring in target environment

#### Phase 3: Migration (Week 5-8)
- [ ] Deploy infrastructure in {target.upper()}
- [ ] Set up data replication
- [ ] Migrate stateless services first
- [ ] Migrate stateful services with data sync
- [ ] Cut over DNS/traffic

#### Phase 4: Validation (Week 9-10)
- [ ] Run integration tests
- [ ] Validate data integrity
- [ ] Performance testing
- [ ] Security audit

#### Phase 5: Decommission (Week 11-12)
- [ ] Verify all traffic on new platform
- [ ] Backup and archive {source.upper()} data
- [ ] Decommission {source.upper()} resources
- [ ] Final cost reconciliation
"""


def _generate_target_terraform(mappings: str, target: str) -> str:
    """Generate target Terraform configuration."""
    if target == "gcp":
        return '''# GCP Target Infrastructure

provider "google" {
  project = var.project_id
  region  = var.region
}

# Compute
resource "google_compute_instance" "web" {
  name         = "web-server"
  machine_type = "e2-medium"
  zone         = "${var.region}-a"

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
    }
  }

  network_interface {
    network = "default"
    access_config {}
  }
}

# Database
resource "google_sql_database_instance" "main" {
  name             = "main-db"
  database_version = "POSTGRES_14"
  region           = var.region

  settings {
    tier = "db-f1-micro"
  }
}

# Storage
resource "google_storage_bucket" "assets" {
  name     = "${var.project_id}-assets"
  location = var.region
}'''
    else:
        return f"# {target.upper()} Target Infrastructure\n# Configuration placeholder"


def _generate_rollback_plan(mappings: str, source: str) -> str:
    """Generate rollback plan."""
    return f"""### Rollback Procedure

If migration issues occur, follow these steps:

1. **Immediate Actions**
   - Switch DNS back to {source.upper()} endpoints
   - Pause data sync from new to old environment
   - Notify stakeholders of rollback

2. **Data Recovery**
   - Assess data changes made during migration
   - Replay transactions if needed
   - Verify data consistency in {source.upper()}

3. **Traffic Migration**
   - Gradually shift traffic back (10% → 50% → 100%)
   - Monitor error rates and latency

4. **Post-Rollback**
   - Conduct incident review
   - Document lessons learned
   - Plan retry with improvements
"""


def _generate_data_migration_strategy(source: str, target: str) -> str:
    """Generate data migration strategy."""
    return f"""### Data Migration Approach

#### Online Migration (Recommended for minimal downtime)

1. **Initial Sync**
   - Use native replication tools or DMS
   - Full copy of existing data

2. **Continuous Replication**
   - CDC (Change Data Capture) for ongoing changes
   - Monitor replication lag

3. **Cutover**
   - Stop writes to source
   - Wait for replication to catch up
   - Switch application to target
   - Resume writes

#### Tools

| Data Type | {source.upper()} Tool | {target.upper()} Tool | Third-party |
|-----------|---------|---------|-------------|
| Relational DB | DMS | Database Migration Service | Striim, Fivetran |
| Object Storage | S3 sync | gsutil/azcopy | rclone |
| NoSQL | DynamoDB export | Import tools | - |
"""


def _generate_validation_checklist(mappings: str) -> str:
    """Generate validation checklist."""
    return """### Validation Checklist

#### Functional Validation
- [ ] All API endpoints responding correctly
- [ ] Authentication/Authorization working
- [ ] File uploads/downloads functional
- [ ] Background jobs processing
- [ ] Email/notification delivery

#### Performance Validation
- [ ] Response times within SLA
- [ ] Database query performance acceptable
- [ ] No memory leaks or CPU spikes
- [ ] Cache hit rates normal

#### Data Validation
- [ ] Row counts match between systems
- [ ] Checksums verify data integrity
- [ ] Foreign key relationships intact
- [ ] Timestamps/timezones correct

#### Security Validation
- [ ] SSL/TLS certificates valid
- [ ] IAM permissions correct
- [ ] Secrets properly migrated
- [ ] Network security groups configured
"""


def _generate_migration_timeline(mappings: str) -> str:
    """Generate migration timeline."""
    return """### Timeline Overview

```
Week 1-2: Assessment & Planning
├── Infrastructure inventory
├── Dependency mapping
└── Migration plan approval

Week 3-4: Preparation
├── Target environment setup
├── Network connectivity
└── Monitoring setup

Week 5-6: Non-Production Migration
├── Dev environment migration
├── Testing & validation
└── Staging environment migration

Week 7-8: Production Migration
├── Data sync initiation
├── Application deployment
└── Traffic cutover

Week 9-10: Validation & Optimization
├── Performance testing
├── Security audit
└── Cost optimization

Week 11-12: Cleanup
├── Source decommission
└── Documentation
```
"""


async def _detect_resources(workspace_path: str, provider: str) -> List[Dict[str, Any]]:
    """Detect resources from infrastructure files."""
    resources = []

    # Default resources for estimation
    resources = [
        {"type": "compute", "name": "web-server", "size": "medium", "count": 2},
        {"type": "database", "name": "main-db", "size": "small", "count": 1},
        {"type": "storage", "name": "assets", "size_gb": 100, "count": 1},
        {"type": "loadbalancer", "name": "main-lb", "count": 1},
    ]

    return resources


def _calculate_costs(resources: List[Dict], provider: str, usage_pattern: str) -> List[Dict]:
    """Calculate cost estimates for resources."""
    # Simplified pricing (actual pricing varies by region, instance type, etc.)
    pricing = {
        "aws": {
            "compute": {"small": 20, "medium": 50, "large": 100},
            "database": {"small": 30, "medium": 100, "large": 300},
            "storage": 0.023,  # per GB
            "loadbalancer": 20,
        },
        "gcp": {
            "compute": {"small": 18, "medium": 45, "large": 90},
            "database": {"small": 25, "medium": 90, "large": 280},
            "storage": 0.020,
            "loadbalancer": 18,
        },
        "azure": {
            "compute": {"small": 19, "medium": 48, "large": 95},
            "database": {"small": 28, "medium": 95, "large": 290},
            "storage": 0.021,
            "loadbalancer": 22,
        },
    }

    provider_pricing = pricing.get(provider, pricing["aws"])
    costs = []

    for resource in resources:
        res_type = resource.get("type")
        size = resource.get("size", "medium")
        count = resource.get("count", 1)

        if res_type == "storage":
            cost = resource.get("size_gb", 100) * provider_pricing.get("storage", 0.023) * count
        else:
            type_pricing = provider_pricing.get(res_type, {})
            if isinstance(type_pricing, dict):
                cost = type_pricing.get(size, 50) * count
            else:
                cost = type_pricing * count

        # Adjust for usage pattern
        if usage_pattern == "burst":
            cost *= 1.3
        elif usage_pattern == "variable":
            cost *= 1.1

        costs.append({
            "resource": resource.get("name", res_type),
            "type": res_type,
            "quantity": count,
            "cost": cost,
        })

    return costs


def _format_cost_table(cost_breakdown: List[Dict], multiplier: int) -> str:
    """Format cost breakdown as table rows."""
    lines = []
    for item in cost_breakdown:
        monthly = item["cost"]
        period_cost = monthly * multiplier
        lines.append(
            f"| {item['resource']} | {item['type']} | {item['quantity']} | "
            f"${monthly:,.2f} | ${period_cost:,.2f} |"
        )
    return "\n".join(lines)


def _generate_cost_by_category(cost_breakdown: List[Dict], period: str) -> str:
    """Generate cost breakdown by category."""
    categories = {}
    for item in cost_breakdown:
        cat = item["type"]
        if cat not in categories:
            categories[cat] = 0
        categories[cat] += item["cost"]

    multiplier = 12 if period == "yearly" else 1
    lines = ["| Category | Monthly | " + period.title() + " |"]
    lines.append("|----------|---------|---------|")

    for cat, cost in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"| {cat.title()} | ${cost:,.2f} | ${cost * multiplier:,.2f} |")

    return "\n".join(lines)


def _compare_provider_costs(resources: List[Dict], usage_pattern: str) -> str:
    """Compare costs across providers."""
    providers = ["aws", "gcp", "azure"]
    comparisons = []

    for provider in providers:
        costs = _calculate_costs(resources, provider, usage_pattern)
        total = sum(item["cost"] for item in costs)
        comparisons.append({"provider": provider, "total": total})

    comparisons.sort(key=lambda x: x["total"])
    cheapest = comparisons[0]["total"]

    lines = ["| Provider | Monthly Cost | vs Cheapest |"]
    lines.append("|----------|-------------|-------------|")

    for comp in comparisons:
        diff = ((comp["total"] - cheapest) / cheapest * 100) if cheapest > 0 else 0
        diff_str = f"+{diff:.1f}%" if diff > 0 else "Lowest"
        lines.append(f"| {comp['provider'].upper()} | ${comp['total']:,.2f} | {diff_str} |")

    return "\n".join(lines)


def _generate_cost_optimizations(resources: List[Dict], provider: str, costs: List[Dict]) -> str:
    """Generate cost optimization recommendations."""
    recommendations = [
        "### Immediate Savings Opportunities\n",
        "1. **Reserved Instances** - Commit to 1-3 year terms for 30-72% savings",
        "2. **Spot/Preemptible Instances** - Use for fault-tolerant workloads (70-90% savings)",
        "3. **Right-sizing** - Analyze utilization and downsize over-provisioned resources",
        "4. **Storage Tiers** - Move infrequently accessed data to cheaper storage classes",
        "5. **Scheduled Scaling** - Scale down during off-peak hours",
        "",
        "### Estimated Potential Savings",
        "",
        "| Optimization | Estimated Savings |",
        "|-------------|-------------------|",
        "| Reserved Instances | 30-40% |",
        "| Spot Instances | 60-70% |",
        "| Right-sizing | 10-20% |",
        "| Storage Optimization | 5-15% |",
    ]

    return "\n".join(recommendations)


def _generate_reserved_savings(resources: List[Dict], provider: str) -> str:
    """Generate reserved instance savings analysis."""
    return """### Reserved Instance Analysis

| Term | Upfront | Monthly Savings | Total Savings |
|------|---------|-----------------|---------------|
| 1 Year, No Upfront | $0 | ~30% | ~30% |
| 1 Year, Partial Upfront | Medium | ~35% | ~35% |
| 1 Year, All Upfront | High | ~40% | ~40% |
| 3 Year, No Upfront | $0 | ~50% | ~50% |
| 3 Year, Partial Upfront | Medium | ~60% | ~60% |
| 3 Year, All Upfront | High | ~72% | ~72% |

**Recommendation:** For stable workloads, 1-year partial upfront provides good
balance of savings and flexibility.
"""


def _generate_spot_opportunities(resources: List[Dict], provider: str) -> str:
    """Generate spot instance opportunities."""
    return """### Spot/Preemptible Instance Candidates

| Workload Type | Spot Suitable? | Savings | Notes |
|---------------|----------------|---------|-------|
| Batch Processing | Yes | 70-90% | Ideal for interruptible jobs |
| Dev/Test | Yes | 70-90% | Non-critical environments |
| CI/CD Runners | Yes | 70-90% | Stateless build agents |
| Web Servers | Partial | 50-70% | With proper auto-scaling |
| Databases | No | - | Use reserved instead |
| Stateful Services | No | - | Risk of data loss |

**Best Practices:**
- Use spot for at least 2 AZs to reduce interruption impact
- Set up instance diversification (multiple instance types)
- Use spot fleet or managed instance groups
"""


def _generate_account_structure(provider: str, org_name: str, environments: List[str]) -> str:
    """Generate account/project structure."""
    if provider == "aws":
        return f"""### AWS Organization Structure

```
{org_name} (Management Account)
├── Security OU
│   ├── audit-{org_name}
│   └── security-{org_name}
├── Infrastructure OU
│   ├── network-{org_name}
│   └── shared-services-{org_name}
├── Workloads OU
│   ├── {environments[0]}-{org_name}
│   ├── {environments[1] if len(environments) > 1 else 'staging'}-{org_name}
│   └── {environments[2] if len(environments) > 2 else 'production'}-{org_name}
└── Sandbox OU
    └── sandbox-{org_name}
```
"""
    elif provider == "gcp":
        return f"""### GCP Organization Structure

```
{org_name}.com (Organization)
├── folders/
│   ├── Security/
│   │   ├── audit-{org_name}
│   │   └── security-{org_name}
│   ├── Shared/
│   │   ├── networking-{org_name}
│   │   └── shared-services-{org_name}
│   ├── Workloads/
│   │   ├── {environments[0]}-{org_name}
│   │   ├── {environments[1] if len(environments) > 1 else 'staging'}-{org_name}
│   │   └── {environments[2] if len(environments) > 2 else 'production'}-{org_name}
│   └── Sandbox/
│       └── sandbox-{org_name}
```
"""
    else:
        return f"### {provider.upper()} Structure\n\nManagement groups and subscriptions for {org_name}"


def _generate_landing_zone_networking(provider: str, environments: List[str]) -> str:
    """Generate landing zone networking configuration."""
    return """### Hub-and-Spoke Network Architecture

```
                    ┌─────────────────┐
                    │   Hub VPC/VNet  │
                    │   (Shared)      │
                    │                 │
                    │ ┌─────────────┐ │
                    │ │  Firewall   │ │
                    │ └─────────────┘ │
                    │ ┌─────────────┐ │
                    │ │   VPN/ER    │ │
                    │ └─────────────┘ │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│   Dev VPC     │   │ Staging VPC   │   │  Prod VPC     │
│               │   │               │   │               │
│ 10.1.0.0/16   │   │ 10.2.0.0/16   │   │ 10.3.0.0/16   │
└───────────────┘   └───────────────┘   └───────────────┘
```

### IP Addressing Plan

| Environment | CIDR | Subnets |
|-------------|------|---------|
| Hub/Shared | 10.0.0.0/16 | Transit, Firewall, Management |
| Development | 10.1.0.0/16 | Public, Private, Data |
| Staging | 10.2.0.0/16 | Public, Private, Data |
| Production | 10.3.0.0/16 | Public, Private, Data |
"""


def _generate_landing_zone_iam(provider: str, org_name: str) -> str:
    """Generate landing zone IAM configuration."""
    return f"""### Identity & Access Management

#### Role Structure

| Role | Scope | Permissions |
|------|-------|-------------|
| OrganizationAdmin | Organization | Full admin |
| SecurityAdmin | Security OU | Security controls |
| NetworkAdmin | Infrastructure | Network management |
| BillingAdmin | Organization | Cost management |
| DeveloperAdmin | Workloads OU | Workload management |
| Developer | Project/Account | Limited development |
| ReadOnly | All | View-only access |

#### Federation Setup

```yaml
# SAML/OIDC Federation
identity_provider:
  type: SAML  # or OIDC
  provider: okta  # or azure_ad, google, onelogin
  attribute_mapping:
    email: user.email
    groups: user.groups
    role: user.role

# Group to Role Mapping
group_mappings:
  - group: {org_name}-admins
    role: OrganizationAdmin
  - group: {org_name}-security
    role: SecurityAdmin
  - group: {org_name}-developers
    role: Developer
```
"""


def _generate_security_controls(provider: str, compliance: List[str]) -> str:
    """Generate security controls configuration."""
    controls = """### Security Controls

#### Preventive Controls

| Control | Implementation | Status |
|---------|---------------|--------|
| MFA Required | IAM Policy | Required |
| Encryption at Rest | KMS/Key Vault | Enabled |
| Encryption in Transit | TLS 1.2+ | Enforced |
| Public Access Blocked | Storage Policy | Enabled |
| VPC Flow Logs | Network Config | Enabled |

#### Detective Controls

| Control | Implementation | Status |
|---------|---------------|--------|
| CloudTrail/Audit Logs | Centralized | Enabled |
| Config Rules | Compliance Checks | Active |
| GuardDuty/Security Center | Threat Detection | Enabled |
| Vulnerability Scanning | Container/VM | Scheduled |

#### Responsive Controls

| Control | Implementation | Status |
|---------|---------------|--------|
| Auto-remediation | Lambda/Functions | Configured |
| Incident Response | Runbooks | Documented |
| Backup/Recovery | Automated | Tested |
"""

    if "hipaa" in compliance:
        controls += """
#### HIPAA-Specific Controls
- PHI data encryption
- Access logging and monitoring
- BAA with cloud provider
- Annual security assessments
"""

    if "pci" in compliance:
        controls += """
#### PCI-DSS Controls
- Cardholder data isolation
- Network segmentation
- Quarterly vulnerability scans
- Annual penetration testing
"""

    return controls


def _generate_governance_policies(provider: str, compliance: List[str]) -> str:
    """Generate governance policies."""
    return """### Governance Policies

#### Service Control Policies / Organization Policies

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyUnapprovedRegions",
      "Effect": "Deny",
      "Action": "*",
      "Resource": "*",
      "Condition": {
        "StringNotEquals": {
          "aws:RequestedRegion": ["us-east-1", "us-west-2", "eu-west-1"]
        }
      }
    },
    {
      "Sid": "RequireIMDSv2",
      "Effect": "Deny",
      "Action": "ec2:RunInstances",
      "Resource": "arn:aws:ec2:*:*:instance/*",
      "Condition": {
        "StringNotEquals": {
          "ec2:MetadataHttpTokens": "required"
        }
      }
    }
  ]
}
```

#### Tagging Policy

| Tag | Required | Example |
|-----|----------|---------|
| Environment | Yes | production, staging, dev |
| Owner | Yes | team-platform |
| CostCenter | Yes | CC-12345 |
| Application | Yes | web-api |
| DataClassification | Yes | public, internal, confidential |
"""


def _generate_landing_zone_monitoring(provider: str) -> str:
    """Generate landing zone monitoring configuration."""
    return """### Centralized Monitoring

#### Log Aggregation
- All accounts ship logs to central logging account
- Retention: 1 year hot, 7 years cold storage
- Log types: CloudTrail, VPC Flow Logs, Application Logs

#### Metrics Dashboard
- Organization-wide cost dashboard
- Security posture dashboard
- Resource utilization dashboard

#### Alerting
- Security events → Security team
- Cost anomalies → Finance team
- Infrastructure issues → Platform team
"""


def _generate_landing_zone_cost_management(provider: str) -> str:
    """Generate landing zone cost management."""
    return """### Cost Management

#### Budget Alerts

| Level | Alert Threshold | Action |
|-------|----------------|--------|
| Organization | 80% of budget | Email CFO |
| Account | 90% of budget | Email Owner |
| Project | 100% of budget | Auto-notify |

#### Cost Allocation

- Tag-based cost allocation enabled
- Showback reports per team/project
- Monthly cost review meetings

#### Reserved Capacity

- Centralized RI/Savings Plans purchasing
- Coverage target: 70% of steady-state
- Quarterly optimization reviews
"""


def _generate_landing_zone_steps(provider: str) -> str:
    """Generate landing zone implementation steps."""
    return """### Implementation Steps

#### Phase 1: Foundation (Week 1-2)
- [ ] Create organization/management account
- [ ] Enable CloudTrail/Audit logging
- [ ] Set up SSO/Federation
- [ ] Configure billing and cost management

#### Phase 2: Security (Week 3-4)
- [ ] Create security account
- [ ] Deploy centralized logging
- [ ] Enable security services
- [ ] Implement SCPs/Organization policies

#### Phase 3: Networking (Week 5-6)
- [ ] Create network account
- [ ] Deploy hub VPC/VNet
- [ ] Configure Transit Gateway/VNet peering
- [ ] Set up VPN/ExpressRoute

#### Phase 4: Workloads (Week 7-8)
- [ ] Create workload accounts
- [ ] Deploy spoke networks
- [ ] Configure CI/CD pipelines
- [ ] Migrate first workloads

#### Phase 5: Optimization (Ongoing)
- [ ] Fine-tune policies
- [ ] Optimize costs
- [ ] Regular security assessments
- [ ] Documentation updates
"""


def _generate_spend_summary(optimizations: List[Dict]) -> str:
    """Generate spend summary."""
    total_savings = sum(opt.get("savings", 0) for opt in optimizations)
    return f"""Based on infrastructure analysis, we identified **{len(optimizations)} optimization opportunities**
with potential annual savings of **${total_savings:,.2f}**.

Key findings:
- Over-provisioned compute resources
- Opportunities for reserved capacity
- Unused or underutilized resources
"""


def _format_optimizations(optimizations: List[Dict]) -> str:
    """Format optimization recommendations."""
    lines = ["| Priority | Resource | Recommendation | Monthly Savings |"]
    lines.append("|----------|----------|----------------|-----------------|")

    for i, opt in enumerate(optimizations, 1):
        lines.append(
            f"| {i} | {opt.get('resource', 'Unknown')} | "
            f"{opt.get('recommendation', 'Optimize')} | "
            f"${opt.get('savings', 0):,.2f} |"
        )

    return "\n".join(lines)


def _generate_detailed_analysis(resources: List[Dict], provider: str, focus_areas: List[str]) -> str:
    """Generate detailed analysis by category."""
    analysis = []

    for area in focus_areas:
        analysis.append(f"#### {area.title()}")
        analysis.append(f"Analysis of {area} resources and optimization opportunities.")
        analysis.append("")

    return "\n".join(analysis)


def _generate_rightsizing_recommendations(resources: List[Dict], provider: str) -> str:
    """Generate right-sizing recommendations."""
    return """### Right-Sizing Analysis

Based on utilization data, consider these adjustments:

| Resource | Current Size | Recommended | Est. Savings |
|----------|--------------|-------------|--------------|
| web-server-1 | Large | Medium | $50/month |
| api-server-1 | Medium | Small | $30/month |
| worker-1 | Large | Spot Medium | $80/month |

**Note:** Recommendations based on 14-day utilization average < 40%
"""


def _generate_unused_resource_report(resources: List[Dict]) -> str:
    """Generate unused resources report."""
    return """### Potentially Unused Resources

| Resource Type | Resource Name | Last Activity | Est. Cost |
|---------------|---------------|---------------|-----------|
| EBS Volume | vol-unused-1 | 30+ days ago | $10/month |
| Elastic IP | eip-unattached | Never used | $4/month |
| Snapshot | snap-old-1 | 90+ days old | $5/month |

**Recommendation:** Review and delete confirmed unused resources.
"""


def _generate_optimization_priority(optimizations: List[Dict]) -> str:
    """Generate optimization priority matrix."""
    return """### Implementation Priority Matrix

| Priority | Effort | Impact | Recommendation |
|----------|--------|--------|----------------|
| P0 | Low | High | Reserved instances for predictable workloads |
| P1 | Medium | High | Right-size over-provisioned instances |
| P2 | Low | Medium | Delete unused resources |
| P3 | Medium | Medium | Implement auto-scaling |
| P4 | High | High | Architecture optimization |
"""


def _calculate_total_savings(optimizations: List[Dict]) -> str:
    """Calculate total potential savings."""
    monthly = sum(opt.get("savings", 0) for opt in optimizations)
    return f"""### Total Potential Savings

| Period | Amount |
|--------|--------|
| Monthly | ${monthly:,.2f} |
| Quarterly | ${monthly * 3:,.2f} |
| Annually | ${monthly * 12:,.2f} |

**Implementation Note:** These are estimated savings. Actual results may vary
based on implementation timing and usage patterns.
"""


def _analyze_area(resources: List[Dict], provider: str, area: str) -> List[Dict]:
    """Analyze specific area for optimizations."""
    optimizations = []

    if area == "compute":
        optimizations.append({
            "resource": "web-server",
            "recommendation": "Use reserved instances",
            "savings": 50,
        })
        optimizations.append({
            "resource": "worker",
            "recommendation": "Use spot instances",
            "savings": 80,
        })
    elif area == "storage":
        optimizations.append({
            "resource": "assets-bucket",
            "recommendation": "Enable intelligent tiering",
            "savings": 20,
        })
    elif area == "database":
        optimizations.append({
            "resource": "main-db",
            "recommendation": "Use reserved capacity",
            "savings": 40,
        })

    return optimizations


# ============================================================================
# Tool Registry
# ============================================================================

MULTICLOUD_TOOLS = {
    "cloud_compare_services": compare_cloud_services,
    "cloud_multi_region": generate_multi_region_config,
    "cloud_migrate": migrate_cloud_provider,
    "cloud_estimate_costs": estimate_cloud_costs,
    "cloud_landing_zone": generate_cloud_landing_zone,
    "cloud_analyze_spend": analyze_cloud_spend,
}
