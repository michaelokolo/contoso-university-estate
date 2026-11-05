#!/usr/bin/env bash
# Deploy Contoso's four vendor SaaS systems to Azure Container Apps.
#
#   ./deploy/deploy-vendors.sh            first deploy (about 10-15 minutes)
#   ./deploy/deploy-vendors.sh            run again to rebuild and update (keeps the same secrets)
#
# What it creates, in resource group rg-contoso-vendors (UK South):
#   - Azure Container Registry (Basic)        stores the images; images are built IN Azure (no local Docker needed)
#   - Container Apps environment              shared network + Log Analytics for the four apps
#   - 4 container apps: portal, ucas, payments, events
#       scale to zero when idle, max 1 replica, public HTTPS
#       secrets held as Container Apps secrets, not in code
#
# Output: deploy/.vendors.env with every URL and secret (ignored by Git; keep it private).
# Remove everything:  ./deploy/teardown-vendors.sh
set -euo pipefail

cd "$(dirname "$0")/.."
RG="rg-contoso-vendors"
LOCATION="uksouth"
ENVIRONMENT="cae-contoso-vendors"
STATE="deploy/.vendors.env"

step() { printf '\n\033[1m==> %s\033[0m\n' "$*" >&2; }   # stderr, so it still shows inside $(...)

step "Checking prerequisites"
command -v az >/dev/null || { echo "Install the Azure CLI first: brew install azure-cli"; exit 1; }
az account show >/dev/null 2>&1 || { echo "Sign in first: az login"; exit 1; }
[ -f output/portal/applications.jsonl ] && [ -d output/ucas ] || {
  echo "No seed data. Run the data generator first: python data-generator/generate.py"; exit 1; }
echo "Subscription: $(az account show --query name -o tsv)"
read -r -p "Deploy to this subscription? [y/N] " ok
[ "$ok" = "y" ] || [ "$ok" = "Y" ] || exit 1
az extension add --name containerapp --upgrade --only-show-errors
az provider register --namespace Microsoft.App --wait --only-show-errors
az provider register --namespace Microsoft.ContainerRegistry --wait --only-show-errors
az provider register --namespace Microsoft.OperationalInsights --wait --only-show-errors

step "Secrets (generated once, then reused)"
if [ -f "$STATE" ]; then
  # shellcheck disable=SC1090
  source "$STATE"
  echo "Reusing secrets from $STATE"
else
  SUFFIX=$(openssl rand -hex 3)
  ACR_NAME="acrcontoso${SUFFIX}"
  ADMIN_TOKEN=$(openssl rand -hex 16)
  PORTAL_API_KEY=$(openssl rand -hex 16)
  UCAS_PROVIDER_KEY=$(openssl rand -hex 16)
  PAYMENTS_SECRET_KEY="sk_test_$(openssl rand -hex 16)"
  EVENTS_CLIENT_SECRET=$(openssl rand -hex 16)
  WEBHOOK_SECRET="whsec_$(openssl rand -hex 16)"
fi

step "Resource group, registry and Container Apps environment"
az group create -n "$RG" -l "$LOCATION" --tags project=contoso-estate -o none
az acr show -n "$ACR_NAME" -g "$RG" -o none 2>/dev/null || az acr create -n "$ACR_NAME" -g "$RG" --sku Basic -o none
az containerapp env show -n "$ENVIRONMENT" -g "$RG" -o none 2>/dev/null ||
  az containerapp env create -n "$ENVIRONMENT" -g "$RG" -l "$LOCATION" -o none
REGISTRY="${ACR_NAME}.azurecr.io"
TAG="v$(date +%Y%m%d%H%M)"

