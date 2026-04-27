variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "techstream"
}

variable "container_port" {
  description = "Container port for web app"
  type        = number
  default     = 5000
}

variable "ecs_task_cpu" {
  description = "Task CPU units"
  type        = number
  default     = 256
}

variable "ecs_task_memory" {
  description = "Task memory in MB"
  type        = number
  default     = 512
}

variable "ecs_desired_count" {
  description = "Number of ECS tasks"
  type        = number
  default     = 2
}
