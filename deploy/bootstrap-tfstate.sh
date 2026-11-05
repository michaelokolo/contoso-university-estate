#!/usr/bin/env bash
# CU-3: create the storage account that holds Terraform state for every environment.
#
#   ./deploy/bootstrap-tfstate.sh
#
# This is the one piece of infrastructure created outside Terraform (Terraform can't
# store its state in something it hasn't created yet). Run it once.
#
# Creates, in rg-contoso-tfstate (UK South):
#   - a storage account: no public blob access, no shared keys (Entra ID only), TLS 1.2,
#     blob versioning and 14-day soft delete (so a bad state write can be recovered)
#   - a "tfstate" container; Terraform uses keys dev.tfstate, test.tfstate, prod.tfstate
#   - gives YOU "Storage Blob Data Contributor" so you can run Terraform locally
# Saves the names to infra/backend.env (not secret: just names).
set -euo pipefail
cd "$(dirname "$0")/.."

RG="rg-contoso-tfstate"
LOCATION="uksouth"
OUT="infra/backend.env"

az account show >/dev/null 2>&1 || { echo "Sign in first: az login"; exit 1; }
echo "Subscription: $(az account show --query name -o tsv)"
read -r -p "Create Terraform state storage in this subscription? [y/N] " ok
[ "$ok" = "y" ] || [ "$ok" = "Y" ] || exit 1
az provider register --namespace Microsoft.Storage --wait --only-show-errors

if [ -f "$OUT" ]; then
  # shellcheck disable=SC1090
  source "$OUT"
  echo "Reusing storage account $TFSTATE_STORAGE_ACCOUNT"
else
  TFSTATE_STORAGE_ACCOUNT="sttfcontoso$(openssl rand -hex 3)"
fi

az group create -n "$RG" -l "$LOCATION" --tags project=contoso-estate purpose=terraform-state -o none
az storage account show -n "$TFSTATE_STORAGE_ACCOUNT" -g "$RG" -o none 2>/dev/null ||
  az storage account create -n "$TFSTATE_STORAGE_ACCOUNT" -g "$RG" -l "$LOCATION" \
    --sku Standard_LRS --kind StorageV2 --min-tls-version TLS1_2 \
    --allow-blob-public-access false --allow-shared-key-access false -o none

az storage account blob-service-properties update -n "$TFSTATE_STORAGE_ACCOUNT" -g "$RG" \
  --enable-versioning true --enable-delete-retention true --delete-retention-days 14 -o none

SCOPE=$(az storage account show -n "$TFSTATE_STORAGE_ACCOUNT" -g "$RG" --query id -o tsv)
ME=$(az ad signed-in-user show --query id -o tsv)
az role assignment create --role "Storage Blob Data Contributor" --assignee-object-id "$ME" \
  --assignee-principal-type User --scope "$SCOPE" -o none 2>/dev/null || true

echo "Waiting 60 seconds for the role assignment to take effect..."
sleep 60
az storage container create --name tfstate --account-name "$TFSTATE_STORAGE_ACCOUNT" --auth-mode login -o none

mkdir -p infra
cat > "$OUT" <<EOF
# Terraform remote state (CU-3). Names only, no secrets: safe to commit.
TFSTATE_RESOURCE_GROUP=$RG
TFSTATE_STORAGE_ACCOUNT=$TFSTATE_STORAGE_ACCOUNT
TFSTATE_CONTAINER=tfstate
EOF

echo
echo "Done. Terraform state lives in:"
echo "  storage account: $TFSTATE_STORAGE_ACCOUNT   container: tfstate   (resource group $RG)"
echo "Saved to $OUT. Commit that file. Next: ./deploy/setup-oidc.sh"
