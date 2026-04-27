terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  name_prefix = var.project_name
  tags = {
    Project   = "TechStream"
    ManagedBy = "Terraform"
  }
}

module "networking" {
  source = "./modules/networking"

  name_prefix = local.name_prefix
  tags        = local.tags
}

module "ecr" {
  source = "./modules/ecr"

  name_prefix = local.name_prefix
  tags        = local.tags
}

module "ecs" {
  source = "./modules/ecs"

  name_prefix          = local.name_prefix
  vpc_id               = module.networking.vpc_id
  private_subnet_ids   = module.networking.private_subnet_ids
  alb_security_group   = module.networking.alb_security_group
  ecs_tasks_security_group = module.networking.ecs_tasks_security_group
  alb_target_group_arn = module.networking.alb_target_group_arn

  web_app_image          = "${module.ecr.web_app_repository_url}:latest"
  web_app_container_port = var.container_port
  web_app_cpu            = var.ecs_task_cpu
  web_app_memory         = var.ecs_task_memory
  web_app_desired_count  = var.ecs_desired_count

  remediation_image  = "${module.ecr.remediation_repository_url}:latest"
  remediation_port   = 8085
  remediation_cpu    = 256
  remediation_memory = 512

  analyzer_image  = "${module.ecr.analyzer_repository_url}:latest"
  analyzer_port   = 9000
  analyzer_cpu    = 256
  analyzer_memory = 512

  prometheus_image  = "prom/prometheus:v2.51.2"
  prometheus_port   = 9090
  prometheus_cpu    = 256
  prometheus_memory = 512

  grafana_image  = "grafana/grafana:10.4.2"
  grafana_port   = 3000
  grafana_cpu    = 256
  grafana_memory = 512

  tags = local.tags

  depends_on = [module.ecr]
}

module "monitoring" {
  source = "./modules/monitoring"

  name_prefix = local.name_prefix

  ecs_cluster_name = module.ecs.ecs_cluster_name
  ecs_services     = module.ecs.ecs_service_names

  tags = local.tags

  depends_on = [module.ecs]
}

module "lambda_remediation" {
  source = "./modules/lambda"

  name_prefix = local.name_prefix

  ecs_cluster_name = module.ecs.ecs_cluster_name
  ecs_service_name = module.ecs.web_app_service_name

  tags = local.tags

  depends_on = [module.ecs]
}

module "devops_guru" {
  source = "./modules/devops_guru"

  name_prefix     = local.name_prefix
  ecs_cluster_arn = module.ecs.ecs_cluster_arn

  tags = local.tags

  depends_on = [module.ecs]
}
