# Self-RAG: Complete AWS + Docker Deployment Guide

**Purpose**: Deploy Self-RAG application on AWS using Docker containerization with ECS Fargate, ECR, S3, and supporting services.

**Current Status**: ✅ **PRODUCTION-READY FOR AWS**

**Last Updated**: April 17, 2026

---

## 📋 Table of Contents

1. [Architecture Overview](#-aws-architecture-overview)
2. [Prerequisites](#-prerequisites)
3. [Docker Setup](#-docker-setup)
4. [AWS Infrastructure Setup](#-aws-infrastructure-setup)
5. [Deployment Steps](#-deployment-steps)
6. [Configuration & Secrets](#-configuration--secrets)
7. [Scaling & Performance](#-scaling--performance)
8. [Monitoring & Logging](#-monitoring--logging)
9. [CI/CD Pipeline](#-cicd-pipeline)
10. [Troubleshooting](#-troubleshooting)
11. [Cost Optimization](#-cost-optimization)

---

## 🏗️ AWS Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    CloudFront CDN                               │
│              (Fast content delivery globally)                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│           Application Load Balancer (ALB)                       │
│              (Auto-scaling, health checks)                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
      ┌────────────────────┼────────────────────┐
      │                    │                    │
┌─────▼─────┐      ┌──────▼──────┐      ┌──────▼──────┐
│  ECS Task  │      │  ECS Task   │      │  ECS Task   │
│ (Docker    │      │ (Docker     │      │ (Docker     │
│ Container) │      │ Container)  │      │ Container)  │
│ Port 5000  │      │ Port 5000   │      │ Port 5000   │
└────────────┘      └─────────────┘      └─────────────┘
      │                    │                    │
      └────────────────────┼────────────────────┘
                           │
          ┌────────────────┴────────────────┐
          │                                 │
     ┌────▼─────┐                  ┌────────▼─────┐
     │ RDS MySQL │                  │   S3 Bucket  │
     │(optional) │                  │(PDF storage, │
     │Persistence│                  │ logs, session│
     │           │                  │ data)        │
     └───────────┘                  └──────────────┘
          │                                 │
     ┌────▼─────────────────────────────────▼─────┐
     │     CloudWatch Logs & Monitoring            │
     │  - Application logs                         │
     │  - ECS performance metrics                  │
     │  - ALB access logs                          │
     │  - Alarms for errors/scaling                │
     └──────────────────────────────────────────────┘
```

### External Integrations

```
┌─────────────────────────────────────────────────────┐
│  Self-RAG Application (ECS Fargate)                 │
├─────────────────────────────────────────────────────┤
│  • Flask 3.0.0 API Server                           │
│  • LangGraph Self-RAG Pipeline (9 nodes)            │
│  • Embedding Service (all-MiniLM-L6-v2)             │
│  • FAISS Indexing (in-memory per session)           │
├─────────────────────────────────────────────────────┤
│  External APIs:                                     │
│  • Groq API → LLM inference (llama-3.3-70b)        │
│  • AWS S3 → Document & session storage              │
│  • AWS SecretsManager → Credentials                 │
│  • AWS CloudWatch → Logging                         │
└─────────────────────────────────────────────────────┘
```

---

## 📋 Prerequisites

### Local Development

```bash
# Required software
- Docker Desktop 4.0+
- AWS CLI v2
- Git
- Python 3.11+ (for local testing)
- Docker Compose (included with Docker Desktop)

# AWS Requirements
- AWS Account with permissions for:
  - ECR (Elastic Container Registry)
  - ECS (Elastic Container Service)
  - S3 (Simple Storage Service)
  - CloudWatch (Monitoring)
  - RDS (optional, for persistence)
  - Secrets Manager
  - IAM (creating roles/policies)
  - VPC & Networking
```

### AWS Credentials Setup

```bash
# Configure AWS CLI
aws configure

# You'll be prompted for:
# AWS Access Key ID: [your-key]
# AWS Secret Access Key: [your-secret]
# Default region: us-east-1 (or your preferred region)
# Default output format: json

# Verify setup
aws sts get-caller-identity
# Should show your AWS account details
```

### Required Credentials

```
GROQ_API_KEY: Get from https://console.groq.com
  - Create API key
  - Save securely (will be stored in Secrets Manager)
```

---

## 🐳 Docker Setup

### 1. Create Dockerfile

Create `Dockerfile` in project root:

```dockerfile
# Multi-stage build for optimized size
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies with optimizations
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt


# ════════════════════════════════════════════════════════════════
# Final runtime image
# ════════════════════════════════════════════════════════════════

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies only (minimal)
RUN apt-get update && apt-get install -y \
    libopenblas0 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY flask_app.py .
COPY embedding_service.py .
COPY self_rag_pipeline.py .
COPY templates/ ./templates/
COPY static/ ./static/

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH"
ENV FLASK_APP=flask_app.py
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/health', timeout=5)" || exit 1

# Expose port
EXPOSE 5000

# Run Flask application
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=5000"]
```

### 2. Create .dockerignore

```
venv/
__pycache__/
*.pyc
.git/
.gitignore
.env
.env.example
*.md
docs/
.pytest_cache/
*.egg-info/
.DS_Store
tests/
```

### 3. Create docker-compose.yml (Local Development)

```yaml
version: '3.8'

services:
  self-rag:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "5000:5000"
    environment:
      - GROQ_API_KEY=${GROQ_API_KEY}
      - FLASK_ENV=development
      - AWS_REGION=us-east-1
    volumes:
      - ./templates:/app/templates
      - ./static:/app/static
      - ./embedding_service.py:/app/embedding_service.py
      - ./flask_app.py:/app/flask_app.py
      - ./self_rag_pipeline.py:/app/self_rag_pipeline.py
    networks:
      - self-rag-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

networks:
  self-rag-network:
    driver: bridge
```

### 4. Build Docker Image Locally

```bash
# Navigate to project directory
cd f:\PROJECTS\new_rag\adv_rag

# Set GROQ API Key
$env:GROQ_API_KEY = "gsk_your_key_here"

# Build image
docker build -t self-rag:latest .

# Test locally
docker run -p 5000:5000 -e GROQ_API_KEY=$env:GROQ_API_KEY self-rag:latest

# Access at http://localhost:5000
```

### 5. Test Docker Image

```bash
# Run container
docker run -p 5000:5000 \
  -e GROQ_API_KEY=gsk_your_key_here \
  self-rag:latest

# In another terminal, test endpoints
curl http://localhost:5000/health
# Expected: {"status": "ok"}

curl http://localhost:5000/api/models
# Expected: {"models": ["llama-3.3-70b-versatile", ...]}

# Stop container
docker stop <container_id>
```

---

## 🔧 AWS Infrastructure Setup

### Step 1: Create ECR Repository

```bash
# Set variables
$region = "us-east-1"
$account_id = "$(aws sts get-caller-identity --query Account --output text)"
$repo_name = "self-rag"

# Create ECR repository
aws ecr create-repository `
  --repository-name $repo_name `
  --region $region `
  --image-scanning-configuration scanOnPush=true `
  --image-tag-mutability MUTABLE

# Output
# {
#   "repository": {
#     "repositoryArn": "arn:aws:ecr:us-east-1:123456789012:repository/self-rag",
#     "registryId": "123456789012",
#     "repositoryName": "self-rag",
#     "repositoryUri": "123456789012.dkr.ecr.us-east-1.amazonaws.com/self-rag"
#   }
# }

# Save the repositoryUri for next steps
echo "Repository URI: 123456789012.dkr.ecr.us-east-1.amazonaws.com/self-rag"
```

### Step 2: Push Docker Image to ECR

```bash
# Set variables
$registry_url = "123456789012.dkr.ecr.us-east-1.amazonaws.com"
$repo_name = "self-rag"
$region = "us-east-1"

# Login to ECR
aws ecr get-login-password --region $region | `
  docker login --username AWS --password-stdin $registry_url

# Tag image
docker tag self-rag:latest "$registry_url/$repo_name`:latest"
docker tag self-rag:latest "$registry_url/$repo_name`:v1.0.0"

# Push to ECR
docker push "$registry_url/$repo_name`:latest"
docker push "$registry_url/$repo_name`:v1.0.0"

# Verify
aws ecr describe-images --repository-name $repo_name --region $region
```

### Step 3: Create IAM Role for ECS Task

```bash
# Create trust policy (trust-policy.json)
@'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
'@ | Out-File -Path trust-policy.json -Encoding UTF8

# Create IAM role
aws iam create-role `
  --role-name self-rag-ecs-task-role `
  --assume-role-policy-document file://trust-policy.json

# Create policy for S3, Secrets Manager, and CloudWatch (policy.json)
@'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::self-rag-documents",
        "arn:aws:s3:::self-rag-documents/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:*:secret:self-rag/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:us-east-1:*:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken"
      ],
      "Resource": "*"
    }
  ]
}
'@ | Out-File -Path policy.json -Encoding UTF8

# Attach policy to role
aws iam put-role-policy `
  --role-name self-rag-ecs-task-role `
  --policy-name self-rag-permissions `
  --policy-document file://policy.json

# Create IAM role for task execution
aws iam create-role `
  --role-name self-rag-ecs-task-execution-role `
  --assume-role-policy-document file://trust-policy.json

# Attach managed policy for ECR access
aws iam attach-role-policy `
  --role-name self-rag-ecs-task-execution-role `
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
```

### Step 4: Create S3 Buckets

```bash
# Create bucket for documents & sessions
aws s3api create-bucket `
  --bucket self-rag-documents-prod `
  --region us-east-1 `
  --acl private

# Create bucket for logs
aws s3api create-bucket `
  --bucket self-rag-logs-prod `
  --region us-east-1 `
  --acl private

# Enable versioning for documents (safety)
aws s3api put-bucket-versioning `
  --bucket self-rag-documents-prod `
  --versioning-configuration Status=Enabled

# Block public access
aws s3api put-public-access-block `
  --bucket self-rag-documents-prod `
  --public-access-block-configuration `
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

aws s3api put-public-access-block `
  --bucket self-rag-logs-prod `
  --public-access-block-configuration `
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

### Step 5: Create Secrets in Secrets Manager

```bash
# Create secret for GROQ_API_KEY
aws secretsmanager create-secret `
  --name self-rag/groq-api-key `
  --description "Groq API key for Self-RAG application" `
  --secret-string "gsk_your_production_key_here" `
  --region us-east-1

# Verify secret
aws secretsmanager get-secret-value `
  --secret-id self-rag/groq-api-key `
  --region us-east-1
```

### Step 6: Create VPC & Networking (or Use Default)

```bash
# List available VPCs
aws ec2 describe-vpcs --region us-east-1

# List subnets
aws ec2 describe-subnets --region us-east-1 --filters Name=vpc-id,Values=vpc-xxxxx

# Create security group for ECS tasks
aws ec2 create-security-group `
  --group-name self-rag-ecs-sg `
  --description "Security group for Self-RAG ECS tasks" `
  --vpc-id vpc-xxxxx `
  --region us-east-1

# Get security group ID
$sg_id = aws ec2 describe-security-groups `
  --filters "Name=group-name,Values=self-rag-ecs-sg" `
  --query "SecurityGroups[0].GroupId" `
  --output text

# Allow inbound traffic on port 5000 from ALB
aws ec2 authorize-security-group-ingress `
  --group-id $sg_id `
  --protocol tcp `
  --port 5000 `
  --cidr 0.0.0.0/0 `
  --region us-east-1

# Allow outbound HTTPS (for Groq API)
aws ec2 authorize-security-group-egress `
  --group-id $sg_id `
  --protocol tcp `
  --port 443 `
  --cidr 0.0.0.0/0 `
  --region us-east-1
```

### Step 7: Create Application Load Balancer

```bash
# Get availability zones
$azs = aws ec2 describe-availability-zones `
  --query "AvailabilityZones[*].ZoneName" `
  --output text

# Get subnet IDs
$subnets = aws ec2 describe-subnets `
  --query "Subnets[*].SubnetId" `
  --output text

# Create ALB
aws elbv2 create-load-balancer `
  --name self-rag-alb `
  --subnets $subnets.Split() `
  --security-groups $sg_id `
  --scheme internet-facing `
  --type application `
  --ip-address-type ipv4 `
  --region us-east-1

# Get load balancer ARN (needed next)
$lb_arn = aws elbv2 describe-load-balancers `
  --names self-rag-alb `
  --query "LoadBalancers[0].LoadBalancerArn" `
  --output text

echo "ALB ARN: $lb_arn"
```

### Step 8: Create Target Group

```bash
# Get VPC ID
$vpc_id = aws ec2 describe-vpcs `
  --query "Vpcs[0].VpcId" `
  --output text

# Create target group
aws elbv2 create-target-group `
  --name self-rag-tg `
  --protocol HTTP `
  --port 5000 `
  --vpc-id $vpc_id `
  --health-check-protocol HTTP `
  --health-check-path /health `
  --health-check-interval-seconds 30 `
  --health-check-timeout-seconds 10 `
  --healthy-threshold-count 2 `
  --unhealthy-threshold-count 3 `
  --region us-east-1

# Get target group ARN
$tg_arn = aws elbv2 describe-target-groups `
  --names self-rag-tg `
  --query "TargetGroups[0].TargetGroupArn" `
  --output text

echo "Target Group ARN: $tg_arn"
```

### Step 9: Create ALB Listener

```bash
# Create listener
aws elbv2 create-listener `
  --load-balancer-arn $lb_arn `
  --protocol HTTP `
  --port 80 `
  --default-actions Type=forward,TargetGroupArn=$tg_arn `
  --region us-east-1

# Note: For production, use HTTPS with ACM certificate
# aws elbv2 create-listener `
#   --load-balancer-arn $lb_arn `
#   --protocol HTTPS `
#   --port 443 `
#   --certificates CertificateArn=arn:aws:acm:... `
#   --default-actions Type=forward,TargetGroupArn=$tg_arn
```

### Step 10: Create ECS Cluster

```bash
# Create ECS cluster
aws ecs create-cluster `
  --cluster-name self-rag-cluster `
  --capacity-providers FARGATE FARGATE_SPOT `
  --default-capacity-provider-strategy capacityProvider=FARGATE,weight=100,base=1 `
  --region us-east-1

# Alternatively, using simple cluster
aws ecs create-cluster `
  --cluster-name self-rag-cluster `
  --region us-east-1
```

### Step 11: Create ECS Task Definition

```bash
# Create task definition JSON (ecs-task-definition.json)
@'
{
  "family": "self-rag-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [
    {
      "name": "self-rag",
      "image": "123456789012.dkr.ecr.us-east-1.amazonaws.com/self-rag:latest",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 5000,
          "hostPort": 5000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "FLASK_ENV",
          "value": "production"
        },
        {
          "name": "AWS_REGION",
          "value": "us-east-1"
        },
        {
          "name": "S3_DOCUMENTS_BUCKET",
          "value": "self-rag-documents-prod"
        }
      ],
      "secrets": [
        {
          "name": "GROQ_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:self-rag/groq-api-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/self-rag",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:5000/health || exit 1"],
        "interval": 30,
        "timeout": 10,
        "retries": 3,
        "startPeriod": 40
      }
    }
  ],
  "taskRoleArn": "arn:aws:iam::123456789012:role/self-rag-ecs-task-role",
  "executionRoleArn": "arn:aws:iam::123456789012:role/self-rag-ecs-task-execution-role"
}
'@ | Out-File -Path ecs-task-definition.json -Encoding UTF8

# Register task definition
aws ecs register-task-definition `
  --cli-input-json file://ecs-task-definition.json `
  --region us-east-1
```

### Step 12: Create CloudWatch Log Group

```bash
# Create log group
aws logs create-log-group `
  --log-group-name /ecs/self-rag `
  --region us-east-1

# Set retention policy (30 days)
aws logs put-retention-policy `
  --log-group-name /ecs/self-rag `
  --retention-in-days 30 `
  --region us-east-1
```

---

## 🚀 Deployment Steps

### Complete Deployment Workflow

```bash
# 1. Push updated Docker image
cd f:\PROJECTS\new_rag\adv_rag
docker build -t self-rag:latest .
docker tag self-rag:latest 123456789012.dkr.ecr.us-east-1.amazonaws.com/self-rag:latest
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/self-rag:latest

# 2. Create ECS Service
aws ecs create-service `
  --cluster self-rag-cluster `
  --service-name self-rag-service `
  --task-definition self-rag-task:1 `
  --desired-count 2 `
  --load-balancers targetGroupArn=arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/self-rag-tg/xxxxx,containerName=self-rag,containerPort=5000 `
  --launch-type FARGATE `
  --network-configuration "awsvpcConfiguration={subnets=[subnet-12345,subnet-67890],securityGroups=[sg-12345],assignPublicIp=ENABLED}" `
  --region us-east-1

# 3. Verify deployment
aws ecs describe-services `
  --cluster self-rag-cluster `
  --services self-rag-service `
  --region us-east-1

# 4. Get load balancer DNS
aws elbv2 describe-load-balancers `
  --names self-rag-alb `
  --query "LoadBalancers[0].DNSName" `
  --output text
  
# 5. Test application
curl http://self-rag-alb-1234567890.us-east-1.elb.amazonaws.com/health
```

### Update Deployment (New Image)

```bash
# 1. Build and push new image
docker build -t self-rag:v2.0.0 .
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com
docker tag self-rag:v2.0.0 123456789012.dkr.ecr.us-east-1.amazonaws.com/self-rag:v2.0.0
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/self-rag:v2.0.0

# 2. Update task definition with new image
# (Repeat step 11, update image URI in JSON)

# 3. Update service to use new task definition
aws ecs update-service `
  --cluster self-rag-cluster `
  --service self-rag-service `
  --task-definition self-rag-task:2 `
  --force-new-deployment `
  --region us-east-1

# 4. Monitor deployment
aws ecs describe-services `
  --cluster self-rag-cluster `
  --services self-rag-service `
  --region us-east-1 `
  --query "services[0].{pendingCount:pendingCount,runningCount:runningCount,desiredCount:desiredCount}"
```

---

## ⚙️ Configuration & Secrets

### Environment Variables (ECS Task Definition)

```yaml
FLASK_ENV: production                      # Flask environment
AWS_REGION: us-east-1                      # AWS region
S3_DOCUMENTS_BUCKET: self-rag-documents-prod  # S3 bucket for PDFs
S3_SESSION_BUCKET: self-rag-sessions-prod     # Session data
FAISS_PERSISTENCE: true                    # Enable FAISS persistence
LOG_LEVEL: INFO                            # Logging level
MAX_UPLOAD_SIZE_MB: 50                     # Max file upload size
```

### Secrets in AWS Secrets Manager

```bash
# Store sensitive data
aws secretsmanager create-secret \
  --name self-rag/groq-api-key \
  --secret-string "gsk_your_key"

aws secretsmanager create-secret \
  --name self-rag/db-password \
  --secret-string "your-secure-password"

# Reference in task definition
# "valueFrom": "arn:aws:secretsmanager:region:account:secret:self-rag/groq-api-key"
```

### .env File for Local Development

```bash
# Development only
GROQ_API_KEY=gsk_dev_key_here
FLASK_ENV=development
AWS_REGION=us-east-1
S3_DOCUMENTS_BUCKET=self-rag-documents-dev
```

---

## 📈 Scaling & Performance

### Auto-Scaling Configuration

```bash
# Create Auto Scaling target
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/self-rag-cluster/self-rag-service \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 2 \
  --max-capacity 10 \
  --region us-east-1

# Create scaling policy (CPU-based)
aws application-autoscaling put-scaling-policy \
  --policy-name self-rag-cpu-scaling \
  --service-namespace ecs \
  --resource-id service/self-rag-cluster/self-rag-service \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration \
    TargetValue=70.0,PredefinedMetricSpecification={PredefinedMetricType=ECSServiceAverageCPUUtilization},ScaleOutCooldown=60,ScaleInCooldown=300 \
  --region us-east-1

# Create scaling policy (Memory-based)
aws application-autoscaling put-scaling-policy \
  --policy-name self-rag-memory-scaling \
  --service-namespace ecs \
  --resource-id service/self-rag-cluster/self-rag-service \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration \
    TargetValue=80.0,PredefinedMetricSpecification={PredefinedMetricType=ECSServiceAverageMemoryUtilization},ScaleOutCooldown=60,ScaleInCooldown=300 \
  --region us-east-1
```

### Resource Recommendations

#### Small Deployment (Dev/Test)
- CPU: 256
- Memory: 512 MB
- Desired tasks: 1
- Max tasks: 3

#### Medium Deployment (Production)
- CPU: 1024 (1 vCPU)
- Memory: 2048 MB (2 GB)
- Desired tasks: 2
- Max tasks: 6

#### Large Deployment (High Traffic)
- CPU: 2048 (2 vCPU)
- Memory: 4096 MB (4 GB)
- Desired tasks: 4
- Max tasks: 12

---

## 📊 Monitoring & Logging

### CloudWatch Dashboards

```bash
# Create custom dashboard
aws cloudwatch put-dashboard \
  --dashboard-name self-rag-dashboard \
  --dashboard-body file://dashboard-config.json \
  --region us-east-1
```

Create `dashboard-config.json`:

```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/ECS", "CPUUtilization", {"stat": "Average"}],
          [".", "MemoryUtilization", {"stat": "Average"}],
          ["AWS/ApplicationELB", "TargetResponseTime", {"stat": "Average"}],
          [".", "RequestCount", {"stat": "Sum"}],
          [".", "HTTPCode_Target_5XX_Count", {"stat": "Sum"}]
        ],
        "period": 60,
        "stat": "Average",
        "region": "us-east-1"
      }
    }
  ]
}
```

### CloudWatch Alarms

```bash
# CPU utilization alarm
aws cloudwatch put-metric-alarm \
  --alarm-name self-rag-high-cpu \
  --alarm-description "Alert when CPU > 85%" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 85 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --region us-east-1

