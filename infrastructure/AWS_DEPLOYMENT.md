# AWS Free Tier Deployment Guide

## Cost: $0/month 🎉

Uses only AWS Free Tier resources:
- **EC2 t2.micro** - 750 hrs/month free (12 months)
- **RDS db.t3.micro** - 750 hrs/month free (12 months)
- **30GB EBS** - Free
- **Elastic IP** - Free when attached
- **ECR** - 500MB free storage

---

## Prerequisites

1. AWS account (new accounts get 12 months free tier)
2. AWS CLI configured
3. Docker installed

---

## Deploy in 3 Steps

### Step 1: Create SSH Key Pair
```bash
aws ec2 create-key-pair \
  --key-name commerce-signal-key \
  --query 'KeyMaterial' \
  --output text > commerce-signal-key.pem

chmod 400 commerce-signal-key.pem
```

### Step 2: Set Environment Variables
```bash
export KEY_PAIR_NAME=commerce-signal-key
export DB_PASSWORD=YourSecurePassword123
export AWS_REGION=us-east-1
```

### Step 3: Deploy!
```bash
chmod +x infrastructure/deploy.sh
./infrastructure/deploy.sh
```

---

## What Happens

1. Creates ECR repositories
2. Builds & pushes Docker images
3. Creates VPC, subnets, security groups
4. Launches EC2 t2.micro with Docker
5. Creates RDS PostgreSQL (free tier)
6. Redis runs in Docker on EC2
7. Outputs your endpoint IP

---

## After Deployment

### Test Your Endpoint
```bash
# Wait 2-3 minutes, then:
curl http://<YOUR-IP>:3000/health
```

### SSH Into EC2
```bash
ssh -i commerce-signal-key.pem ubuntu@<YOUR-IP>

# View logs:
docker-compose logs -f
```

### Register on CTX Protocol
1. Go to https://ctxprotocol.com/contribute
2. Paste: `http://<YOUR-IP>:3000/mcp`
3. Set prices → Stake → Go live!

---

## Free Tier Limits

| Resource | Free Limit | Our Usage |
|----------|------------|-----------|
| EC2 | 750 hrs/mo | ~720 hrs ✅ |
| RDS | 750 hrs/mo | ~720 hrs ✅ |
| EBS | 30 GB | 30 GB ✅ |
| Data Transfer | 100 GB | Variable |

> ⚠️ Free tier expires after 12 months. Set billing alerts!

---

## Troubleshooting

### Check EC2 Status
```bash
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=commerce-signal-free" \
  --query 'Reservations[].Instances[].State.Name'
```

### View Logs
```bash
ssh -i commerce-signal-key.pem ubuntu@<IP>
docker-compose logs
```

### Redeploy Containers
```bash
ssh -i commerce-signal-key.pem ec2-user@<IP>
docker-compose pull
docker-compose up -d
```
