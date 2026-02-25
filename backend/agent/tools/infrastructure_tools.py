"""
Infrastructure as Code (IaC) tools for NAVI agent.

Provides tools to generate infrastructure configurations:
- Terraform (AWS, GCP, Azure, DigitalOcean)
- CloudFormation (AWS)
- Kubernetes manifests
- Docker Compose
- Helm charts

Works dynamically for any project type without hardcoding.

Now with REAL EXECUTION capabilities - terraform apply, kubectl apply, helm install!
"""

import os
import json
from typing import Any, Dict, List, Optional
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)

# Import execution services
try:
    from backend.services.execution_confirmation_service import (
        execution_confirmation_service,
    )
    from backend.services.infrastructure_executor_service import (
        infrastructure_executor_service,
    )

    EXECUTION_SERVICES_AVAILABLE = True
except ImportError:
    EXECUTION_SERVICES_AVAILABLE = False
    logger.warning("Infrastructure execution services not available")


# Cloud provider resource templates
TERRAFORM_TEMPLATES = {
    "aws": {
        "provider": """terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "project_name" {
  description = "Project name"
  type        = string
}
""",
        "resources": {
            "ec2": """# EC2 Instance
resource "aws_instance" "{name}" {
  ami           = var.ami_id
  instance_type = var.instance_type

  vpc_security_group_ids = [aws_security_group.{name}_sg.id]
  subnet_id              = var.subnet_id

  tags = {
    Name        = "${{var.project_name}}-{name}"
    Environment = var.environment
  }
}

variable "ami_id" {
  description = "AMI ID for EC2 instance"
  type        = string
  default     = "ami-0c55b159cbfafe1f0"  # Amazon Linux 2
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "{instance_type}"
}

variable "subnet_id" {
  description = "Subnet ID for EC2 instance"
  type        = string
}

resource "aws_security_group" "{name}_sg" {
  name        = "${{var.project_name}}-{name}-sg"
  description = "Security group for {name}"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${{var.project_name}}-{name}-sg"
  }
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}
""",
            "rds": """# RDS Database
resource "aws_db_instance" "{name}" {
  identifier           = "${{var.project_name}}-{name}"
  allocated_storage    = var.db_storage
  storage_type         = "gp3"
  engine               = var.db_engine
  engine_version       = var.db_engine_version
  instance_class       = var.db_instance_class
  db_name              = var.db_name
  username             = var.db_username
  password             = var.db_password
  parameter_group_name = "default.${{var.db_engine}}${{var.db_engine_version}}"
  skip_final_snapshot  = var.environment != "production"

  vpc_security_group_ids = [aws_security_group.{name}_db_sg.id]
  db_subnet_group_name   = aws_db_subnet_group.{name}.name

  tags = {
    Name        = "${{var.project_name}}-{name}"
    Environment = var.environment
  }
}

variable "db_storage" {
  description = "Database storage in GB"
  type        = number
  default     = 20
}

variable "db_engine" {
  description = "Database engine"
  type        = string
  default     = "postgres"
}

variable "db_engine_version" {
  description = "Database engine version"
  type        = string
  default     = "15"
}

variable "db_instance_class" {
  description = "Database instance class"
  type        = string
  default     = "{instance_type}"
}

variable "db_name" {
  description = "Database name"
  type        = string
}

variable "db_username" {
  description = "Database username"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

resource "aws_db_subnet_group" "{name}" {
  name       = "${{var.project_name}}-{name}-subnet-group"
  subnet_ids = var.db_subnet_ids

  tags = {
    Name = "${{var.project_name}}-{name}-subnet-group"
  }
}

variable "db_subnet_ids" {
  description = "Subnet IDs for RDS"
  type        = list(string)
}

resource "aws_security_group" "{name}_db_sg" {
  name        = "${{var.project_name}}-{name}-db-sg"
  description = "Security group for {name} database"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }

  tags = {
    Name = "${{var.project_name}}-{name}-db-sg"
  }
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to access database"
  type        = list(string)
  default     = ["10.0.0.0/8"]
}
""",
            "s3": """# S3 Bucket
resource "aws_s3_bucket" "{name}" {
  bucket = "${{var.project_name}}-{name}-${{var.environment}}"

  tags = {
    Name        = "${{var.project_name}}-{name}"
    Environment = var.environment
  }
}

resource "aws_s3_bucket_versioning" "{name}" {
  bucket = aws_s3_bucket.{name}.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "{name}" {
  bucket = aws_s3_bucket.{name}.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "{name}" {
  bucket = aws_s3_bucket.{name}.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

output "{name}_bucket_name" {
  value = aws_s3_bucket.{name}.bucket
}

output "{name}_bucket_arn" {
  value = aws_s3_bucket.{name}.arn
}
""",
            "lambda": """# Lambda Function
resource "aws_lambda_function" "{name}" {
  function_name = "${{var.project_name}}-{name}"
  role          = aws_iam_role.{name}_lambda_role.arn
  handler       = var.lambda_handler
  runtime       = var.lambda_runtime
  timeout       = var.lambda_timeout
  memory_size   = var.lambda_memory

  filename         = var.lambda_filename
  source_code_hash = filebase64sha256(var.lambda_filename)

  environment {
    variables = var.lambda_env_vars
  }

  tags = {
    Name        = "${{var.project_name}}-{name}"
    Environment = var.environment
  }
}

variable "lambda_handler" {
  description = "Lambda handler"
  type        = string
  default     = "index.handler"
}

variable "lambda_runtime" {
  description = "Lambda runtime"
  type        = string
  default     = "nodejs18.x"
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 30
}

variable "lambda_memory" {
  description = "Lambda memory in MB"
  type        = number
  default     = 256
}

variable "lambda_filename" {
  description = "Lambda deployment package path"
  type        = string
}

variable "lambda_env_vars" {
  description = "Lambda environment variables"
  type        = map(string)
  default     = {}
}

resource "aws_iam_role" "{name}_lambda_role" {
  name = "${{var.project_name}}-{name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "{name}_lambda_basic" {
  role       = aws_iam_role.{name}_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

output "{name}_function_name" {
  value = aws_lambda_function.{name}.function_name
}

output "{name}_function_arn" {
  value = aws_lambda_function.{name}.arn
}
""",
            "ecs": """# ECS Cluster and Service
resource "aws_ecs_cluster" "{name}" {
  name = "${{var.project_name}}-{name}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name        = "${{var.project_name}}-{name}"
    Environment = var.environment
  }
}

resource "aws_ecs_task_definition" "{name}" {
  family                   = "${{var.project_name}}-{name}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.ecs_cpu
  memory                   = var.ecs_memory
  execution_role_arn       = aws_iam_role.{name}_ecs_execution_role.arn
  task_role_arn            = aws_iam_role.{name}_ecs_task_role.arn

  container_definitions = jsonencode([{
    name  = "{name}"
    image = var.container_image
    portMappings = [{
      containerPort = var.container_port
      protocol      = "tcp"
    }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.{name}.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "ecs"
      }
    }
    environment = var.container_env_vars
  }])
}

variable "ecs_cpu" {
  description = "ECS task CPU units"
  type        = string
  default     = "256"
}

variable "ecs_memory" {
  description = "ECS task memory"
  type        = string
  default     = "512"
}

variable "container_image" {
  description = "Container image"
  type        = string
}

variable "container_port" {
  description = "Container port"
  type        = number
  default     = 8080
}

variable "container_env_vars" {
  description = "Container environment variables"
  type        = list(object({
    name  = string
    value = string
  }))
  default = []
}

resource "aws_ecs_service" "{name}" {
  name            = "${{var.project_name}}-{name}"
  cluster         = aws_ecs_cluster.{name}.id
  task_definition = aws_ecs_task_definition.{name}.arn
  desired_count   = var.ecs_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.ecs_subnet_ids
    security_groups  = [aws_security_group.{name}_ecs_sg.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.{name}.arn
    container_name   = "{name}"
    container_port   = var.container_port
  }
}

variable "ecs_desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 2
}

variable "ecs_subnet_ids" {
  description = "Subnet IDs for ECS tasks"
  type        = list(string)
}

resource "aws_security_group" "{name}_ecs_sg" {
  name        = "${{var.project_name}}-{name}-ecs-sg"
  description = "Security group for {name} ECS tasks"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = var.container_port
    to_port         = var.container_port
    protocol        = "tcp"
    security_groups = [aws_security_group.{name}_alb_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_cloudwatch_log_group" "{name}" {
  name              = "/ecs/${{var.project_name}}-{name}"
  retention_in_days = 30
}

# IAM Roles
resource "aws_iam_role" "{name}_ecs_execution_role" {
  name = "${{var.project_name}}-{name}-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "{name}_ecs_execution_policy" {
  role       = aws_iam_role.{name}_ecs_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "{name}_ecs_task_role" {
  name = "${{var.project_name}}-{name}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

# Application Load Balancer
resource "aws_lb" "{name}" {
  name               = "${{var.project_name}}-{name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.{name}_alb_sg.id]
  subnets            = var.alb_subnet_ids

  tags = {
    Name        = "${{var.project_name}}-{name}-alb"
    Environment = var.environment
  }
}

variable "alb_subnet_ids" {
  description = "Subnet IDs for ALB"
  type        = list(string)
}

resource "aws_lb_target_group" "{name}" {
  name        = "${{var.project_name}}-{name}-tg"
  port        = var.container_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 2
  }
}

resource "aws_lb_listener" "{name}" {
  load_balancer_arn = aws_lb.{name}.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.{name}.arn
  }
}

resource "aws_security_group" "{name}_alb_sg" {
  name        = "${{var.project_name}}-{name}-alb-sg"
  description = "Security group for {name} ALB"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

output "{name}_alb_dns_name" {
  value = aws_lb.{name}.dns_name
}
""",
        },
    },
    "gcp": {
        "provider": """terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.gcp_project
  region  = var.gcp_region
}

variable "gcp_project" {
  description = "GCP project ID"
  type        = string
}

variable "gcp_region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "project_name" {
  description = "Project name"
  type        = string
}
""",
        "resources": {
            "cloud_run": """# Cloud Run Service
resource "google_cloud_run_service" "{name}" {
  name     = "${{var.project_name}}-{name}"
  location = var.gcp_region

  template {
    spec {
      containers {
        image = var.container_image
        resources {
          limits = {
            cpu    = var.cloud_run_cpu
            memory = var.cloud_run_memory
          }
        }
        ports {
          container_port = var.container_port
        }
        dynamic "env" {
          for_each = var.container_env_vars
          content {
            name  = env.value.name
            value = env.value.value
          }
        }
      }
    }
    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale" = var.min_instances
        "autoscaling.knative.dev/maxScale" = var.max_instances
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }
}

variable "container_image" {
  description = "Container image URL"
  type        = string
}

variable "cloud_run_cpu" {
  description = "CPU limit"
  type        = string
  default     = "1000m"
}

variable "cloud_run_memory" {
  description = "Memory limit"
  type        = string
  default     = "512Mi"
}

variable "container_port" {
  description = "Container port"
  type        = number
  default     = 8080
}

variable "container_env_vars" {
  description = "Container environment variables"
  type        = list(object({
    name  = string
    value = string
  }))
  default = []
}

variable "min_instances" {
  description = "Minimum instances"
  type        = string
  default     = "0"
}

variable "max_instances" {
  description = "Maximum instances"
  type        = string
  default     = "10"
}

# Allow unauthenticated access (remove for private services)
resource "google_cloud_run_service_iam_member" "{name}_invoker" {
  service  = google_cloud_run_service.{name}.name
  location = google_cloud_run_service.{name}.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "{name}_url" {
  value = google_cloud_run_service.{name}.status[0].url
}
""",
            "cloud_sql": """# Cloud SQL Instance
resource "google_sql_database_instance" "{name}" {
  name             = "${{var.project_name}}-{name}"
  database_version = var.db_version
  region           = var.gcp_region

  settings {
    tier = var.db_tier

    ip_configuration {
      ipv4_enabled    = true
      private_network = var.vpc_id
    }

    backup_configuration {
      enabled = true
    }
  }

  deletion_protection = var.environment == "production"
}

variable "db_version" {
  description = "Database version"
  type        = string
  default     = "POSTGRES_15"
}

variable "db_tier" {
  description = "Database tier"
  type        = string
  default     = "db-f1-micro"
}

variable "vpc_id" {
  description = "VPC network ID"
  type        = string
}

resource "google_sql_database" "{name}" {
  name     = var.db_name
  instance = google_sql_database_instance.{name}.name
}

variable "db_name" {
  description = "Database name"
  type        = string
}

resource "google_sql_user" "{name}" {
  name     = var.db_user
  instance = google_sql_database_instance.{name}.name
  password = var.db_password
}

variable "db_user" {
  description = "Database username"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

output "{name}_connection_name" {
  value = google_sql_database_instance.{name}.connection_name
}
""",
            "gcs": """# Google Cloud Storage Bucket
resource "google_storage_bucket" "{name}" {
  name     = "${{var.project_name}}-{name}-${{var.environment}}"
  location = var.gcp_region

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  labels = {
    environment = var.environment
  }
}

output "{name}_bucket_name" {
  value = google_storage_bucket.{name}.name
}

output "{name}_bucket_url" {
  value = google_storage_bucket.{name}.url
}
""",
        },
    },
}