# Memory utilization alarm
aws cloudwatch put-metric-alarm \
  --alarm-name self-rag-high-memory \
  --alarm-description "Alert when Memory > 90%" \
  --metric-name MemoryUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 90 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --region us-east-1

# Task failure alarm
aws cloudwatch put-metric-alarm \
  --alarm-name self-rag-task-failures \
  --alarm-description "Alert on task failures" \
  --metric-name FailedTaskCount \
  --namespace AWS/ECS \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --evaluation-periods 1 \
  --region us-east-1
```

### Viewing Logs

```bash
# Stream live logs
aws logs tail /ecs/self-rag --follow

# Query logs
aws logs filter-log-events \
  --log-group-name /ecs/self-rag \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --region us-east-1
```

---

## 🔄 CI/CD Pipeline

### GitHub Actions Workflow

Create `.github/workflows/deploy-to-aws.yml`:

```yaml
name: Deploy to AWS ECS

on:
  push:
    branches:
      - main
      - production
  release:
    types: [created]

env:
  AWS_REGION: us-east-1
  ECR_REPOSITORY: self-rag
  ECS_SERVICE: self-rag-service
  ECS_CLUSTER: self-rag-cluster
  ECS_TASK_DEFINITION: self-rag-task

jobs:
  deploy:
    name: Deploy to ECS
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v1

      - name: Build, tag, and push image to Amazon ECR
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          echo "image=$ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG" >> $GITHUB_OUTPUT

      - name: Download task definition
        run: |
          aws ecs describe-task-definition --task-definition ${{ env.ECS_TASK_DEFINITION }} \
          --query taskDefinition > task-definition.json

      - name: Update ECS task definition
        id: task-def
        uses: aws-actions/amazon-ecs-render-task-definition@v1
        with:
          task-definition: task-definition.json
          container-name: self-rag
          image: ${{ steps.login-ecr.outputs.registry }}/${{ env.ECR_REPOSITORY }}:${{ github.sha }}

      - name: Deploy to Amazon ECS service
        uses: aws-actions/amazon-ecs-deploy-task-definition@v1
        with:
          task-definition: ${{ steps.task-def.outputs.task-definition }}
          service: ${{ env.ECS_SERVICE }}
          cluster: ${{ env.ECS_CLUSTER }}
          wait-for-service-stability: true

      - name: Notify deployment
        run: |
          echo "✅ Deployment successful to ECS"
          echo "Service: ${{ env.ECS_SERVICE }}"
          echo "Cluster: ${{ env.ECS_CLUSTER }}"
