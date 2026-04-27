variable "name_prefix" {
  type = string
}

variable "tags" {
  type = map(string)
}

variable "image_tag_mutability" {
  type    = string
  default = "MUTABLE"
}

variable "scan_on_push" {
  type    = bool
  default = true
}