# Kubernetes manifest templates
K8S_TEMPLATES = {
    "deployment": """apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}
  labels:
    app: {name}
spec:
  replicas: {replicas}
  selector:
    matchLabels:
      app: {name}
  template:
    metadata:
      labels:
        app: {name}
    spec:
      containers:
      - name: {name}
        image: {image}
        ports:
        - containerPort: {port}
        resources:
          requests:
            memory: "{memory_request}"
            cpu: "{cpu_request}"
          limits:
            memory: "{memory_limit}"
            cpu: "{cpu_limit}"
        livenessProbe:
          httpGet:
            path: /health
            port: {port}
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: {port}
          initialDelaySeconds: 5
          periodSeconds: 5
        env:
{env_vars}
""",
    "service": """apiVersion: v1
kind: Service
metadata:
  name: {name}
spec:
  selector:
    app: {name}
  ports:
  - protocol: TCP
    port: 80
    targetPort: {port}
  type: ClusterIP
""",
    "ingress": """apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {name}
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - {host}
    secretName: {name}-tls
  rules:
  - host: {host}
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: {name}
            port:
              number: 80
""",
    "hpa": """apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {name}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {name}
  minReplicas: {min_replicas}
  maxReplicas: {max_replicas}
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
""",
    "configmap": """apiVersion: v1
kind: ConfigMap
metadata:
  name: {name}-config
data:
{config_data}
""",
    "secret": """apiVersion: v1
kind: Secret
metadata:
  name: {name}-secrets
type: Opaque
stringData:
{secret_data}
""",
}