deploy_app() {   # deploy_app <name> <secrets...> -- <env vars...>
  local name="$1"; shift
  local secrets=() envs=()
  while [ "$1" != "--" ]; do secrets+=("$1"); shift; done; shift
  envs=("$@")
  step "Building $name ($TAG) in Azure Container Registry"
  az acr build -r "$ACR_NAME" -t "${name}:${TAG}" -f "systems/${name}/Dockerfile" . --only-show-errors -o none 1>&2
  if az containerapp show -n "ca-${name}" -g "$RG" -o none 2>/dev/null; then
    step "Updating ca-${name}"
    az containerapp secret set -n "ca-${name}" -g "$RG" --secrets "${secrets[@]}" -o none
    az containerapp update -n "ca-${name}" -g "$RG" --image "${REGISTRY}/${name}:${TAG}" --set-env-vars "${envs[@]}" -o none
  else
    step "Creating ca-${name}"
    az containerapp create -n "ca-${name}" -g "$RG" --environment "$ENVIRONMENT" \
      --image "${REGISTRY}/${name}:${TAG}" --registry-server "$REGISTRY" --registry-identity system \
      --ingress external --target-port 8000 --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi \
      --secrets "${secrets[@]}" --env-vars "${envs[@]}" -o none
  fi
  az containerapp show -n "ca-${name}" -g "$RG" --query properties.configuration.ingress.fqdn -o tsv
}

PORTAL_FQDN=$(deploy_app portal "api-key=$PORTAL_API_KEY" "admin-token=$ADMIN_TOKEN" "webhook-secret=$WEBHOOK_SECRET" -- \
  "PORTAL_API_KEY=secretref:api-key" "ADMIN_TOKEN=secretref:admin-token" "WEBHOOK_SECRET=secretref:webhook-secret" | tail -1)
UCAS_FQDN=$(deploy_app ucas "provider-key=$UCAS_PROVIDER_KEY" "admin-token=$ADMIN_TOKEN" -- \
  "UCAS_PROVIDER_KEY=secretref:provider-key" "ADMIN_TOKEN=secretref:admin-token" | tail -1)
PAYMENTS_FQDN=$(deploy_app payments "secret-key=$PAYMENTS_SECRET_KEY" "admin-token=$ADMIN_TOKEN" "webhook-secret=$WEBHOOK_SECRET" -- \
  "PAYMENTS_SECRET_KEY=secretref:secret-key" "ADMIN_TOKEN=secretref:admin-token" "WEBHOOK_SECRET=secretref:webhook-secret" | tail -1)
az containerapp update -n ca-payments -g "$RG" --set-env-vars "PUBLIC_URL=https://${PAYMENTS_FQDN}" -o none
EVENTS_FQDN=$(deploy_app events "client-secret=$EVENTS_CLIENT_SECRET" "admin-token=$ADMIN_TOKEN" "webhook-secret=$WEBHOOK_SECRET" -- \
  "EVENTS_CLIENT_ID=contoso-university" "EVENTS_CLIENT_SECRET=secretref:client-secret" "ADMIN_TOKEN=secretref:admin-token" \
  "WEBHOOK_SECRET=secretref:webhook-secret" | tail -1)

step "Saving URLs and secrets to $STATE"
umask 077
cat > "$STATE" <<EOF
# Contoso vendor systems: URLs and secrets. PRIVATE: never commit or share this file.
SUFFIX=$SUFFIX
ACR_NAME=$ACR_NAME
ADMIN_TOKEN=$ADMIN_TOKEN
PORTAL_API_KEY=$PORTAL_API_KEY
UCAS_PROVIDER_KEY=$UCAS_PROVIDER_KEY
PAYMENTS_SECRET_KEY=$PAYMENTS_SECRET_KEY
EVENTS_CLIENT_SECRET=$EVENTS_CLIENT_SECRET
WEBHOOK_SECRET=$WEBHOOK_SECRET
PORTAL_URL=https://$PORTAL_FQDN
UCAS_URL=https://$UCAS_FQDN
PAYMENTS_URL=https://$PAYMENTS_FQDN
EVENTS_URL=https://$EVENTS_FQDN
EOF

step "Done"
for u in "$PORTAL_FQDN" "$UCAS_FQDN" "$PAYMENTS_FQDN" "$EVENTS_FQDN"; do
  printf '  https://%s/health  ->  ' "$u"
  curl -s --max-time 60 "https://$u/health" || echo "(still starting; try again in a minute)"
  echo
done
echo
echo "First request after idle takes 10-20 seconds: the app is scaling up from zero."
