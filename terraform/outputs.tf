output "alb_dns_name" {
  description = "DNS name of the load balancer"
  value       = module.networking.alb_dns_name
}

output "alb_url" {
  description = "Full URL to access the application"
  value       = "http://${module.networking.alb_dns_name}"
}

output "grafana_url" {
  description = "Grafana dashboard URL"
  value       = "http://${module.networking.alb_dns_name}:3000"
}

output "prometheus_url" {
  description = "Prometheus URL"
  value       = "http://${module.networking.alb_dns_name}:9090"
}

output "ecr_repositories" {
  description = "ECR repository URLs"
  value = {
    web_app     = module.ecr.web_app_repository_url
    remediation = module.ecr.remediation_repository_url
    analyzer    = module.ecr.analyzer_repository_url
  }
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.ecs.ecs_cluster_name
}

output "cloudwatch_dashboard_url" {
  description = "CloudWatch dashboard for Golden Signals"
  value       = "https://console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=TechStream-GoldenSignals"
}

output "devops_guru_console_url" {
  description = "DevOps Guru console URL"
  value       = "https://console.aws.amazon.com/devops-guru/"
}

output "lambda_functions" {
  description = "Lambda function names"
  value       = module.lambda_remediation.function_names
}

output "sns_topic_arn" {
  description = "SNS topic for alerts"
  value       = module.monitoring.sns_topic_arn
}