# Docker Compose templates
DOCKER_COMPOSE_TEMPLATES = {
    "web": """  {name}:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "{host_port}:{container_port}"
    environment:
{env_vars}
    depends_on:
{depends_on}
    restart: unless-stopped
""",
    "database": """  {name}:
    image: {image}
    ports:
      - "{host_port}:{container_port}"
    environment:
{env_vars}
    volumes:
      - {name}_data:/var/lib/{volume_path}
    restart: unless-stopped
""",
    "redis": """  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
""",
}


async def generate_terraform(
    context: Dict[str, Any],
    workspace_path: str,
    cloud_provider: str,
    resources: List[Dict[str, Any]],
    output_dir: str = "terraform",
) -> ToolResult:
    """
    Generate Terraform configuration for cloud infrastructure.

    Args:
        workspace_path: Path to the project root
        cloud_provider: Cloud provider (aws, gcp, azure, digitalocean)
        resources: List of resources to create, each with type, name, and config
        output_dir: Output directory for Terraform files

    Returns:
        ToolResult with generated Terraform configuration
    """
    logger.info(
        "generate_terraform",
        workspace_path=workspace_path,
        cloud_provider=cloud_provider,
        resources=resources,
    )

    cloud_provider = cloud_provider.lower()
    if cloud_provider not in TERRAFORM_TEMPLATES:
        available = ", ".join(TERRAFORM_TEMPLATES.keys())
        return ToolResult(
            output=f"Unsupported cloud provider: {cloud_provider}\n\nAvailable: {available}",
            sources=[],
        )

    templates = TERRAFORM_TEMPLATES[cloud_provider]

    # Generate main.tf with provider configuration
    main_tf = templates["provider"]

    # Generate resource files
    resource_contents = []

    for resource in resources:
        res_type = resource.get("type", "").lower()
        res_name = resource.get("name", "app")
        res_config = resource.get("config", {})

        if res_type not in templates.get("resources", {}):
            available_resources = ", ".join(templates.get("resources", {}).keys())
            resource_contents.append(f"# Unknown resource type: {res_type}")
            resource_contents.append(
                f"# Available resources for {cloud_provider}: {available_resources}"
            )
            continue

        template = templates["resources"][res_type]

        # Format template with resource-specific values
        instance_type = res_config.get("instance_type", "t3.micro")
        formatted = template.format(
            name=res_name,
            instance_type=instance_type,
        )
        resource_contents.append(f"# {res_type.upper()} - {res_name}")
        resource_contents.append(formatted)

    # Generate outputs.tf
    outputs_tf = """# Outputs
output "environment" {
  value = var.environment
}

output "project_name" {
  value = var.project_name
}
"""

    # Generate terraform.tfvars.example
    tfvars_example = """# Example Terraform variables
# Copy this file to terraform.tfvars and fill in your values

project_name = "my-project"
environment  = "production"
"""

    if cloud_provider == "aws":
        tfvars_example += """aws_region   = "us-east-1"
vpc_id       = "vpc-xxxxxxxx"
subnet_id    = "subnet-xxxxxxxx"
"""
    elif cloud_provider == "gcp":
        tfvars_example += """gcp_project  = "my-gcp-project"
gcp_region   = "us-central1"
"""

    # Build output
    lines = [f"## Generated Terraform Configuration ({cloud_provider.upper()})\n"]
    lines.append(f"**Cloud Provider**: {cloud_provider}")
    lines.append(f"**Resources**: {len(resources)}")
    lines.append(f"**Output Directory**: `{output_dir}/`")

    lines.append("\n### main.tf")
    lines.append("```hcl")
    lines.append(main_tf)
    lines.append("```")

    if resource_contents:
        lines.append("\n### resources.tf")
        lines.append("```hcl")
        lines.append("\n\n".join(resource_contents))
        lines.append("```")

    lines.append("\n### outputs.tf")
    lines.append("```hcl")
    lines.append(outputs_tf)
    lines.append("```")

    lines.append("\n### terraform.tfvars.example")
    lines.append("```hcl")
    lines.append(tfvars_example)
    lines.append("```")

    lines.append("\n### Next Steps")
    lines.append("1. Save files to `{}/`".format(output_dir))
    lines.append("2. Copy `terraform.tfvars.example` to `terraform.tfvars`")
    lines.append("3. Fill in your actual values")
    lines.append("4. Run `terraform init`")
    lines.append("5. Run `terraform plan` to preview changes")
    lines.append("6. Run `terraform apply` to create infrastructure")

    return ToolResult(output="\n".join(lines), sources=[])


