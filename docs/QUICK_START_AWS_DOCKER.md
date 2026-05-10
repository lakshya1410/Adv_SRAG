# Self-RAG AWS & Docker Deployment - Quick Start Guide

## Prerequisites

✅ AWS Account with appropriate permissions
✅ AWS CLI v2 configured
✅ Docker Desktop installed
✅ Git configured
✅ GROQ API key (from https://console.groq.com)

## Quick Testing Locally

### 1. Test Docker Build

```bash
cd f:\PROJECTS\new_rag\adv_rag

# Build and run
docker-compose up --build

# Visit: http://localhost:5000
```

### 2. Verify Endpoints

```bash
# Health check
curl http://localhost:5000/health

# Models
curl http://localhost:5000/api/models

# Status
curl http://localhost:5000/api/status
```

---

## Complete AWS Deployment (15-30 minutes)

### Step 1: Configure AWS Credentials

```powershell
# Windows PowerShell
aws configure
# Enter your access key, secret key, region (us-east-1), format (json)

# Verify
aws sts get-caller-identity
```

### Step 2: Set Required Variables

```powershell
$env:AWS_REGION = "us-east-1"
$env:GROQ_API_KEY = "gsk_your_key_here"
$env:AWS_ACCOUNT_ID = aws sts get-caller-identity --query Account --output text
```

### Step 3: Run Deployment Script

```bash
# Make script executable
chmod +x aws/deploy.sh

# Setup infrastructure (one-time)
./aws/deploy.sh setup production

# Build and deploy application
./aws/deploy.sh deploy production
```

Or use these individual commands:

```bash
# Manual Step 1: Create ECR repository
aws ecr create-repository \
  --repository-name self-rag \
  --region us-east-1 \
  --image-scanning-configuration scanOnPush=true

# Manual Step 2: Build and push Docker image
$ECR_URL = "$(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com"
docker build -t self-rag:latest .
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_URL
docker tag self-rag:latest "$ECR_URL/self-rag:latest"
docker push "$ECR_URL/self-rag:latest"

# Manual Step 3: Create S3 buckets
aws s3api create-bucket --bucket self-rag-documents-prod --region us-east-1
aws s3api create-bucket --bucket self-rag-sessions-prod --region us-east-1

# Manual Step 4: Store API key in Secrets Manager
aws secretsmanager create-secret \
  --name self-rag/groq-api-key \
  --secret-string "gsk_your_key"

# Manual Step 5: Create CloudWatch log group
aws logs create-log-group --log-group-name /ecs/self-rag --region us-east-1
aws logs put-retention-policy --log-group-name /ecs/self-rag --retention-in-days 30

# Manual Step 6: Create ECS cluster
aws ecs create-cluster --cluster-name self-rag-cluster --region us-east-1

# Manual Step 7: Register task definition
aws ecs register-task-definition \
  --cli-input-json file://aws/ecs-task-definition.json \
  --region us-east-1

# Manual Step 8: Create service
aws ecs create-service \
  --cluster self-rag-cluster \
  --service-name self-rag-service \
  --task-definition self-rag-task \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}" \
  --region us-east-1
```

### Step 4: Monitor Deployment

```bash
# Check service status
aws ecs describe-services \
  --cluster self-rag-cluster \
  --services self-rag-service \
  --region us-east-1

# View logs
aws logs tail /ecs/self-rag --follow

# or use script
./aws/deploy.sh logs production
```

### Step 5: Get Application URL

```bash
# After ALB is created (1-2 minutes)
aws elbv2 describe-load-balancers \
  --names self-rag-alb \
  --region us-east-1 \
  --query "LoadBalancers[0].DNSName"

# Should output something like:
# self-rag-alb-123456789.us-east-1.elb.amazonaws.com
```

---

## Key Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage Docker build |
| `docker-compose.yml` | Local development setup |
| `.dockerignore` | Files excluded from Docker image |
| `aws/deploy.sh` | Deployment automation script |
| `aws/ecs-task-definition.json` | ECS task configuration |
| `aws/iam-policy.json` | IAM permissions |
| `.github/workflows/deploy-to-aws.yml` | CI/CD pipeline |
| `docs/AWS_DOCKER_DEPLOYMENT.md` | Full documentation |

---

## Common Tasks

### Update Application Code

```bash
# 1. Make changes locally
# 2. Test with Docker Compose
docker-compose up --build

# 3. Build new image
docker build -t self-rag:latest .

# 4. Push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_URL
docker tag self-rag:latest "$ECR_URL/self-rag:latest"
docker push "$ECR_URL/self-rag:latest"

# 5. Force new deployment
aws ecs update-service \
  --cluster self-rag-cluster \
  --service self-rag-service \
  --force-new-deployment \
  --region us-east-1
```

### View Logs

```bash
# Stream logs
./aws/deploy.sh logs production

# Or use AWS CLI
aws logs tail /ecs/self-rag --follow --since 1h

# Search for errors
aws logs filter-log-events \
  --log-group-name /ecs/self-rag \
  --filter-pattern "ERROR"
```

### Scale Service

```bash
# Increase to 4 tasks
aws ecs update-service \
  --cluster self-rag-cluster \
  --service self-rag-service \
  --desired-count 4 \
  --region us-east-1

# Check status
./aws/deploy.sh status production
```

### Rollback Deployment

```bash
# Revert to previous task definition
aws ecs update-service \
  --cluster self-rag-cluster \
  --service self-rag-service \
  --task-definition self-rag-task:PREVIOUS_REVISION \
  --region us-east-1
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
aws logs tail /ecs/self-rag --follow

# Debug task
aws ecs describe-tasks \
  --cluster self-rag-cluster \
  --tasks <task-arn> \
  --region us-east-1 \
  --query 'tasks[0].[lastStatus,stopCode,stoppedReason]'
```

### Health Check Failing

```bash
# Verify endpoint
curl http://localhost:5000/health

# Check security group allows port 5000
aws ec2 describe-security-groups \
  --group-ids sg-xxx \
  --query 'SecurityGroups[0].IpPermissions'
```

### API Key Not Working

```bash
# Verify secret exists
aws secretsmanager get-secret-value \
  --secret-id self-rag/groq-api-key

# Verify task role has permission
aws iam get-role-policy \
  --role-name self-rag-ecs-task-role \
  --policy-name self-rag-permissions
```

---

## Cost Estimate

| Service | Monthly Cost |
|---------|--------------|
| ECS Fargate (2×1vCPU, 2GB) | ~$115 |
| ALB | ~$16 |
| S3 (100GB) | ~$2.50 |
| CloudWatch Logs | ~$5 |
| **Total** | **~$138** |

Use Fargate Spot to save 70% (recommended for non-critical deployments).

---

## Next Steps

1. ✅ Test locally with Docker Compose
2. ✅ Deploy to AWS
3. ✅ Configure custom domain (optional)
4. ✅ Setup CI/CD with GitHub Actions
5. ✅ Configure auto-scaling
6. ✅ Setup monitoring and alerts

---

For detailed documentation, see: **docs/AWS_DOCKER_DEPLOYMENT.md**
