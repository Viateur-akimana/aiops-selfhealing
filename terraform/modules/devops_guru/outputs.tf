output "devops_guru_collection_id" {
  value = aws_devopsguru_resource_collection.ecs.id
}

output "insights_topic_arn" {
  value = aws_sns_topic.devops_guru_insights.arn
}

output "devops_guru_console_url" {
  value = "https://console.aws.amazon.com/devops-guru/home"
}