async def generate_cloudformation(
    context: Dict[str, Any],
    workspace_path: str,
    resources: List[Dict[str, Any]],
    output_path: str = "cloudformation.yaml",
) -> ToolResult:
    """
    Generate AWS CloudFormation template.

    Args:
        workspace_path: Path to the project root
        resources: List of resources to create
        output_path: Output file path

    Returns:
        ToolResult with generated CloudFormation template
    """
    logger.info("generate_cloudformation", workspace_path=workspace_path)

    template = {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "CloudFormation template generated by NAVI",
        "Parameters": {
            "Environment": {
                "Type": "String",
                "Default": "production",
                "AllowedValues": ["development", "staging", "production"],
            },
            "ProjectName": {
                "Type": "String",
                "Description": "Project name",
            },
        },
        "Resources": {},
        "Outputs": {},
    }

    for resource in resources:
        res_type = resource.get("type", "").lower()
        res_name = resource.get("name", "App")
        res_config = resource.get("config", {})

        # Generate CloudFormation resource based on type
        if res_type == "ec2":
            template["Resources"][f"{res_name}Instance"] = {
                "Type": "AWS::EC2::Instance",
                "Properties": {
                    "InstanceType": res_config.get("instance_type", "t3.micro"),
                    "ImageId": {"Ref": "AMI"},
                    "Tags": [
                        {
                            "Key": "Name",
                            "Value": {"Fn::Sub": "${ProjectName}-" + res_name},
                        },
                        {"Key": "Environment", "Value": {"Ref": "Environment"}},
                    ],
                },
            }
            template["Parameters"]["AMI"] = {
                "Type": "AWS::EC2::Image::Id",
                "Description": "AMI ID for EC2 instance",
            }

        elif res_type == "s3":
            template["Resources"][f"{res_name}Bucket"] = {
                "Type": "AWS::S3::Bucket",
                "Properties": {
                    "BucketName": {
                        "Fn::Sub": "${ProjectName}-"
                        + res_name.lower()
                        + "-${Environment}"
                    },
                    "VersioningConfiguration": {"Status": "Enabled"},
                    "BucketEncryption": {
                        "ServerSideEncryptionConfiguration": [
                            {
                                "ServerSideEncryptionByDefault": {
                                    "SSEAlgorithm": "AES256",
                                },
                            }
                        ],
                    },
                    "PublicAccessBlockConfiguration": {
                        "BlockPublicAcls": True,
                        "BlockPublicPolicy": True,
                        "IgnorePublicAcls": True,
                        "RestrictPublicBuckets": True,
                    },
                },
            }
            template["Outputs"][f"{res_name}BucketArn"] = {
                "Value": {"Fn::GetAtt": [f"{res_name}Bucket", "Arn"]},
            }

        elif res_type == "lambda":
            template["Resources"][f"{res_name}Function"] = {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "FunctionName": {"Fn::Sub": "${ProjectName}-" + res_name},
                    "Runtime": res_config.get("runtime", "nodejs18.x"),
                    "Handler": res_config.get("handler", "index.handler"),
                    "MemorySize": res_config.get("memory", 256),
                    "Timeout": res_config.get("timeout", 30),
                    "Role": {"Fn::GetAtt": [f"{res_name}Role", "Arn"]},
                },
            }
            template["Resources"][f"{res_name}Role"] = {
                "Type": "AWS::IAM::Role",
                "Properties": {
                    "AssumeRolePolicyDocument": {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Principal": {"Service": "lambda.amazonaws.com"},
                                "Action": "sts:AssumeRole",
                            }
                        ],
                    },
                    "ManagedPolicyArns": [
                        "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
                    ],
                },
            }

    # Convert to YAML
    import yaml

    try:
        yaml_content = yaml.dump(template, default_flow_style=False, sort_keys=False)
    except ImportError:
        yaml_content = json.dumps(template, indent=2)

    lines = ["## Generated CloudFormation Template\n"]
    lines.append(f"**Resources**: {len(resources)}")
    lines.append(f"**Output File**: `{output_path}`")
    lines.append("\n**Generated Template**:")
    lines.append("```yaml")
    lines.append(yaml_content)
    lines.append("```")

    lines.append("\n### Deployment")
    lines.append("```bash")
    lines.append("# Deploy the stack")
    lines.append("aws cloudformation deploy \\")
    lines.append("  --template-file cloudformation.yaml \\")
    lines.append("  --stack-name my-stack \\")
    lines.append(
        "  --parameter-overrides ProjectName=my-project Environment=production \\"
    )
    lines.append("  --capabilities CAPABILITY_IAM")
    lines.append("```")

    return ToolResult(output="\n".join(lines), sources=[])


async def generate_kubernetes_manifests(
    context: Dict[str, Any],
    workspace_path: str,
    app_name: str,
    image: Optional[str] = None,
    replicas: int = 2,
    port: int = 8080,
    env_vars: Optional[Dict[str, str]] = None,
    host: Optional[str] = None,
) -> ToolResult:
    """
    Generate Kubernetes manifests for an application.

    Analyzes Dockerfile if present for container configuration.

    Args:
        workspace_path: Path to the project root
        app_name: Application name
        image: Container image (default: {app_name}:latest)
        replicas: Number of replicas
        port: Container port
        env_vars: Environment variables
        host: Ingress hostname

    Returns:
        ToolResult with generated Kubernetes manifests
    """
    logger.info(
        "generate_kubernetes_manifests",
        workspace_path=workspace_path,
        app_name=app_name,
    )

    # Default values
    image = image or f"{app_name}:latest"
    env_vars = env_vars or {}
    host = host or f"{app_name}.example.com"

    # Try to detect port from Dockerfile
    dockerfile_path = os.path.join(workspace_path, "Dockerfile")
    if os.path.exists(dockerfile_path):
        try:
            with open(dockerfile_path, "r") as f:
                content = f.read()
            import re

            expose_match = re.search(r"EXPOSE\s+(\d+)", content)
            if expose_match:
                port = int(expose_match.group(1))
        except (IOError, ValueError):
            pass

    # Format environment variables for YAML
    env_yaml = ""
    if env_vars:
        for key, value in env_vars.items():
            env_yaml += f'        - name: {key}\n          value: "{value}"\n'
    else:
        env_yaml = "        []"

    # Generate deployment
    deployment = K8S_TEMPLATES["deployment"].format(
        name=app_name,
        replicas=replicas,
        image=image,
        port=port,
        memory_request="128Mi",
        cpu_request="100m",
        memory_limit="256Mi",
        cpu_limit="500m",
        env_vars=env_yaml,
    )

    # Generate service
    service = K8S_TEMPLATES["service"].format(
        name=app_name,
        port=port,
    )

    # Generate ingress
    ingress = K8S_TEMPLATES["ingress"].format(
        name=app_name,
        host=host,
    )

    # Generate HPA
    hpa = K8S_TEMPLATES["hpa"].format(
        name=app_name,
        min_replicas=replicas,
        max_replicas=replicas * 5,
    )

    lines = ["## Generated Kubernetes Manifests\n"]
    lines.append(f"**Application**: {app_name}")
    lines.append(f"**Image**: {image}")
    lines.append(f"**Replicas**: {replicas}")
    lines.append(f"**Port**: {port}")

    lines.append("\n### deployment.yaml")
    lines.append("```yaml")
    lines.append(deployment)
    lines.append("```")

    lines.append("\n### service.yaml")
    lines.append("```yaml")
    lines.append(service)
    lines.append("```")

    lines.append("\n### ingress.yaml")
    lines.append("```yaml")
    lines.append(ingress)
    lines.append("```")

    lines.append("\n### hpa.yaml")
    lines.append("```yaml")
    lines.append(hpa)
    lines.append("```")

    lines.append("\n### Deployment Commands")
    lines.append("```bash")
    lines.append("# Apply all manifests")
    lines.append("kubectl apply -f k8s/")
    lines.append("")
    lines.append("# Or apply individually")
    lines.append("kubectl apply -f deployment.yaml")
    lines.append("kubectl apply -f service.yaml")
    lines.append("kubectl apply -f ingress.yaml")
    lines.append("kubectl apply -f hpa.yaml")
    lines.append("```")

    return ToolResult(output="\n".join(lines), sources=[])


