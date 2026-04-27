# IAM Role for Lambda
resource "aws_iam_role" "lambda_remediation_role" {
  name = "${var.name_prefix}-lambda-remediation-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_remediation_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_ecs_policy" {
  name = "${var.name_prefix}-lambda-ecs-policy"
  role = aws_iam_role.lambda_remediation_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecs:UpdateService",
          "ecs:DescribeServices",
          "ecs:DescribeTaskDefinition",
          "ecs:DescribeTasks",
          "ecs:ListTasks",
          "ecs:RunTask"
        ]
        Resource = "*"
      }
    ]
  })
}

# Lambda Layer with Dependencies
data "archive_file" "lambda_layer" {
  type        = "zip"
  source_dir  = "${path.root}/../lambda_code/layer"
  output_path = "${path.root}/../lambda_code/layer.zip"
}

resource "aws_lambda_layer_version" "dependencies" {
  filename   = data.archive_file.lambda_layer.output_path
  layer_name = "${var.name_prefix}-dependencies"

  source_code_hash = data.archive_file.lambda_layer.output_base64sha256

  compatible_runtimes = ["python3.11"]
}

# Lambda Function for Auto-Restart (Self-Healing)
data "archive_file" "lambda_auto_restart" {
  type        = "zip"
  source_file = "${path.root}/../lambda_code/restart_function.py"
  output_path = "${path.root}/../lambda_code/restart_function.zip"
}

resource "aws_lambda_function" "auto_restart" {
  filename      = data.archive_file.lambda_auto_restart.output_path
  function_name = "${var.name_prefix}-auto-restart"
  role          = aws_iam_role.lambda_remediation_role.arn
  handler       = "restart_function.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30

  source_code_hash = data.archive_file.lambda_auto_restart.output_base64sha256

  environment {
    variables = {
      CLUSTER_NAME = var.ecs_cluster_name
      SERVICE_NAME = var.ecs_service_name
      ENVIRONMENT  = "production"
    }
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-auto-restart"
  })
}

# Lambda Function for Scale-Out (Auto-Scaling Trigger)
data "archive_file" "lambda_scale_out" {
  type        = "zip"
  source_file = "${path.root}/../lambda_code/scale_out_function.py"
  output_path = "${path.root}/../lambda_code/scale_out_function.zip"
}

resource "aws_lambda_function" "scale_out" {
  filename      = data.archive_file.lambda_scale_out.output_path
  function_name = "${var.name_prefix}-scale-out"
  role          = aws_iam_role.lambda_remediation_role.arn
  handler       = "scale_out_function.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30

  source_code_hash = data.archive_file.lambda_scale_out.output_base64sha256

  environment {
    variables = {
      CLUSTER_NAME = var.ecs_cluster_name
      SERVICE_NAME = var.ecs_service_name
      ENVIRONMENT  = "production"
    }
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-scale-out"
  })
}

# EventBridge Rule: High Error Rate -> Auto-Restart
resource "aws_cloudwatch_event_rule" "high_error_rate_rule" {
  name        = "${var.name_prefix}-high-error-rate-rule"
  description = "Trigger remediation on high error rate"

  event_pattern = jsonencode({
    source      = ["aws.cloudwatch"]
    detail-type = ["CloudWatch Alarm State Change"]
    detail = {
      alarmName = [
        "${var.name_prefix}-high-error-rate"
      ]
      state = {
        value = ["ALARM"]
      }
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "error_rate_target" {
  rule      = aws_cloudwatch_event_rule.high_error_rate_rule.name
  target_id = "RestartService"
  arn       = aws_lambda_function.auto_restart.arn
}

resource "aws_lambda_permission" "allow_eventbridge_error" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.auto_restart.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.high_error_rate_rule.arn
}

# EventBridge Rule: High Saturation -> Scale Out
resource "aws_cloudwatch_event_rule" "high_saturation_rule" {
  name        = "${var.name_prefix}-high-saturation-rule"
  description = "Trigger scale-out on high saturation"

  event_pattern = jsonencode({
    source      = ["aws.cloudwatch"]
    detail-type = ["CloudWatch Alarm State Change"]
    detail = {
      alarmName = [
        "${var.name_prefix}-high-cpu-saturation",
        "${var.name_prefix}-high-memory-saturation"
      ]
      state = {
        value = ["ALARM"]
      }
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "saturation_target" {
  rule      = aws_cloudwatch_event_rule.high_saturation_rule.name
  target_id = "ScaleOut"
  arn       = aws_lambda_function.scale_out.arn
}

resource "aws_lambda_permission" "allow_eventbridge_saturation" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scale_out.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.high_saturation_rule.arn
}

# CloudWatch Logs for Lambda
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.name_prefix}"
  retention_in_days = 30

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-lambda-logs"
  })
}
