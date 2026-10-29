# =============================================================================
# Automated GCP Cloud Run Deployment Script for AgentBPMN (lang-bpmn)
# Target Project: mlops2215 | Region: us-central1
# =============================================================================

$PROJECT_ID = "mlops2215"
$REGION = "us-central1"
$REPO_NAME = "scf-repo"
$SERVICE_NAME = "agent-bpmn"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  🚀 DEPLOYING AGENT-BPMN TO GOOGLE CLOUD RUN" -ForegroundColor Green
Write-Host "  Project ID:   $PROJECT_ID" -ForegroundColor Yellow
Write-Host "  Region:       $REGION" -ForegroundColor Yellow
Write-Host "  Service Name: $SERVICE_NAME" -ForegroundColor Yellow
Write-Host "============================================================`n" -ForegroundColor Cyan

# 1. Verify gcloud CLI
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Error: 'gcloud' CLI is not found in your PATH." -ForegroundColor Red
    Write-Host "Please install Google Cloud SDK or run from Google Cloud Shell / authenticated terminal:" -ForegroundColor Yellow
    Write-Host "👉 https://cloud.google.com/sdk/docs/install`n" -ForegroundColor White
    exit 1
}

# 2. Configure active project
Write-Host "▶ Setting GCP project to $PROJECT_ID..." -ForegroundColor Cyan
gcloud config set project $PROJECT_ID

# 3. Submit Cloud Build
Write-Host "▶ Submitting Google Cloud Build pipeline..." -ForegroundColor Cyan
gcloud builds submit `
    --config=cloudbuild.yaml `
    --substitutions=_REGION=$REGION,_REPO_NAME=$REPO_NAME,_SERVICE_NAME=$SERVICE_NAME `
    --project=$PROJECT_ID

if ($LASTEXITCODE -ne 0) {
    Write-Host "`n❌ Cloud Build failed. Please check the Cloud Build logs in the GCP Console." -ForegroundColor Red
    exit $LASTEXITCODE
}

# 4. Retrieve deployed Cloud Run URL
Write-Host "`n▶ Fetching deployed Cloud Run Service URL..." -ForegroundColor Cyan
$SERVICE_URL = gcloud run services describe $SERVICE_NAME --region=$REGION --project=$PROJECT_ID --format="value(status.url)"

Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "  🎉 DEPLOYMENT SUCCESSFUL!" -ForegroundColor Green
Write-Host "  🌐 AgentBPMN Studio Live URL: $SERVICE_URL" -ForegroundColor Cyan
Write-Host "  📑 API Swagger Documentation: $SERVICE_URL/docs" -ForegroundColor Cyan
Write-Host "============================================================`n" -ForegroundColor Green