async def generate_docker_compose(
    context: Dict[str, Any],
    workspace_path: str,
    services: Optional[List[Dict[str, Any]]] = None,
) -> ToolResult:
    """
    Generate Docker Compose configuration.

    Auto-detects services from project if not specified.

    Args:
        workspace_path: Path to the project root
        services: List of services to include

    Returns:
        ToolResult with generated docker-compose.yml
    """
    logger.info("generate_docker_compose", workspace_path=workspace_path)

    # Auto-detect if services not provided
    if not services:
        services = _detect_docker_services(workspace_path)

    compose = {
        "version": "3.8",
        "services": {},
        "volumes": {},
    }

    for service in services:
        svc_type = service.get("type", "web")
        svc_name = service.get("name", "app")
        svc_config = service.get("config", {})

        if svc_type == "web":
            compose["services"][svc_name] = {
                "build": {"context": ".", "dockerfile": "Dockerfile"},
                "ports": [
                    f"{svc_config.get('host_port', 3000)}:{svc_config.get('container_port', 3000)}"
                ],
                "environment": svc_config.get("env", {}),
                "restart": "unless-stopped",
            }
            if svc_config.get("depends_on"):
                compose["services"][svc_name]["depends_on"] = svc_config["depends_on"]

        elif svc_type == "postgres":
            compose["services"][svc_name] = {
                "image": "postgres:15-alpine",
                "ports": [f"{svc_config.get('host_port', 5432)}:5432"],
                "environment": {
                    "POSTGRES_USER": "${DB_USER:-postgres}",
                    "POSTGRES_PASSWORD": "${DB_PASSWORD:-postgres}",
                    "POSTGRES_DB": "${DB_NAME:-app}",
                },
                "volumes": [f"{svc_name}_data:/var/lib/postgresql/data"],
                "restart": "unless-stopped",
            }
            compose["volumes"][f"{svc_name}_data"] = {}

        elif svc_type == "redis":
            compose["services"][svc_name] = {
                "image": "redis:alpine",
                "ports": [f"{svc_config.get('host_port', 6379)}:6379"],
                "volumes": [f"{svc_name}_data:/data"],
                "restart": "unless-stopped",
            }
            compose["volumes"][f"{svc_name}_data"] = {}

        elif svc_type == "mongodb":
            compose["services"][svc_name] = {
                "image": "mongo:6",
                "ports": [f"{svc_config.get('host_port', 27017)}:27017"],
                "environment": {
                    "MONGO_INITDB_ROOT_USERNAME": "${MONGO_USER:-mongo}",
                    "MONGO_INITDB_ROOT_PASSWORD": "${MONGO_PASSWORD:-mongo}",
                },
                "volumes": [f"{svc_name}_data:/data/db"],
                "restart": "unless-stopped",
            }
            compose["volumes"][f"{svc_name}_data"] = {}

    # Convert to YAML
    import yaml

    try:
        yaml_content = yaml.dump(compose, default_flow_style=False, sort_keys=False)
    except ImportError:
        yaml_content = json.dumps(compose, indent=2)

    lines = ["## Generated Docker Compose Configuration\n"]
    lines.append(f"**Services**: {len(compose['services'])}")
    lines.append(f"**Volumes**: {len(compose['volumes'])}")

    lines.append("\n### docker-compose.yml")
    lines.append("```yaml")
    lines.append(yaml_content)
    lines.append("```")

    lines.append("\n### Commands")
    lines.append("```bash")
    lines.append("# Start all services")
    lines.append("docker-compose up -d")
    lines.append("")
    lines.append("# View logs")
    lines.append("docker-compose logs -f")
    lines.append("")
    lines.append("# Stop all services")
    lines.append("docker-compose down")
    lines.append("```")

    return ToolResult(output="\n".join(lines), sources=[])


async def generate_helm_chart(
    context: Dict[str, Any],
    workspace_path: str,
    chart_name: str,
    app_version: str = "1.0.0",
) -> ToolResult:
    """
    Generate Helm chart for Kubernetes deployment.

    Args:
        workspace_path: Path to the project root
        chart_name: Name of the Helm chart
        app_version: Application version

    Returns:
        ToolResult with generated Helm chart structure
    """
    logger.info("generate_helm_chart", chart_name=chart_name)

    # Chart.yaml
    chart_yaml = f"""apiVersion: v2
name: {chart_name}
description: A Helm chart for {chart_name}
type: application
version: 0.1.0
appVersion: "{app_version}"
"""

    # values.yaml
    values_yaml = f"""# Default values for {chart_name}
replicaCount: 2

image:
  repository: {chart_name}
  pullPolicy: IfNotPresent
  tag: ""

service:
  type: ClusterIP
  port: 80

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: {chart_name}.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: {chart_name}-tls
      hosts:
        - {chart_name}.example.com

resources:
  limits:
    cpu: 500m
    memory: 256Mi
  requests:
    cpu: 100m
    memory: 128Mi

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80

env: []
"""

    # templates/deployment.yaml
    deployment_template = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "{name}.fullname" . }}
  labels:
    {{{{- include "{name}.labels" . | nindent 4 }}}}
spec:
  {{{{- if not .Values.autoscaling.enabled }}}}
  replicas: {{{{ .Values.replicaCount }}}}
  {{{{- end }}}}
  selector:
    matchLabels:
      {{{{- include "{name}.selectorLabels" . | nindent 6 }}}}
  template:
    metadata:
      labels:
        {{{{- include "{name}.selectorLabels" . | nindent 8 }}}}
    spec:
      containers:
        - name: {{{{ .Chart.Name }}}}
          image: "{{{{ .Values.image.repository }}}}:{{{{ .Values.image.tag | default .Chart.AppVersion }}}}"
          imagePullPolicy: {{{{ .Values.image.pullPolicy }}}}
          ports:
            - name: http
              containerPort: 8080
              protocol: TCP
          livenessProbe:
            httpGet:
              path: /health
              port: http
          readinessProbe:
            httpGet:
              path: /ready
              port: http
          resources:
            {{{{- toYaml .Values.resources | nindent 12 }}}}
          env:
            {{{{- toYaml .Values.env | nindent 12 }}}}
