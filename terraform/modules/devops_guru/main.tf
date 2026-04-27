# Enable DevOps Guru
resource "aws_devopsguru_resource_collection" "ecs" {
  type = "AWS_CLOUD_FORMATION"

  cloudformation {
    stack_names = ["*"]
  }
}

# EventBridge Integration for DevOps Guru Insights
resource "aws_sns_topic" "devops_guru_insights" {
  name = "${var.name_prefix}-devops-guru-insights"

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-devops-guru-insights-topic"
  })
}

resource "aws_devopsguru_notification_channel" "sns" {
  sns {
    topic_arn = aws_sns_topic.devops_guru_insights.arn
  }
}

# CloudWatch Event Rule to capture DevOps Guru Insights
resource "aws_cloudwatch_event_rule" "devops_guru_insights_rule" {
  name        = "${var.name_prefix}-devops-guru-insights-rule"
  description = "Capture DevOps Guru anomaly and insight events"

  event_pattern = jsonencode({
    source = ["aws.devops-guru"]
    detail-type = [
      "DevOps Guru Insight",
      "DevOps Guru Anomaly Report"
    ]
  })

  tags = var.tags
}

# CloudWatch Log Group for DevOps Guru Events
resource "aws_cloudwatch_log_group" "devops_guru_logs" {
  name              = "/aws/devops-guru/${var.name_prefix}"
  retention_in_days = 30

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-devops-guru-logs"
  })
}

resource "aws_cloudwatch_event_target" "devops_guru_logs" {
  rule      = aws_cloudwatch_event_rule.devops_guru_insights_rule.name
  target_id = "DevOpsGuruLogGroup"
  arn       = aws_cloudwatch_log_group.devops_guru_logs.arn

}

# Resource Policy for EventBridge to write to CloudWatch
data "aws_iam_policy_document" "eventbridge_log_policy" {
  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com", "delivery.logs.amazonaws.com"]
    }

    resources = ["${aws_cloudwatch_log_group.devops_guru_logs.arn}:*"]
  }
}

resource "aws_cloudwatch_log_resource_policy" "devops_guru" {
  policy_document = data.aws_iam_policy_document.eventbridge_log_policy.json
  policy_name     = "${var.name_prefix}-devops-guru-eventbridge-logs"
}