```

### Setup GitHub Secrets

```bash
# Add these to GitHub repository settings
GITHUB_REPOSITORY_SETTINGS → Secrets and variables → Actions

AWS_ACCESS_KEY_ID: "your-access-key"
AWS_SECRET_ACCESS_KEY: "your-secret-key"
```

---

## 🐛 Troubleshooting

### Task Won't Start

```bash
# Check task logs
aws ecs describe-tasks \
  --cluster self-rag-cluster \
  --tasks <task-arn> \
  --region us-east-1

# View CloudWatch logs
aws logs get-log-events \
  --log-group-name /ecs/self-rag \
  --log-stream-name ecs/self-rag/<task-id>
```

### Application Errors

```bash
# Check service events
aws ecs describe-services \
  --cluster self-rag-cluster \
  --services self-rag-service \
  --region us-east-1 \
  --query "services[0].events"

# Connect to running container (ECS Exec)
aws ecs execute-command \
  --cluster self-rag-cluster \
  --task <task-id> \
  --container self-rag \
  --interactive \
  --command "/bin/bash"
```

### Groq API Issues

```bash
# Verify secret is accessible
aws secretsmanager get-secret-value \
  --secret-id self-rag/groq-api-key

# Check task role permissions
aws iam get-role --role-name self-rag-ecs-task-role
```

### High CPU/Memory Usage

```bash
# Check CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=self-rag-service Name=ClusterName,Value=self-rag-cluster \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum

