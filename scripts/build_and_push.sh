#!/bin/bash

set -e

AWS_REGION=${AWS_REGION:-"us-east-1"}
PROJECT_NAME=${PROJECT_NAME:-"techstream"}
REGISTRY_NAME="${PROJECT_NAME}"

echo "TechStream AIOps - AWS ECR Push"
echo "=============================="

if ! command -v aws &> /dev/null; then
    echo "ERROR: AWS CLI not installed"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker not installed"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
if [ -z "$ACCOUNT_ID" ]; then
    echo "ERROR: Cannot get AWS account ID"
    exit 1
fi

echo "AWS Account ID: $ACCOUNT_ID"
echo "Creating ECR repositories..."

for SERVICE in "web-app" "remediation" "analyzer"; do
    REPO_NAME="${REGISTRY_NAME}-${SERVICE}"
    
    if aws ecr describe-repositories --repository-names "$REPO_NAME" --region "$AWS_REGION" &>/dev/null; then
        echo "Repository already exists: $REPO_NAME"
    else
        echo "Creating ECR repository: $REPO_NAME"
        aws ecr create-repository \
            --repository-name "$REPO_NAME" \
            --region "$AWS_REGION" \
            --encryption-configuration encryptionType=AES256 \
            --image-scanning-configuration scanOnPush=true \
            --image-tag-mutability MUTABLE &>/dev/null
    fi
done

echo "Building and pushing Docker images..."
aws ecr get-login-password --region "$AWS_REGION" | \
    docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

for SERVICE in "web-app" "remediation" "analyzer"; do
    echo "Processing $SERVICE..."
    REPO_URL="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/${REGISTRY_NAME}-${SERVICE}"
    
    case $SERVICE in
        web-app)
            docker build -t "${REGISTRY_NAME}-web-app:latest" -f app/Dockerfile app/
            docker tag "${REGISTRY_NAME}-web-app:latest" "$REPO_URL:latest"
            docker push "$REPO_URL:latest"
            ;;
        remediation)
            docker build -t "${REGISTRY_NAME}-remediation:latest" -f remediation/Dockerfile remediation/
            docker tag "${REGISTRY_NAME}-remediation:latest" "$REPO_URL:latest"
            docker push "$REPO_URL:latest"
            ;;
        analyzer)
            docker build -t "${REGISTRY_NAME}-analyzer:latest" -f ai_analyzer/Dockerfile ai_analyzer/
            docker tag "${REGISTRY_NAME}-analyzer:latest" "$REPO_URL:latest"
            docker push "$REPO_URL:latest"
            ;;
    esac
done

echo "SUCCESS: All images pushed to ECR"
echo ""
echo "Next: Run ./scripts/deploy_terraform.sh"

