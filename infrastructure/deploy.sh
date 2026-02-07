#!/bin/bash
# CommerceSignal AWS FREE TIER Deployment
# Cost: $0/month (within free tier limits)

set -e

STACK_NAME="commerce-signal-free"
REGION=${AWS_REGION:-us-east-1}

echo "🆓 Deploying CommerceSignal on AWS FREE TIER"
echo ""

# Check prerequisites
command -v aws >/dev/null 2>&1 || { echo "❌ AWS CLI not found"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "❌ Docker not found"; exit 1; }

# Get AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

# Check for key pair
if [ -z "${KEY_PAIR_NAME}" ]; then
  echo "⚠️  KEY_PAIR_NAME not set."
  echo "   Create one: aws ec2 create-key-pair --key-name commerce-signal-key --query 'KeyMaterial' --output text > commerce-signal-key.pem"
  echo "   Then: export KEY_PAIR_NAME=commerce-signal-key"
  exit 1
fi

if [ -z "${DB_PASSWORD}" ]; then
  echo "⚠️  DB_PASSWORD not set. Generating..."
  DB_PASSWORD=$(openssl rand -base64 12 | tr -dc 'a-zA-Z0-9')
  echo "   Password: ${DB_PASSWORD}"
  echo "   Save this! You'll need it."
fi

echo ""
echo "📦 Step 1: Create ECR repositories..."
aws ecr create-repository --repository-name commerce-signal/python-api --region ${REGION} 2>/dev/null || true
aws ecr create-repository --repository-name commerce-signal/ctx-wrapper --region ${REGION} 2>/dev/null || true

echo "🔐 Step 2: Login to ECR..."
aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}

echo "🏗️  Step 3: Build images..."
docker build -f Dockerfile.python -t ${ECR_REGISTRY}/commerce-signal/python-api:latest .
docker build -f ctx-wrapper/Dockerfile -t ${ECR_REGISTRY}/commerce-signal/ctx-wrapper:latest ctx-wrapper/

echo "📤 Step 4: Push images..."
docker push ${ECR_REGISTRY}/commerce-signal/python-api:latest
docker push ${ECR_REGISTRY}/commerce-signal/ctx-wrapper:latest

echo "☁️  Step 5: Deploy CloudFormation stack..."
aws cloudformation deploy \
  --template-file infrastructure/cloudformation.yml \
  --stack-name ${STACK_NAME} \
  --parameter-overrides \
    KeyPairName=${KEY_PAIR_NAME} \
    DBPassword=${DB_PASSWORD} \
  --capabilities CAPABILITY_IAM \
  --region ${REGION}

echo "⏳ Waiting for stack to complete..."
aws cloudformation wait stack-create-complete --stack-name ${STACK_NAME} --region ${REGION} 2>/dev/null || true

echo ""
echo "📋 Getting outputs..."
PUBLIC_IP=$(aws cloudformation describe-stacks \
  --stack-name ${STACK_NAME} \
  --query 'Stacks[0].Outputs[?OutputKey==`PublicIP`].OutputValue' \
  --output text \
  --region ${REGION})

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✅ DEPLOYMENT COMPLETE!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "  🌐 MCP Endpoint:   http://${PUBLIC_IP}:3000/mcp"
echo "  ❤️  Health Check:   http://${PUBLIC_IP}:3000/health"
echo "  🔌 SSH Access:     ssh -i ${KEY_PAIR_NAME}.pem ubuntu@${PUBLIC_IP}"
echo ""
echo "  💰 COST: \$0/month (Free Tier)"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "📝 Next Steps:"
echo "   1. Wait 2-3 mins for EC2 to fully initialize"
echo "   2. Test: curl http://${PUBLIC_IP}:3000/health"
echo "   3. Register on CTX: https://ctxprotocol.com/contribute"
echo "   4. Paste endpoint: http://${PUBLIC_IP}:3000/mcp"
echo ""
