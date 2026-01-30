variable "region" {
  type        = string
  description = "AWS region"
  default     = "us-east-1"
}

variable "name_prefix" {
  type        = string
  description = "Prefix for AWS resources"
  default     = "navi"
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR"
  default     = "10.20.0.0/16"
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "Public subnet CIDRs"
  default     = ["10.20.1.0/24", "10.20.2.0/24"]
}

variable "container_image" {
  type        = string
  description = "Container image for backend"
}

variable "container_port" {
  type        = number
  description = "Container port"
  default     = 8787
}

variable "desired_count" {
  type        = number
  description = "Desired ECS service count"
  default     = 2
}

variable "cpu" {
  type        = number
  description = "Fargate CPU units"
  default     = 512
}

variable "memory" {
  type        = number
  description = "Fargate memory (MiB)"
  default     = 1024
}

variable "env_vars" {
  type        = map(string)
  description = "Environment variables for the container"
  default     = {}
}

variable "enable_rds" {
  type        = bool
  description = "Provision RDS Postgres (minimal)"
  default     = false
}

variable "rds_instance_class" {
  type        = string
  description = "RDS instance class"
  default     = "db.t4g.micro"
}

variable "rds_allocated_storage" {
  type        = number
  description = "RDS storage (GB)"
  default     = 20
}

variable "rds_username" {
  type        = string
  description = "RDS master username"
  default     = "navi"
}

variable "rds_password" {
  type        = string
  description = "RDS master password"
  sensitive   = true
  default     = ""
}

variable "enable_redis" {
  type        = bool
  description = "Provision Redis (Elasticache)"
  default     = false
}

variable "redis_node_type" {
  type        = string
  description = "Redis node type"
  default     = "cache.t4g.micro"
}
