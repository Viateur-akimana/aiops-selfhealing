output "web_app_repository_url" {
  value = data.aws_ecr_repository.web_app.repository_url
}

output "web_app_repository_arn" {
  value = data.aws_ecr_repository.web_app.arn
}

output "remediation_repository_url" {
  value = data.aws_ecr_repository.remediation.repository_url
}

output "remediation_repository_arn" {
  value = data.aws_ecr_repository.remediation.arn
}

output "analyzer_repository_url" {
  value = data.aws_ecr_repository.analyzer.repository_url
}

output "analyzer_repository_arn" {
  value = data.aws_ecr_repository.analyzer.arn
}
