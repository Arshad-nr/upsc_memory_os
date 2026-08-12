# ── Outputs ──────────────────────────────────────────────────────

output "alb_dns_name" {
  description = "Public URL of the application (ALB DNS)"
  value       = "http://${aws_lb.main.dns_name}"
}

output "backend_health_url" {
  description = "Backend health check endpoint"
  value       = "http://${aws_lb.main.dns_name}/health"
}

output "ecr_backend_url" {
  description = "ECR repository URL for backend images"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecr_frontend_url" {
  description = "ECR repository URL for frontend images"
  value       = aws_ecr_repository.frontend.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name (used in CI/CD)"
  value       = aws_ecs_cluster.main.name
}

output "backend_service_name" {
  description = "Backend ECS service name (used in CI/CD)"
  value       = aws_ecs_service.backend.name
}

output "frontend_service_name" {
  description = "Frontend ECS service name (used in CI/CD)"
  value       = aws_ecs_service.frontend.name
}
