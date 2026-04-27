output "ecs_cluster_id" {
  value = aws_ecs_cluster.main.id
}

output "ecs_cluster_arn" {
  value = aws_ecs_cluster.main.arn
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "web_app_service_name" {
  value = aws_ecs_service.web_app.name
}

output "ecs_service_names" {
  value = {
    web_app     = aws_ecs_service.web_app.name
    remediation = aws_ecs_service.remediation.name
    analyzer    = aws_ecs_service.analyzer.name
  }
}

output "ecs_log_group" {
  value = aws_cloudwatch_log_group.ecs.name
}
