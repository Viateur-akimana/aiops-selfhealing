variable "name_prefix" {
  type = string
}

variable "ecs_cluster_name" {
  type = string
}

variable "ecs_services" {
  type = map(string)
}

variable "tags" {
  type = map(string)
}
