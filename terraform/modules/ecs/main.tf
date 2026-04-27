resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${var.name_prefix}"
  retention_in_days = 30

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-ecs-logs"
  })
}

resource "aws_ecs_cluster" "main" {
  name = "${var.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-cluster"
  })
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name = aws_ecs_cluster.main.name

  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    base              = 1
    weight            = 100
    capacity_provider = "FARGATE"
  }
}

resource "aws_iam_role" "ecs_task_execution_role" {
  name = "${var.name_prefix}-ecs-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_role_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task_role" {
  name = "${var.name_prefix}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })

  tags = var.tags
}

resource "aws_ecs_task_definition" "web_app" {
  family                   = "${var.name_prefix}-web-app"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.web_app_cpu
  memory                   = var.web_app_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "web-app"
      image     = var.web_app_image
      essential = true
      portMappings = [
        {
          containerPort = var.web_app_container_port
          hostPort      = var.web_app_container_port
          protocol      = "tcp"
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "web-app"
        }
      }
      environment = [
        {
          name  = "PORT"
          value = tostring(var.web_app_container_port)
        }
      ]
    }
  ])

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-web-app-td"
  })
}

resource "aws_ecs_service" "web_app" {
  name            = "${var.name_prefix}-web-app-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.web_app.arn
  desired_count   = var.web_app_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_tasks_security_group]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = var.alb_target_group_arn
    container_name   = "web-app"
    container_port   = var.web_app_container_port
  }

  enable_ecs_managed_tags = true
  propagate_tags          = "SERVICE"

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-web-app-service"
  })

  depends_on = [
    aws_iam_role.ecs_task_execution_role
  ]
}

resource "aws_appautoscaling_target" "web_app" {
  max_capacity       = 4
  min_capacity       = var.web_app_desired_count
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.web_app.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "web_app_cpu" {
  name               = "${var.name_prefix}-web-app-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.web_app.resource_id
  scalable_dimension = aws_appautoscaling_target.web_app.scalable_dimension
  service_namespace  = aws_appautoscaling_target.web_app.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value = 70.0
  }
}

resource "aws_appautoscaling_policy" "web_app_memory" {
  name               = "${var.name_prefix}-web-app-memory-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.web_app.resource_id
  scalable_dimension = aws_appautoscaling_target.web_app.scalable_dimension
  service_namespace  = aws_appautoscaling_target.web_app.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageMemoryUtilization"
    }
    target_value = 80.0
  }
}

resource "aws_ecs_task_definition" "remediation" {
  family                   = "${var.name_prefix}-remediation"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.remediation_cpu
  memory                   = var.remediation_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "remediation"
      image     = var.remediation_image
      essential = true
      portMappings = [
        {
          containerPort = var.remediation_port
          hostPort      = var.remediation_port
          protocol      = "tcp"
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "remediation"
        }
      }
      environment = [
        {
          name  = "PORT"
          value = tostring(var.remediation_port)
        }
      ]
    }
  ])

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-remediation-td"
  })
}

resource "aws_ecs_service" "remediation" {
  name            = "${var.name_prefix}-remediation-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.remediation.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_tasks_security_group]
    assign_public_ip = false
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-remediation-service"
  })
}

resource "aws_ecs_task_definition" "analyzer" {
  family                   = "${var.name_prefix}-analyzer"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.analyzer_cpu
  memory                   = var.analyzer_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "analyzer"
      image     = var.analyzer_image
      essential = true
      portMappings = [
        {
          containerPort = var.analyzer_port
          hostPort      = var.analyzer_port
          protocol      = "tcp"
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "analyzer"
        }
      }
    }
  ])

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-analyzer-td"
  })
}

resource "aws_ecs_service" "analyzer" {
  name            = "${var.name_prefix}-analyzer-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.analyzer.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_tasks_security_group]
    assign_public_ip = false
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-analyzer-service"
  })
}



data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
