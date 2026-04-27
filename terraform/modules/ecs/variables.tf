variable "name_prefix" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "alb_security_group" {
  type = string
}

variable "alb_target_group_arn" {
  type = string
}

variable "web_app_image" {
  type = string
}

variable "web_app_container_port" {
  type = number
}

variable "web_app_cpu" {
  type = number
}

variable "web_app_memory" {
  type = number
}

variable "web_app_desired_count" {
  type = number
}

variable "remediation_image" {
  type = string
}

variable "remediation_port" {
  type = number
}

variable "remediation_cpu" {
  type = number
}

variable "remediation_memory" {
  type = number
}

variable "analyzer_image" {
  type = string
}

variable "analyzer_port" {
  type = number
}

variable "analyzer_cpu" {
  type = number
}

variable "analyzer_memory" {
  type = number
}

variable "prometheus_image" {
  type = string
}

variable "prometheus_port" {
  type = number
}

variable "prometheus_cpu" {
  type = number
}

variable "prometheus_memory" {
  type = number
}

variable "grafana_image" {
  type = string
}

variable "grafana_port" {
  type = number
}

variable "grafana_cpu" {
  type = number
}

variable "grafana_memory" {
  type = number
}

variable "ecs_tasks_security_group" {
  type = string
}

variable "tags" {
  type = map(string)
}
