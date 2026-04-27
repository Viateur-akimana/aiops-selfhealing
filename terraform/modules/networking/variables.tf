variable "name_prefix" {
  type = string
}

variable "tags" {
  type = map(string)
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "availability_zones" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b"]
}

variable "container_port" {
  type    = number
  default = 5000
}