# Solutions:
# 1. Increase task memory (update task definition)
# 2. Scale horizontally (more tasks)
# 3. Optimize embeddings batch size in embedding_service.py
```

---

## 💰 Cost Optimization

### Estimated Monthly Costs (US-East-1)

| Service | Configuration | Cost |
|---------|----------------|------|
| ECS Fargate | 2 × 1024 CPU, 2048 MB × 730 hours | ~$115 |
| ALB | 1 ALB, ~100K requests/month | ~$16 |
| S3 | 100 GB storage, 50K operations | ~$2.50 |
| CloudWatch Logs | ~1-10 GB/month | ~$5 |
| NAT Gateway | 1 gateway, ~10 GB data | ~$32 |
| **Total (Small Prod)** | | **~$170/month** |

### Cost Reduction Strategies

```bash
# 1. Use Fargate Spot Instances
aws ecs create-service \
  --cluster self-rag-cluster \
  --service-name self-rag-service \
  --task-definition self-rag-task \
  --desired-count 2 \
  --launch-type FARGATE_SPOT  # Save 70% on Fargate costs!

# 2. Set up Reserved Capacity (if using EC2)
# Save 40% with 1-year commitment

# 3. Implement log retention
aws logs put-retention-policy \
  --log-group-name /ecs/self-rag \
  --retention-in-days 14  # Reduce storage costs

