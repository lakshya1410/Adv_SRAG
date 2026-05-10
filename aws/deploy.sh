#!/bin/bash

# Self-RAG AWS Deployment Script
# ──────────────────────────────────────────
# Usage: ./deploy-to-aws.sh <action> <environment>
# Examples:
#   ./deploy-to-aws.sh setup production
#   ./deploy-to-aws.sh deploy production
#   ./deploy-to-aws.sh logs production

set -e

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPOSITORY="self-rag"
ECS_CLUSTER="self-rag-cluster"
ECS_SERVICE="self-rag-service"
ECS_TASK_DEFINITION="self-rag-task"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_header() {
    echo -e "${BLUE}══════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}══════════════════════════════════════════${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# Action: Setup
setup_infrastructure() {
    print_header "Setting up AWS Infrastructure"
    
    # Create ECR repository
    print_info "Creating ECR repository..."
    aws ecr create-repository \
        --repository-name $ECR_REPOSITORY \
        --region $AWS_REGION \
        --image-scanning-configuration scanOnPush=true \
        --image-tag-mutability MUTABLE || print_info "Repository already exists"
    
    # Create S3 buckets
    print_info "Creating S3 buckets..."
    aws s3api create-bucket \
        --bucket self-rag-documents-prod \
        --region $AWS_REGION \
        --create-bucket-configuration LocationConstraint=$AWS_REGION || print_info "Documents bucket already exists"
    
    aws s3api create-bucket \
        --bucket self-rag-sessions-prod \
        --region $AWS_REGION \
        --create-bucket-configuration LocationConstraint=$AWS_REGION || print_info "Sessions bucket already exists"
    
    # Create Secrets Manager secret
    print_info "Creating Secrets Manager secret..."
    if [ -z "$GROQ_API_KEY" ]; then
        print_error "GROQ_API_KEY environment variable not set"
        exit 1
    fi
    
    aws secretsmanager create-secret \
        --name self-rag/groq-api-key \
        --description "Groq API key for Self-RAG application" \
        --secret-string "$GROQ_API_KEY" \
        --region $AWS_REGION || print_info "Secret already exists"
    
    # Create CloudWatch log group
    print_info "Creating CloudWatch log group..."
    aws logs create-log-group \
        --log-group-name /ecs/self-rag \
        --region $AWS_REGION || print_info "Log group already exists"
    
    aws logs put-retention-policy \
        --log-group-name /ecs/self-rag \
        --retention-in-days 30 \
        --region $AWS_REGION
    
    print_success "Infrastructure setup complete"
}

# Action: Build and Push
build_and_push() {
    print_header "Building and Pushing Docker Image"
    
    image_tag=$(date +%s)
    registry_url="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
    
    # Build Docker image
    print_info "Building Docker image..."
    docker build -t $ECR_REPOSITORY:$image_tag .
    docker tag $ECR_REPOSITORY:$image_tag $registry_url/$ECR_REPOSITORY:$image_tag
    docker tag $ECR_REPOSITORY:$image_tag $registry_url/$ECR_REPOSITORY:latest
    
    # Login to ECR
    print_info "Logging in to ECR..."
    aws ecr get-login-password --region $AWS_REGION | \
        docker login --username AWS --password-stdin $registry_url
    
    # Push image
    print_info "Pushing image to ECR..."
    docker push $registry_url/$ECR_REPOSITORY:$image_tag
    docker push $registry_url/$ECR_REPOSITORY:latest
    
    print_success "Image pushed to ECR"
    echo "Image URI: $registry_url/$ECR_REPOSITORY:$image_tag"
}

# Action: Deploy
deploy_to_ecs() {
    print_header "Deploying to ECS"
    
    registry_url="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
    image_uri="$registry_url/$ECR_REPOSITORY:latest"
    
    # Get current task definition
    print_info "Fetching current task definition..."
    aws ecs describe-task-definition \
        --task-definition $ECS_TASK_DEFINITION \
        --region $AWS_REGION \
        --query taskDefinition > task-definition.json
    
    # Register new task definition
    print_info "Registering new task definition..."
    new_task_def=$(jq \
        --arg image "$image_uri" \
        '.containerDefinitions[0].image = $image | del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities)' \
        task-definition.json)
    
    task_def_arn=$(aws ecs register-task-definition \
        --cli-input-json "$new_task_def" \
        --region $AWS_REGION \
        --query 'taskDefinition.taskDefinitionArn' \
        --output text)
    
    print_success "Task definition registered: $task_def_arn"
    
    # Update service
    print_info "Updating ECS service..."
    aws ecs update-service \
        --cluster $ECS_CLUSTER \
        --service $ECS_SERVICE \
        --task-definition $task_def_arn \
        --force-new-deployment \
        --region $AWS_REGION
    
    # Wait for service stabilization
    print_info "Waiting for service to stabilize..."
    aws ecs wait services-stable \
        --cluster $ECS_CLUSTER \
        --services $ECS_SERVICE \
        --region $AWS_REGION
    
    print_success "Deployment complete"
    
    # Show service status
    print_info "Current service status:"
    aws ecs describe-services \
        --cluster $ECS_CLUSTER \
        --services $ECS_SERVICE \
        --region $AWS_REGION \
        --query 'services[0].[runningCount,desiredCount,deployments[0].taskDefinition]' \
        --output table
}

# Action: View Logs
view_logs() {
    print_header "Viewing CloudWatch Logs"
    
    print_info "Streaming logs from the last hour..."
    aws logs tail /ecs/self-rag --follow --since 1h --region $AWS_REGION
}

# Action: Check Status
check_status() {
    print_header "Checking Service Status"
    
    # Service info
    print_info "Service Status:"
    aws ecs describe-services \
        --cluster $ECS_CLUSTER \
        --services $ECS_SERVICE \
        --region $AWS_REGION \
        --query 'services[0].[serviceName,status,runningCount,desiredCount]' \
        --output table
    
    # Task info
    print_info "Running Tasks:"
    aws ecs list-tasks \
        --cluster $ECS_CLUSTER \
        --service-name $ECS_SERVICE \
        --region $AWS_REGION \
        --query 'taskArns' \
        --output text | while read task_arn; do
        aws ecs describe-tasks \
            --cluster $ECS_CLUSTER \
            --tasks $task_arn \
            --region $AWS_REGION \
            --query 'tasks[0].[taskArn,lastStatus,startedAt]' \
            --output table
    done
}

# Main
main() {
    action=${1:-help}
    environment=${2:-production}
    
    case $action in
        setup)
            setup_infrastructure
            ;;
        build)
            build_and_push
            ;;
        deploy)
            build_and_push
            deploy_to_ecs
            ;;
        logs)
            view_logs
            ;;
        status)
            check_status
            ;;
        *)
            cat << EOF
Usage: $0 <action> [environment]

Actions:
  setup       - Set up AWS infrastructure (ECR, S3, Secrets, etc.)
  build       - Build Docker image and push to ECR
  deploy      - Build, push, and deploy to ECS
  logs        - Stream CloudWatch logs
  status      - Check service status

Environment defaults to 'production'

Examples:
  $0 setup production
  $0 deploy production
  $0 logs production
  $0 status production

EOF
            exit 1
            ;;
    esac
}

main "$@"
