---
name: localstack-ops
description: "Guidelines, commands, and patterns for LocalStack cloud emulation, dummy AWS credentials, endpoint configuration, and infrastructure resource management."
metadata:
    namespace: cloud
---
# LocalStack Operations & Cloud Emulation

This skill standardizes LocalStack interactions to maximize efficiency, eliminate configuration drift, and guarantee idempotent cloud resource lifecycles.

## 1. Environment & Endpoint Configuration

Always direct cloud infrastructure tooling and SDK clients to the LocalStack mock endpoints with standard test credentials.

### Host Machine vs. Container Networking
- **Host / Local Machine**: `http://localhost:4566` (or `http://127.0.0.1:4566`)
- **Docker Containers / Network**: `http://localstack:4566`

### Standard Dummy Credentials
Export these in your environment or subshell when invoking AWS CLI, CDK, Terraform, or SDKs:
```bash
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
export AWS_ENDPOINT_URL=http://localhost:4566
```

---

## 2. Health & Readiness Verification

Before running deployment scripts or integration tests, probe the LocalStack health endpoint:

```bash
# Check service availability and health state
curl -s http://localhost:4566/_localstack/health | jq .
```

---

## 3. Tooling & CLI Conventions

### `awslocal` CLI Wrapper
Prefer `awslocal` if installed, or configure standard `aws` with `--endpoint-url`:
```bash
# S3 Bucket Creation
awslocal s3 mb s3://crm-event-store

# SQS Queue Provisioning
awslocal sqs create-queue --queue-name crm-sync-queue

# DynamoDB Table Provisioning
awslocal dynamodb create-table \
    --table-name CrmAuditLog \
    --attribute-definitions AttributeName=Id,AttributeType=S \
    --key-schema AttributeName=Id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST
```

---

## 4. Idempotency & Clean Lifecycle Patterns

All resource initialization scripts must be idempotent (safe to run multiple times without failure).

### Idempotent Bash Pattern Example
```bash
#!/usr/bin/env bash
set -euo pipefail

BUCKET_NAME="crm-event-store"
QUEUE_NAME="crm-sync-queue"
ENDPOINT="http://localhost:4566"

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

# Create S3 bucket if it doesn't exist
if ! aws --endpoint-url="$ENDPOINT" s3api head-bucket --bucket "$BUCKET_NAME" 2>/dev/null; then
    echo "Creating S3 bucket: $BUCKET_NAME"
    aws --endpoint-url="$ENDPOINT" s3api create-bucket --bucket "$BUCKET_NAME"
fi

# Create SQS queue idempotently (create-queue returns existing URL if attributes match)
aws --endpoint-url="$ENDPOINT" sqs create-queue --queue-name "$QUEUE_NAME" > /dev/null
echo "LocalStack resources initialized successfully."
```
