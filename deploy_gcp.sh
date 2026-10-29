#!/usr/bin/env bash
# =============================================================================
# Automated GCP Cloud Run Deployment Script for AgentBPMN (lang-bpmn)
# Target Project: mlops2215 | Region: us-central1
# =============================================================================
set -e

PROJECT_ID="mlops2215"
REGION="us-central1"
REPO_NAME="scf-repo"
SERVICE_NAME="agent-bpmn"

echo "============================================================"
echo "  🚀 DEPLOYING AGENT-BPMN TO GOOGLE CLOUD RUN"
echo "  Project ID:   $PROJECT_ID"
echo "  Region:       $REGION"
echo "  Service Name: $SERVICE_NAME"
echo "============================================================"

# Verify gcloud CLI
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: 'gcloud' CLI is not installed or not in PATH."
    echo "👉 Install from https://cloud.google.com/sdk/docs/install"
    exit 1
fi

echo "▶ Setting GCP project to $PROJECT_ID..."
gcloud config set project "$PROJECT_ID"

echo "▶ Submitting Google Cloud Build pipeline..."
gcloud builds submit \
    --config=cloudbuild.yaml \
    --substitutions=_REGION="$REGION",_REPO_NAME="$REPO_NAME",_SERVICE_NAME="$SERVICE_NAME" \
    --project="$PROJECT_ID"

echo "▶ Fetching deployed Cloud Run Service URL..."
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --project="$PROJECT_ID" --format="value(status.url)")

echo ""
echo "============================================================"
echo "  🎉 DEPLOYMENT SUCCESSFUL!"
echo "  🌐 AgentBPMN Studio Live URL: $SERVICE_URL"
echo "  📑 API Swagger Documentation: $SERVICE_URL/docs"
echo "============================================================"