# 4. Use S3 Intelligent-Tiering
aws s3api put-bucket-intelligent-tiering-configuration \
  --bucket self-rag-documents-prod \
  --id self-rag-tiering \
  --intelligent-tiering-configuration '{"Id":"tiering","Filter":{"Prefix":"documents/"},"Status":"Enabled","Tierings":[{"Days":30,"Tier":"ARCHIVE_ACCESS"}]}'
```

### Cost Monitoring

```bash
# Set budget alarm
aws budgets create-budget \
  --account-id $(aws sts get-caller-identity --query Account --output text) \
  --budget file://budget.json

# Track costs
aws ce get-cost-and-usage \
  --time-period Start=2024-04-01,End=2024-04-30 \
  --granularity MONTHLY \
  --metrics "BlendedCost" \
  --group-by Type=DIMENSION,Key=SERVICE
```

---

## ✅ Production Checklist

- [ ] Docker image built and tested locally
- [ ] ECR repository created and image pushed
- [ ] IAM roles and policies created
- [ ] S3 buckets created with encryption
- [ ] Secrets stored in Secrets Manager
- [ ] VPC and security groups configured
- [ ] ALB and target group created
- [ ] ECS cluster created
- [ ] Task definition registered
- [ ] CloudWatch logs configured
- [ ] Health checks verified
- [ ] Auto-scaling configured
- [ ] Monitoring alarms set up
- [ ] Load balancer DNS verified
- [ ] SSL/TLS certificate configured (optional)
- [ ] CI/CD pipeline deployed
- [ ] Backup strategy defined
- [ ] Disaster recovery plan created

---

## 🚀 Summary

Your Self-RAG application is now fully containerized and ready for AWS deployment:

1. **Docker**: Multi-stage build optimizes image size
2. **AWS Infrastructure**: ECS Fargate + ALB + S3 + Secrets Manager
3. **Auto-Scaling**: CPU and memory-based scaling
4. **Monitoring**: CloudWatch logs, metrics, and alarms
5. **CI/CD**: GitHub Actions automated deployment
6. **Cost Optimization**: Fargate Spot, log retention, S3 tiering

---

## 📚 Additional Resources

- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [Docker Documentation](https://docs.docker.com/)
- [Groq API Documentation](https://console.groq.com/docs)
- [AWS Secrets Manager](https://docs.aws.amazon.com/secretsmanager/)
- [AWS CloudWatch](https://docs.aws.amazon.com/cloudwatch/)

---

**Last Updated**: April 17, 2026
**Status**: Production Ready ✅
