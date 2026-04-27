variable "name_prefix" {
  type = string
}

variable "ecs_cluster_arn" {
  type = string
}

variable "tags" {
  type = map(string)
}
