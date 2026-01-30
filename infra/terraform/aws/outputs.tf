output "alb_dns_name" {
  value       = aws_lb.main.dns_name
  description = "Load balancer DNS name"
}

output "ecs_cluster_name" {
  value       = aws_ecs_cluster.main.name
  description = "ECS cluster name"
}

output "ecs_service_name" {
  value       = aws_ecs_service.api.name
  description = "ECS service name"
}

output "rds_endpoint" {
  value       = var.enable_rds ? aws_db_instance.postgres[0].endpoint : null
  description = "RDS endpoint (if enabled)"
}

output "redis_endpoint" {
  value       = var.enable_redis ? aws_elasticache_cluster.redis[0].cache_nodes[0].address : null
  description = "Redis endpoint (if enabled)"
}