""".format(name=chart_name)

    lines = ["## Generated Helm Chart\n"]
    lines.append(f"**Chart Name**: {chart_name}")
    lines.append(f"**App Version**: {app_version}")

    lines.append("\n### Chart.yaml")
    lines.append("```yaml")
    lines.append(chart_yaml)
    lines.append("```")

    lines.append("\n### values.yaml")
    lines.append("```yaml")
    lines.append(values_yaml)
    lines.append("```")

    lines.append("\n### templates/deployment.yaml")
    lines.append("```yaml")
    lines.append(deployment_template)
    lines.append("```")

    lines.append("\n### Installation")
    lines.append("```bash")
    lines.append("# Install the chart")
    lines.append(f"helm install {chart_name} ./{chart_name}")
    lines.append("")
    lines.append("# Install with custom values")
    lines.append(f"helm install {chart_name} ./{chart_name} -f my-values.yaml")
    lines.append("")
    lines.append("# Upgrade")
    lines.append(f"helm upgrade {chart_name} ./{chart_name}")
    lines.append("```")

    return ToolResult(output="\n".join(lines), sources=[])


async def analyze_infrastructure_needs(
    context: Dict[str, Any],
    workspace_path: str,
) -> ToolResult:
    """
    Analyze a project and recommend infrastructure setup.

    Args:
        workspace_path: Path to the project root

    Returns:
        ToolResult with infrastructure recommendations
    """
    logger.info("analyze_infrastructure_needs", workspace_path=workspace_path)

    if not os.path.exists(workspace_path):
        return ToolResult(output=f"Directory not found: {workspace_path}", sources=[])

    recommendations = {
        "compute": [],
        "database": [],
        "storage": [],
        "networking": [],
        "monitoring": [],
    }

    # Analyze package.json
    package_json_path = os.path.join(workspace_path, "package.json")
    if os.path.exists(package_json_path):
        try:
            with open(package_json_path, "r") as f:
                pkg = json.load(f)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

                # Next.js
                if "next" in deps:
                    recommendations["compute"].append(
                        {
                            "type": "Serverless/Container",
                            "options": [
                                "Vercel (recommended)",
                                "AWS ECS/Fargate",
                                "Cloud Run",
                            ],
                            "reason": "Next.js works best with serverless or container deployment",
                        }
                    )

                # Database dependencies
                if "prisma" in deps or "typeorm" in deps or "pg" in deps:
                    recommendations["database"].append(
                        {
                            "type": "PostgreSQL",
                            "options": ["AWS RDS", "Cloud SQL", "Railway Postgres"],
                            "reason": "Detected PostgreSQL ORM/client",
                        }
                    )

                if "mongoose" in deps or "mongodb" in deps:
                    recommendations["database"].append(
                        {
                            "type": "MongoDB",
                            "options": ["MongoDB Atlas", "AWS DocumentDB"],
                            "reason": "Detected MongoDB client",
                        }
                    )

                # Redis
                if "redis" in deps or "ioredis" in deps:
                    recommendations["database"].append(
                        {
                            "type": "Redis",
                            "options": ["AWS ElastiCache", "Upstash", "Redis Cloud"],
                            "reason": "Detected Redis client for caching/sessions",
                        }
                    )

                # File uploads
                if "@aws-sdk/client-s3" in deps or "aws-sdk" in deps:
                    recommendations["storage"].append(
                        {
                            "type": "Object Storage",
                            "options": ["AWS S3", "GCS", "Cloudflare R2"],
                            "reason": "Detected AWS SDK for file storage",
                        }
                    )

        except (json.JSONDecodeError, IOError):
            pass

    # Analyze requirements.txt
    requirements_path = os.path.join(workspace_path, "requirements.txt")
    if os.path.exists(requirements_path):
        try:
            with open(requirements_path, "r") as f:
                content = f.read().lower()

            if "fastapi" in content or "django" in content:
                recommendations["compute"].append(
                    {
                        "type": "Container",
                        "options": ["AWS ECS/Fargate", "Cloud Run", "Railway"],
                        "reason": "Python web frameworks work well containerized",
                    }
                )

            if "psycopg" in content or "sqlalchemy" in content:
                recommendations["database"].append(
                    {
                        "type": "PostgreSQL",
                        "options": ["AWS RDS", "Cloud SQL", "Railway Postgres"],
                        "reason": "Detected PostgreSQL dependencies",
                    }
                )

            if "celery" in content:
                recommendations["compute"].append(
                    {
                        "type": "Background Workers",
                        "options": [
                            "AWS SQS + Lambda",
                            "Cloud Tasks",
                            "Railway Workers",
                        ],
                        "reason": "Detected Celery for task processing",
                    }
                )

        except IOError:
            pass

    # Check for Dockerfile
    if os.path.exists(os.path.join(workspace_path, "Dockerfile")):
        recommendations["compute"].append(
            {
                "type": "Container Orchestration",
                "options": ["Kubernetes (EKS/GKE)", "AWS ECS", "Fly.io"],
                "reason": "Dockerfile present - ready for containerized deployment",
            }
        )

    # Default recommendations
    recommendations["networking"].append(
        {
            "type": "Load Balancer",
            "options": ["AWS ALB", "Cloud Load Balancing", "Cloudflare"],
            "reason": "Recommended for production traffic",
        }
    )

    recommendations["monitoring"].append(
        {
            "type": "Application Monitoring",
            "options": ["Datadog", "New Relic", "Sentry + Grafana"],
            "reason": "Essential for production observability",
        }
    )

    # Build output
    lines = ["## Infrastructure Recommendations\n"]

    for category, items in recommendations.items():
        if items:
            lines.append(f"### {category.title()}")
            for item in items:
                lines.append(f"\n**{item['type']}**")
                lines.append(f"- Options: {', '.join(item['options'])}")
                lines.append(f"- Reason: {item['reason']}")
            lines.append("")

    lines.append("### Estimated Resources")
    lines.append("For a typical production deployment:")
    lines.append("- **Compute**: 2+ instances/containers with auto-scaling")
    lines.append("- **Database**: Single instance with read replicas for scale")
    lines.append("- **Storage**: Based on expected data volume")
    lines.append("- **CDN**: Recommended for static assets")

    return ToolResult(output="\n".join(lines), sources=[])


def _detect_docker_services(workspace_path: str) -> List[Dict[str, Any]]:
    """Detect services needed from project analysis."""
    services = []

    # Always include web service if Dockerfile exists
    if os.path.exists(os.path.join(workspace_path, "Dockerfile")):
        services.append({"type": "web", "name": "app", "config": {}})

    # Check for database dependencies
    package_json_path = os.path.join(workspace_path, "package.json")
    requirements_path = os.path.join(workspace_path, "requirements.txt")

    deps_content = ""

    if os.path.exists(package_json_path):
        try:
            with open(package_json_path, "r") as f:
                pkg = json.load(f)
                deps_content = json.dumps(pkg.get("dependencies", {}))
        except (json.JSONDecodeError, IOError):
            pass

    if os.path.exists(requirements_path):
        try:
            with open(requirements_path, "r") as f:
                deps_content += f.read().lower()
        except IOError:
            pass

    # Add database services based on dependencies
    if "postgres" in deps_content or "pg" in deps_content or "psycopg" in deps_content:
        services.append({"type": "postgres", "name": "db", "config": {}})

    if "mongodb" in deps_content or "mongoose" in deps_content:
        services.append({"type": "mongodb", "name": "mongo", "config": {}})

    if "redis" in deps_content or "ioredis" in deps_content:
        services.append({"type": "redis", "name": "redis", "config": {}})

    # Default to postgres if no database detected but Dockerfile exists
    if len(services) == 1 and services[0]["type"] == "web":
        services.append({"type": "postgres", "name": "db", "config": {}})

    return services


# ============================================================================
# REAL EXECUTION TOOLS - These actually modify infrastructure!
# ============================================================================


async def terraform_plan(
    context: Dict[str, Any],
    workspace_path: Optional[str] = None,
    variables: Optional[Dict[str, Any]] = None,
    var_file: Optional[str] = None,
    destroy: bool = False,
) -> ToolResult:
    """
    Create a Terraform plan showing what changes would be made.

    This is a SAFE operation - it only shows what would happen.

    Args:
        workspace_path: Path to Terraform configuration
        variables: Variables to pass to Terraform
        var_file: Path to variables file
        destroy: If True, plan for destruction
    """
    if not EXECUTION_SERVICES_AVAILABLE:
        return ToolResult(
            output="⚠️ Infrastructure execution services not available.\n\n"
            "To create a plan manually, run:\n```bash\nterraform plan\n```",
            sources=[],
        )

    workspace_path = workspace_path or os.getcwd()

    plan = await infrastructure_executor_service.terraform_plan(
        workspace_path=workspace_path,
        variables=variables,
        var_file=var_file,
        destroy=destroy,
    )

    output = "## Terraform Plan\n\n"
    output += "### Summary\n"
    output += f"- **Add**: {plan.summary.get('add', 0)} resources\n"
    output += f"- **Change**: {plan.summary.get('change', 0)} resources\n"
    output += f"- **Destroy**: {plan.summary.get('destroy', 0)} resources\n\n"

    if plan.changes:
        output += "### Changes\n"
        for change in plan.changes:
            icon = {
                "create": "➕",
                "update": "🔄",
                "delete": "❌",
                "replace": "🔁",
            }.get(change.action, "•")
            output += f"{icon} `{change.resource_address}` ({change.action})\n"

    if plan.plan_file:
        output += f"\n**Plan file**: `{plan.plan_file}`\n"
        output += (
            "\nTo apply this plan, use `infra.terraform_apply` with this plan file."
        )

    return ToolResult(output=output, sources=[])


async def terraform_apply(
    context: Dict[str, Any],
    workspace_path: Optional[str] = None,
    plan_file: Optional[str] = None,
    variables: Optional[Dict[str, Any]] = None,
    var_file: Optional[str] = None,
    auto_approve: bool = False,
    skip_confirmation: bool = False,
) -> ToolResult:
    """
    Apply Terraform changes to create/modify infrastructure.

    ⚠️ CRITICAL WARNING: This WILL modify real cloud infrastructure!
    Costs may be incurred. Resources may be created or destroyed.

    Args:
        workspace_path: Path to Terraform configuration
        plan_file: Path to a saved plan file
        variables: Variables to pass to Terraform
        var_file: Path to variables file
        auto_approve: Skip interactive approval (use with caution!)
        skip_confirmation: Skip NAVI confirmation dialog (dangerous!)
    """
    if not EXECUTION_SERVICES_AVAILABLE:
        return ToolResult(
            output="⚠️ Infrastructure execution services not available.",
            sources=[],
        )

    workspace_path = workspace_path or os.getcwd()

    # Create confirmation request
    if not skip_confirmation:
        request = execution_confirmation_service.create_execution_request(
            operation_name="infra.terraform_apply",
            description="Apply Terraform changes to cloud infrastructure",
            parameters={
                "workspace_path": workspace_path,
                "plan_file": plan_file,
                "variables": list((variables or {}).keys()),
            },
            environment="production",  # Infrastructure is always "production" level risk
            affected_resources=["Cloud infrastructure"],
            estimated_duration="5-30 minutes",
        )

        ui_data = execution_confirmation_service.format_request_for_ui(request)

        return ToolResult(
            output=f"## ⚠️ CRITICAL: Infrastructure Change Confirmation Required\n\n"
            f"**Operation**: Terraform Apply\n"
            f"**Risk Level**: {request.risk_level.value.upper()}\n\n"
            f"### ⚠️ Warnings\n"
            + "\n".join([f"- {w.message}" for w in request.warnings])
            + f"\n\n**Request ID**: `{request.id}`\n"
            f"**Confirmation Phrase**: `{request.confirmation_phrase}`\n\n"
            f"To proceed, call `infra.confirm_apply` with the request ID and confirmation phrase.",
            sources=[{"type": "execution_request", "data": ui_data}],
        )

    # Execute the apply
    result = await infrastructure_executor_service.terraform_apply(
        workspace_path=workspace_path,
        plan_file=plan_file,
        variables=variables,
        var_file=var_file,
        auto_approve=True,
    )

    if result.success:
        output = "## ✅ Terraform Apply Successful\n\n"
        output += f"**Duration**: {result.duration_seconds:.1f}s\n\n"

        if result.outputs:
            output += "### Outputs\n"
            for key, value in result.outputs.items():
                output += f"- **{key}**: `{value}`\n"

        if result.rollback_command:
            output += f"\n### Rollback\n`{result.rollback_command}`\n"

        return ToolResult(output=output, sources=[])
    else:
        return ToolResult(
            output=f"## ❌ Terraform Apply Failed\n\n{result.error}\n\n"
            f"### Logs\n```\n" + "\n".join(result.logs[-30:]) + "\n```",
            sources=[],
        )


async def terraform_destroy(
    context: Dict[str, Any],
    workspace_path: Optional[str] = None,
    variables: Optional[Dict[str, Any]] = None,
    auto_approve: bool = False,
    skip_confirmation: bool = False,
) -> ToolResult:
    """
    Destroy Terraform-managed infrastructure.

    ⚠️⚠️⚠️ EXTREME WARNING: This PERMANENTLY DELETES infrastructure!
    All data in destroyed resources will be LOST FOREVER.

    Args:
        workspace_path: Path to Terraform configuration
        variables: Variables to pass to Terraform
        auto_approve: Skip interactive approval (EXTREMELY DANGEROUS!)
        skip_confirmation: Skip NAVI confirmation (NEVER DO THIS)
    """
    if not EXECUTION_SERVICES_AVAILABLE:
        return ToolResult(
            output="⚠️ Infrastructure execution services not available.",
            sources=[],
        )

    workspace_path = workspace_path or os.getcwd()

    # Always require confirmation for destroy
    if not skip_confirmation:
        request = execution_confirmation_service.create_execution_request(
            operation_name="infra.terraform_destroy",
            description="DESTROY all Terraform-managed infrastructure",
            parameters={"workspace_path": workspace_path},
            environment="production",
        )

        return ToolResult(
            output=f"## ⚠️⚠️⚠️ CRITICAL: DESTRUCTIVE OPERATION ⚠️⚠️⚠️\n\n"
            f"**Operation**: Terraform Destroy\n"
            f"**Risk Level**: CRITICAL\n\n"
            f"### ❌ THIS WILL PERMANENTLY DELETE:\n"
            f"- All Terraform-managed infrastructure\n"
            f"- All data in those resources\n"
            f"- This action CANNOT be undone\n\n"
            f"**Request ID**: `{request.id}`\n"
            f"**Type**: `{request.confirmation_phrase}` to confirm\n\n"
            f"⚠️ THINK CAREFULLY BEFORE PROCEEDING ⚠️",
            sources=[],
        )

    result = await infrastructure_executor_service.terraform_destroy(
        workspace_path=workspace_path,
        variables=variables,
        auto_approve=True,
    )

    if result.success:
        return ToolResult(
            output=f"## ✅ Infrastructure Destroyed\n\n"
            f"All Terraform-managed resources have been deleted.\n"
            f"**Duration**: {result.duration_seconds:.1f}s",
            sources=[],
        )
    else:
        return ToolResult(
            output=f"## ❌ Terraform Destroy Failed\n\n{result.error}",
            sources=[],
        )


async def kubectl_apply(
    context: Dict[str, Any],
    manifest_path: str,
    namespace: Optional[str] = None,
    dry_run: bool = False,
    skip_confirmation: bool = False,
) -> ToolResult:
    """
    Apply Kubernetes manifests to a cluster.

    ⚠️ WARNING: This modifies resources in a Kubernetes cluster!

    Args:
        manifest_path: Path to manifest file or directory
        namespace: Target namespace
        dry_run: If True, only show what would be done
        skip_confirmation: Skip confirmation dialog
    """
    if not EXECUTION_SERVICES_AVAILABLE:
        return ToolResult(
            output="⚠️ Infrastructure execution services not available.",
            sources=[],
        )

    if dry_run:
        result = await infrastructure_executor_service.kubectl_apply(
            manifest_path=manifest_path,
            namespace=namespace,
            dry_run=True,
        )
        return ToolResult(
            output=f"## 🔍 Dry Run - Kubernetes Apply Preview\n\n"
            f"Would apply manifests from: `{manifest_path}`\n"
            f"Namespace: `{namespace or 'default'}`\n\n"
            f"### Changes\n"
            + "\n".join(
                [
                    f"- {c.action} {c.resource_type}/{c.resource_name}"
                    for c in result.changes_applied
                ]
            ),
            sources=[],
        )

    if not skip_confirmation:
        request = execution_confirmation_service.create_execution_request(
            operation_name="infra.kubectl_apply",
            description=f"Apply Kubernetes manifests from {manifest_path}",
            parameters={"manifest_path": manifest_path, "namespace": namespace},
            environment="production",
        )
        return ToolResult(
            output=f"## ⚠️ Kubernetes Apply Confirmation Required\n\n"
            f"**Manifest**: `{manifest_path}`\n"
            f"**Namespace**: `{namespace or 'default'}`\n\n"
            f"**Request ID**: `{request.id}`\n\n"
            f"To proceed, approve this request.",
            sources=[],
        )

    result = await infrastructure_executor_service.kubectl_apply(
        manifest_path=manifest_path,
        namespace=namespace,
    )

    if result.success:
        output = "## ✅ Kubernetes Apply Successful\n\n"
        output += f"**Duration**: {result.duration_seconds:.1f}s\n\n"
        output += "### Applied Resources\n"
        for change in result.changes_applied:
            output += f"- {change.resource_type}/{change.resource_name}\n"
        if result.rollback_command:
            output += f"\n### Rollback\n`{result.rollback_command}`\n"
        return ToolResult(output=output, sources=[])
    else:
        return ToolResult(
            output=f"## ❌ Kubernetes Apply Failed\n\n{result.error}",
            sources=[],
        )


async def helm_install(
    context: Dict[str, Any],
    release_name: str,
    chart: str,
    namespace: Optional[str] = None,
    values_file: Optional[str] = None,
    set_values: Optional[Dict[str, str]] = None,
    dry_run: bool = False,
    skip_confirmation: bool = False,
) -> ToolResult:
    """
    Install a Helm chart.

    Args:
        release_name: Name for the Helm release
        chart: Chart name or path
        namespace: Target namespace
        values_file: Path to values file
        set_values: Values to set via --set
        dry_run: Only show what would be done
        skip_confirmation: Skip confirmation dialog
    """
    if not EXECUTION_SERVICES_AVAILABLE:
        return ToolResult(
            output="⚠️ Infrastructure execution services not available.",
            sources=[],
        )

    if dry_run:
        result = await infrastructure_executor_service.helm_install(
            release_name=release_name,
            chart=chart,
            namespace=namespace,
            values_file=values_file,
            set_values=set_values,
            dry_run=True,
        )
        return ToolResult(
            output=f"## 🔍 Dry Run - Helm Install Preview\n\n"
            f"**Release**: `{release_name}`\n"
            f"**Chart**: `{chart}`\n"
            f"**Namespace**: `{namespace or 'default'}`\n",
            sources=[],
        )

    if not skip_confirmation:
        request = execution_confirmation_service.create_execution_request(
            operation_name="infra.helm_install",
            description=f"Install Helm chart {chart} as {release_name}",
            parameters={
                "release_name": release_name,
                "chart": chart,
                "namespace": namespace,
            },
            environment="production",
        )
        return ToolResult(
            output=f"## ⚠️ Helm Install Confirmation Required\n\n"
            f"**Release**: `{release_name}`\n"
            f"**Chart**: `{chart}`\n\n"
            f"**Request ID**: `{request.id}`",
            sources=[],
        )

    result = await infrastructure_executor_service.helm_install(
        release_name=release_name,
        chart=chart,
        namespace=namespace,
        values_file=values_file,
        set_values=set_values,
    )

    if result.success:
        return ToolResult(
            output=f"## ✅ Helm Install Successful\n\n"
            f"**Release**: `{release_name}`\n"
            f"**Duration**: {result.duration_seconds:.1f}s\n\n"
            f"### Rollback\n`{result.rollback_command}`",
            sources=[],
        )
    else:
        return ToolResult(
            output=f"## ❌ Helm Install Failed\n\n{result.error}",
            sources=[],
        )


# Export tools for the agent dispatcher
INFRASTRUCTURE_TOOLS = {
    # Generation tools
    "infra_generate_terraform": generate_terraform,
    "infra_generate_cloudformation": generate_cloudformation,
    "infra.generate_k8s": generate_kubernetes_manifests,
    "infra_generate_docker_compose": generate_docker_compose,
    "infra_generate_helm": generate_helm_chart,
    "infra_analyze_needs": analyze_infrastructure_needs,
    # Real execution tools
    "infra_terraform_plan": terraform_plan,
    "infra_terraform_apply": terraform_apply,
    "infra_terraform_destroy": terraform_destroy,
    "infra_kubectl_apply": kubectl_apply,
    "infra_helm_install": helm_install,
}
