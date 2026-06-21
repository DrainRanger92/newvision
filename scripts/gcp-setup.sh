#!/usr/bin/env bash
# NewVision — GCP Infrastructure Setup
# Creates GCP project, enables APIs, creates Artifact Registry, GCS bucket, configures IAM.
# Idempotent: safe to re-run.

set -euo pipefail

REGION=europe-west1
PROJECT_ID=newvision-telegram

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[GCP Setup]${NC} $1"; }
warn()  { echo -e "${YELLOW}[GCP Setup]${NC} $1"; }
error() { echo -e "${RED}[GCP Setup]${NC} $1"; }

# ---- Pre-flight ----
info "Pre-flight checks..."

if ! command -v gcloud &>/dev/null; then
  error "gcloud CLI not found. Install: https://cloud.google.com/sdk/docs/install"
  exit 1
fi

ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null || true)
if [[ -z "$ACCOUNT" ]]; then
  error "No active gcloud account. Run: gcloud auth login"
  exit 1
fi
info "Authenticated as $ACCOUNT"

BILLING=$(gcloud billing projects list --filter="projectId:$PROJECT_ID" --format="value(billingEnabled)" 2>/dev/null || true)
BILLING_ACCT=$(gcloud billing accounts list --filter=open=true --format="value(name)" --limit=1 2>/dev/null || true)
if [[ -z "$BILLING_ACCT" ]]; then
  error "No active billing account found. Link one at https://console.cloud.google.com/billing"
  exit 1
fi
info "Billing account available: $BILLING_ACCT"

echo ""

# ---- Step 1: Project ----
info "🏗️  Step 1/6: Project $PROJECT_ID"

EXISTING_PROJECT=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)" 2>/dev/null || true)
if [[ -n "$EXISTING_PROJECT" ]]; then
  warn "Project $PROJECT_ID already exists. Switching..."
  gcloud config set project "$PROJECT_ID" >/dev/null
else
  gcloud projects create "$PROJECT_ID" --set-as-default --name="NewVision" >/dev/null
  info "Project $PROJECT_ID created and set as default"
fi

# Link billing if not linked
if [[ "$BILLING" != "True" ]]; then
  gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCT" >/dev/null
  info "Billing linked to $PROJECT_ID"
fi

echo ""

# ---- Step 2: Region ----
info "🌍  Step 2/6: Default region $REGION"

gcloud config set run/region "$REGION" 2>/dev/null
info "Default region set to $REGION"

echo ""

# ---- Step 3: APIs ----
info "🔌  Step 3/6: Enabling APIs..."

APIS=(
  run.googleapis.com
  artifactregistry.googleapis.com
  cloudbuild.googleapis.com
  secretmanager.googleapis.com
  storage.googleapis.com
)

for api in "${APIS[@]}"; do
  ENABLED=$(gcloud services list --enabled --filter="config.name:$api" --format="value(config.name)" 2>/dev/null || true)
  if [[ "$ENABLED" == "$api" ]]; then
    warn "  $api already enabled — skipping"
  else
    gcloud services enable "$api" >/dev/null
    info "  $api enabled"
  fi
done

echo ""

# ---- Step 4: Artifact Registry ----
info "📦  Step 4/6: Artifact Registry repository"

REPO_EXISTS=$(gcloud artifacts repositories describe newvision --location="$REGION" --format="value(name)" 2>/dev/null || true)
if [[ -n "$REPO_EXISTS" ]]; then
  warn "Repository newvision already exists — skipping"
else
  gcloud artifacts repositories create newvision \
    --repository-format=docker \
    --location="$REGION" \
    >/dev/null
  info "Repository newvision created in $REGION"
fi

echo ""

# ---- Step 5: GCS Bucket ----
info "🪣  Step 5/6: GCS bucket"

BUCKET_NAME=""
if gsutil ls "gs://$PROJECT_ID-data" &>/dev/null 2>&1; then
  warn "Bucket gs://$PROJECT_ID-data already exists — skipping"
  BUCKET_NAME="$PROJECT_ID-data"
else
  if gsutil mb -l "$REGION" "gs://$PROJECT_ID-data" &>/dev/null 2>&1; then
    info "Bucket gs://$PROJECT_ID-data created"
    BUCKET_NAME="$PROJECT_ID-data"
  else
    PROJECT_NUM=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
    FALLBACK="$PROJECT_ID-data-$PROJECT_NUM"
    warn "Bucket name $PROJECT_ID-data taken — using fallback $FALLBACK"
    gsutil mb -l "$REGION" "gs://$FALLBACK" >/dev/null
    info "Bucket gs://$FALLBACK created"
    BUCKET_NAME="$FALLBACK"
  fi
fi

echo ""

# ---- Step 6: IAM ----
info "🔑  Step 6/6: Cloud Build SA IAM"

CLOUDBUILD_SA="$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")@cloudbuild.gserviceaccount.com"

# Retry loop: SA may take several minutes on a fresh project
info "Waiting for Cloud Build SA to propagate (up to 5 min)..."
for i in $(seq 1 60); do
  if gcloud iam service-accounts describe "$CLOUDBUILD_SA" &>/dev/null; then
    info "Cloud Build SA found after ${i}s"
    break
  fi
  if [[ "$i" -eq 36 ]]; then
    error "Cloud Build SA did not appear after 300s."
    error "Check manually: gcloud iam service-accounts list --project=$PROJECT_ID"
    exit 1
  fi
  sleep 5
done

bind_role() {
  local role="$1"
  local has_role
  has_role=$(gcloud projects get-iam-policy "$PROJECT_ID" --flatten="bindings[].members" --filter="bindings.role=$role AND bindings.members:serviceAccount:$CLOUDBUILD_SA" --format="value(bindings.role)" 2>/dev/null || true)
  if [[ -n "$has_role" ]]; then
    warn "  $role already granted — skipping"
  else
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
      --member="serviceAccount:$CLOUDBUILD_SA" \
      --role="$role" \
      >/dev/null
    info "  $role granted"
  fi
}

bind_role "roles/run.admin"
bind_role "roles/iam.serviceAccountUser"
bind_role "roles/secretmanager.secretAccessor"

echo ""

# ---- Summary ----
echo "────────────────────────────────────────"
info "✅ GCP Setup complete!"
echo ""
echo "  Project:         $PROJECT_ID"
echo "  Region:          $REGION"
echo "  Artifact Reg:    $REGION-docker.pkg.dev/$PROJECT_ID/newvision"
echo "  GCS Bucket:      gs://$BUCKET_NAME"
echo "  Cloud Build SA:  $CLOUDBUILD_SA"
echo ""
echo "  Roles granted:"
echo "    - roles/run.admin"
echo "    - roles/iam.serviceAccountUser"
echo "    - roles/secretmanager.secretAccessor"
echo "────────────────────────────────────────"
