#!/usr/bin/env bash
# NewVision — GCP Secrets Setup
# Creates secrets in Secret Manager, assigns IAM roles for Cloud Run.
# Run AFTER gcp-setup.sh. Idempotent: safe to re-run.
#
# Usage:
#   1. Set env vars first:
#      export DEEPSEEK_API_KEY="sk-..."
#      export BOT_TOKEN="123:abc..."
#   2. Run: bash scripts/gcp-secrets.sh
#
# Or pass inline:
#   DEEPSEEK_API_KEY="sk-..." BOT_TOKEN="123:abc..." bash scripts/gcp-secrets.sh

set -euo pipefail

REGION=europe-west1
PROJECT_ID=newvision-telegram

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[GCP Secrets]${NC} $1"; }
warn()  { echo -e "${YELLOW}[GCP Secrets]${NC} $1"; }
error() { echo -e "${RED}[GCP Secrets]${NC} $1"; }

# ---- Pre-flight ----
info "Pre-flight checks..."

if ! command -v gcloud &>/dev/null; then
  error "gcloud CLI not found. Run in Cloud Shell or install: https://cloud.google.com/sdk/docs/install"
  exit 1
fi

ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null || true)
if [[ -z "$ACCOUNT" ]]; then
  error "No active gcloud account. Run: gcloud auth login"
  exit 1
fi
info "Authenticated as $ACCOUNT"

gcloud config set project "$PROJECT_ID" >/dev/null 2>&1 || true

if [[ -z "${DEEPSEEK_API_KEY:-}" && -z "${BOT_TOKEN:-}" ]]; then
  echo ""
  warn "Neither DEEPSEEK_API_KEY nor BOT_TOKEN are set."
  echo "  Export them first:"
  echo "    export DEEPSEEK_API_KEY=\"sk-your-key-here\""
  echo "    export BOT_TOKEN=\"123456:ABC-def-ghi\""
  echo "  Then re-run this script."
  echo ""
  info "You can also create secrets manually:"
  echo "  gcloud secrets create deepseek-api-key --project=$PROJECT_ID --region=$REGION"
  echo "  echo -n 'sk-your-key' | gcloud secrets versions add deepseek-api-key --data-file=-"
  echo ""
  exit 0
fi

echo ""

# ---- Step 1: Create secrets ----
info "🔐 Step 1/3: Creating secrets in Secret Manager..."

create_secret() {
  local NAME="$1"
  local VALUE="$2"

  if gcloud secrets describe "$NAME" --project="$PROJECT_ID" --region="$REGION" &>/dev/null; then
    warn "Secret $NAME already exists. Adding new version..."
    echo -n "$VALUE" | gcloud secrets versions add "$NAME" --data-file=- --region="$REGION" >/dev/null
  else
    info "Creating secret $NAME..."
    echo -n "$VALUE" | gcloud secrets create "$NAME" \
      --project="$PROJECT_ID" --region="$REGION" \
      --data-file=- >/dev/null
  fi
}

if [[ -n "${DEEPSEEK_API_KEY:-}" ]]; then
  create_secret "deepseek-api-key" "$DEEPSEEK_API_KEY"
  info "  ✅ deepseek-api-key created/updated"
fi

if [[ -n "${BOT_TOKEN:-}" ]]; then
  create_secret "bot-token" "$BOT_TOKEN"
  info "  ✅ bot-token created/updated"
fi

# ---- Step 2: Grant Cloud Run SA access to secrets ----
info "🔑 Step 2/3: Granting Cloud Run SA access to secrets..."

# Get default compute SA
COMPUTE_SA=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")-compute@developer.gserviceaccount.com

gcloud secrets add-iam-policy-binding deepseek-api-key \
  --project="$PROJECT_ID" --region="$REGION" \
  --member="serviceAccount:$COMPUTE_SA" \
  --role="roles/secretmanager.secretAccessor" >/dev/null 2>&1 || true

gcloud secrets add-iam-policy-binding bot-token \
  --project="$PROJECT_ID" --region="$REGION" \
  --member="serviceAccount:$COMPUTE_SA" \
  --role="roles/secretmanager.secretAccessor" >/dev/null 2>&1 || true

info "  ✅ Cloud Run SA granted access to both secrets"

# ---- Step 3: Verify ----
info "✅ Step 3/3: Verification..."

for SECRET in deepseek-api-key bot-token; do
  VERSIONS=$(gcloud secrets versions list "$SECRET" --project="$PROJECT_ID" --region="$REGION" --format="value(name)" 2>/dev/null | wc -l)
  if [[ "$VERSIONS" -gt 0 ]]; then
    info "  ✅ $SECRET: $VERSIONS version(s)"
  else
    warn "  ⚠️  $SECRET: no versions found (created but empty?)"
  fi
done

echo ""
info "🎉 Secrets setup complete!"
echo ""
echo "Next step: gcloud builds submit --config=cloudbuild.yaml --region=$REGION ."
echo "Or wait for GitHub → Cloud Build trigger (issue #39)."
