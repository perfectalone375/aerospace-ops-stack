# Production deployment script for Google Cloud Run (PowerShell)
param(
    [string]$ProjectId = $(gcloud config get-value project 2>$null),
    [string]$Region = "us-central1"
)

if (-not $ProjectId) {
    Write-Error "Please specify a Google Cloud ProjectId: .\deploy_gcp.ps1 -ProjectId your-gcp-project-id"
    exit 1
}

$ImageName = "gcr.io/$ProjectId/aerospace-ops-stack:latest"

Write-Host "🚀 Building and pushing container image to Google Container Registry..." -ForegroundColor Cyan
gcloud builds submit --tag $ImageName .

Write-Host "🌐 Deploying to Google Cloud Run (Region: $Region)..." -ForegroundColor Cyan
gcloud run services replace deploy/cloud_run.yaml --region=$Region

Write-Host "🔒 Setting IAM policy for public access..." -ForegroundColor Cyan
gcloud run services add-iam-policy-binding aerospace-ops-gateway `
    --region=$Region `
    --member="allUsers" `
    --role="roles/run.invoker"

Write-Host "✅ Deployment complete! Service URL:" -ForegroundColor Green
gcloud run services describe aerospace-ops-gateway --region=$Region --format="value(status.url)"

