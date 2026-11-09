#!/usr/bin/env bash
# Production deployment script for Google Cloud Run
set -euo pipefail

PROJECT_ID="${1:-$(gcloud config get-value project)}"
REGION="${2:-us-central1}"
IMAGE_NAME="gcr.io/${PROJECT_ID}/aerospace-ops-stack:latest"

echo "🚀 Building and pushing container image to Google Container Registry..."
gcloud builds submit --tag "${IMAGE_NAME}" .

echo "🌐 Deploying to Google Cloud Run (Region: ${REGION})..."
gcloud run services replace deploy/cloud_run.yaml --region="${REGION}"

echo "🔒 Setting IAM policy for public access..."
gcloud run services add-iam-policy-binding aerospace-ops-gateway \
    --region="${REGION}" \
    --member="allUsers" \
    --role="roles/run.invoker"

echo "✅ Deployment complete! Service URL:"
gcloud run services describe aerospace-ops-gateway --region="${REGION}" --format="value(status.url)"

