# AWS Deployment Checklist - Self-RAG (First Deployment)

**Last Updated**: April 21, 2026  
**Status**: ✅ READY FOR SIMPLE DEPLOYMENT  
**Scope**: Stateless app - NO user data storage, documents uploaded per session only

---

## ⚡ QUICK START (5 Steps)

### ✅ Step 1: Test Locally (5 min)
```powershell
cd f:\PROJECTS\new_rag\adv_rag

# Build Docker image
docker build -t self-rag:v1.0 .

# Run with Groq API key (only required env var)
docker run -p 5000:5000 `
  -e GROQ_API_KEY="your_groq_api_key_here" `
  -e FLASK_ENV=production `
  self-rag:v1.0

# In another terminal, test it works
curl http://localhost:5000/health
```

**Expected result**: Should see JSON response with `"status": "ready"`

**What's happening**: 
- `sentence-transformers` downloads `all-MiniLM-L6-v2` from HuggingFace (public model, no token needed)
- Embeddings are created locally in the container
- Groq API is used only for LLM responses

---

### ✅ Step 2: Store Groq API Key in AWS (2 min)
```powershell
# Use AWS CLI to store your Groq API key securely
aws secretsmanager create-secret `
  --name self-rag/groq-api-key `
  --secret-string "your_groq_api_key_here" `
  --region us-east-1
```

**Note**: Get your free Groq API key from https://console.groq.com

---

### ✅ Step 3: Create S3 Bucket for Documents (1 min)
```powershell
# Create an S3 bucket for uploaded PDFs (temp storage only)
aws s3 mb s3://self-rag-documents-$(date +%s) --region us-east-1

# Note: Documents are DELETED after each session - not permanently stored
```

---

### ✅ Step 4: Create ECS Task (5 min)
Create a new ECS Fargate task using the [ecs-task-definition.json](aws/ecs-task-definition.json):

**Required env variables in task definition**:
```json
{
  "name": "GROQ_API_KEY",
  "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:self-rag/groq-api-key:secretString::"
},
{
  "name": "FLASK_ENV",
  "value": "production"
},
{
  "name": "FLASK_HOST",
  "value": "0.0.0.0"
},
{
  "name": "FLASK_PORT",
  "value": "5000"
}
```

---

### ✅ Step 5: Deploy & Test (5 min)
```powershell
# Update task definition in AWS
aws ecs register-task-definition --cli-input-json file://aws/ecs-task-definition.json

# Start the ECS service
aws ecs create-service `
  --cluster self-rag-cluster `
  --service-name self-rag-service `
  --task-definition self-rag-task `
  --desired-count 1 `
  --launch-type FARGATE `
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}" `
  --region us-east-1

# Check logs
aws logs tail /ecs/self-rag --follow
```

---

## 📊 What Gets Stored (Very Minimal)

| Data | Stored? | Where? | Duration | Notes |
|------|---------|--------|----------|-------|
| Uploaded PDFs | ✅ Yes | S3 (temp) | Until session ends | Optional - app works without it |
| Embeddings (FAISS) | ✅ Yes | Memory only | Until app restarts | Created from PDFs using HuggingFace models |
| Chat history | ❌ No | - | - | - |
| User accounts | ❌ No | - | - | - |
| Sessions | ❌ No | - | - | - |

**Embedding Details**:
- Model: `all-MiniLM-L6-v2` (HuggingFace, public)
- Library: `sentence-transformers` 
- **Token required**: ❌ NO (public model, auto-downloaded)
- Runs locally in the container

**Result**: Each new session is completely fresh. App is stateless.

---

## 💰 Estimated Monthly Cost

| Resource | Cost |
|----------|------|
| ECS Fargate (1 task, 1 vCPU, 2GB) | ~$35 |
| S3 storage (minimal, auto-deleted) | ~$1 |
| CloudWatch logs | ~$2 |
| **Total** | **~$38/month** |

---

## 🔍 Verify After Deployment

- [ ] ECS task is running in AWS Console
- [ ] Health check: `curl https://your-load-balancer/health`
- [ ] Can upload a PDF
- [ ] Can ask questions about the PDF
- [ ] Restart app → all data cleared (expected behavior)

---

## ⚠️ Important Notes

1. **NO persistent data** = App works fresh each time. This is intentional.
2. **GROQ_API_KEY is required** - without it, the app won't start.
3. **HuggingFace IS used** for embeddings (no token needed - public model)
4. **S3 is optional** - if you skip it, PDF uploads won't work but app still runs.

---

## 🐛 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| Task won't start | Check if `GROQ_API_KEY` is set in AWS Secrets Manager |
| "API key invalid" error | Verify your Groq key from https://console.groq.com |
| PDF upload fails | Create an S3 bucket and add `S3_DOCUMENTS_BUCKET` env var |
| Slow responses | Normal for first query. LLM initialization takes time. |

---

## 🚀 Next: Do This First Time Only

1. **Get Groq API key**: https://console.groq.com (free tier available)
2. **Test locally**: Follow Step 1 above
3. **Run deploy.sh**: 
```powershell
./aws/deploy.sh setup production
./aws/deploy.sh deploy production
```

That's it! Your app is live.
