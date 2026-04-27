data "aws_ecr_repository" "web_app" {
  name = "${var.name_prefix}-web-app"
}

data "aws_ecr_repository" "remediation" {
  name = "${var.name_prefix}-remediation"
}

data "aws_ecr_repository" "analyzer" {
  name = "${var.name_prefix}-analyzer"
}
