output "vpc_id" {
  value = aws_vpc.main.id
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "alb_security_group" {
  value = aws_security_group.alb.id
}

output "ecs_tasks_security_group" {
  value = aws_security_group.ecs_tasks.id
}

output "alb_arn" {
  value = aws_lb.main.arn
}

output "alb_dns_name" {
  value = aws_lb.main.dns_name
}

output "alb_target_group_arn" {
  value = aws_lb_target_group.web_app.arn
}

output "alb_target_groups" {
  value = {
    web_app      = aws_lb_target_group.web_app.arn
    prometheus   = aws_lb_target_group.monitoring["prometheus"].arn
    grafana      = aws_lb_target_group.monitoring["grafana"].arn
    alertmanager = aws_lb_target_group.monitoring["alertmanager"].arn
  }
}
