output "function_names" {
  value = {
    auto_restart = aws_lambda_function.auto_restart.function_name
    scale_out    = aws_lambda_function.scale_out.function_name
  }
}

output "lambda_arns" {
  value = {
    auto_restart = aws_lambda_function.auto_restart.arn
    scale_out    = aws_lambda_function.scale_out.arn
  }
}

output "eventbridge_rules" {
  value = {
    high_error_rate = aws_cloudwatch_event_rule.high_error_rate_rule.name
    high_saturation = aws_cloudwatch_event_rule.high_saturation_rule.name
  }
}
