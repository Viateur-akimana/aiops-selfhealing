#!/bin/bash

set -e

AWS_REGION=${AWS_REGION:-"us-east-1"}
PROJECT_NAME=${PROJECT_NAME:-"techstream"}

echo "TechStream AIOps - Terraform Deployment"
echo "========================================"

if ! command -v terraform &> /dev/null; then
    echo "ERROR: Terraform not installed"
    exit 1
fi

if ! command -v aws &> /dev/null; then
    echo "ERROR: AWS CLI not installed"
    exit 1
fi

cd terraform

echo "Initializing Terraform..."
terraform init

echo "Validating Terraform configuration..."
terraform validate

echo "Planning Terraform deployment..."
PLAN_FILE="terraform.tfplan"
terraform plan -out="$PLAN_FILE"

echo "Review the plan above. Do you want to apply? (yes/no)"
read -r CONFIRM

if [[ $CONFIRM != "yes" ]]; then
    echo "Deployment cancelled"
    exit 0
fi

echo "Applying Terraform configuration..."
terraform apply "$PLAN_FILE"

echo "Deployment Complete!"
echo ""
echo "Outputs:"
terraform output

ALB_URL=$(terraform output -raw alb_url 2>/dev/null || echo "URL not available")
GRAFANA_URL=$(terraform output -raw grafana_url 2>/dev/null || echo "URL not available")
PROMETHEUS_URL=$(terraform output -raw prometheus_url 2>/dev/null || echo "URL not available")

echo ""
echo "Access URLs:"
echo "  Application: $ALB_URL"
echo "  Grafana: $GRAFANA_URL"
echo "  Prometheus: $PROMETHEUS_URL"

cd ..

