#!/usr/bin/env bash
# CU-4: let GitHub Actions sign in to Azure with OIDC: short-lived tokens, no stored secrets.
#
#   ./deploy/setup-oidc.sh
#
# Needs: Azure CLI (az login), GitHub CLI (gh auth login), and bootstrap-tfstate.sh already run.
#
# What it does:
#   1. Creates an Entra app registration + service principal: "github-contoso-estate"
#   2. Adds federated credentials, so ONLY these GitHub contexts can get a token:
#        - environments dev, test, prod     (deployments)
#        - pull requests                    (terraform plan in CI)
#   3. Grants the service principal, on your subscription:
#        - Contributor                                  (create and change resources)
#        - Role Based Access Control Administrator      (Terraform assigns roles, e.g. AcrPull)
#      and Storage Blob Data Contributor on the Terraform state account.
#   4. Creates GitHub environments dev, test, prod (prod requires your approval)
#   5. Stores the app's client ID, tenant ID and subscription ID as GitHub *variables*
#      (identifiers, not secrets: there is no client secret at all)
set -euo pipefail
cd "$(dirname "$0")/.."

APP_NAME="github-contoso-estate"
command -v gh >/dev/null || { echo "Install the GitHub CLI: brew install gh, then gh auth login"; exit 1; }
az account show >/dev/null 2>&1 || { echo "Sign in first: az login"; exit 1; }
[ -f infra/backend.env ] || { echo "Run ./deploy/bootstrap-tfstate.sh first"; exit 1; }
# shellcheck disable=SC1091
source infra/backend.env

REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)
echo "GitHub repo:  $REPO"
echo "Subscription: $(az account show --query name -o tsv) ($SUBSCRIPTION_ID)"
read -r -p "Set up OIDC between these? [y/N] " ok
[ "$ok" = "y" ] || [ "$ok" = "Y" ] || exit 1

echo "==> App registration and service principal"
APP_ID=$(az ad app list --display-name "$APP_NAME" --query "[0].appId" -o tsv)
if [ -z "$APP_ID" ]; then
  APP_ID=$(az ad app create --display-name "$APP_NAME" --query appId -o tsv)
fi
az ad sp show --id "$APP_ID" -o none 2>/dev/null || az ad sp create --id "$APP_ID" -o none
SP_ID=$(az ad sp show --id "$APP_ID" --query id -o tsv)

echo "==> Federated credentials"
add_credential() {   # add_credential <name> <subject>
  if az ad app federated-credential list --id "$APP_ID" --query "[?name=='$1']" -o tsv | grep -q .; then
    echo "  $1 exists"
    return
  fi
  az ad app federated-credential create --id "$APP_ID" -o none --parameters "{
    \"name\": \"$1\",
    \"issuer\": \"https://token.actions.githubusercontent.com\",
    \"subject\": \"$2\",
    \"audiences\": [\"api://AzureADTokenExchange\"]
  }"
  echo "  $1 -> $2"
}

# GitHub's immutable subject format includes the owner and repo IDs (they never change, even on rename)
OWNER_ID=$(gh api "repos/$REPO" --jq .owner.id)
REPO_ID=$(gh api "repos/$REPO" --jq .id)
SUBJECT="repo:${REPO%%/*}@${OWNER_ID}/${REPO#*/}@${REPO_ID}"
for env in dev test prod; do add_credential "env-$env" "${SUBJECT}:environment:$env"; done
add_credential "pull-requests" "${SUBJECT}:pull_request"

echo "==> Azure role assignments"
assign() {   # assign <role> <scope>
  az role assignment create --assignee-object-id "$SP_ID" --assignee-principal-type ServicePrincipal \
    --role "$1" --scope "$2" -o none 2>/dev/null && echo "  $1" || echo "  $1 (already assigned)"
}
assign "Contributor" "/subscriptions/$SUBSCRIPTION_ID"
assign "Role Based Access Control Administrator" "/subscriptions/$SUBSCRIPTION_ID"
STATE_SCOPE=$(az storage account show -n "$TFSTATE_STORAGE_ACCOUNT" -g "$TFSTATE_RESOURCE_GROUP" --query id -o tsv)
assign "Storage Blob Data Contributor" "$STATE_SCOPE"

echo "==> GitHub environments"
MY_ID=$(gh api user -q .id)
gh api -X PUT "repos/$REPO/environments/dev" --silent
gh api -X PUT "repos/$REPO/environments/test" --silent
if gh api -X PUT "repos/$REPO/environments/prod" --silent --input - <<EOF
{"reviewers": [{"type": "User", "id": $MY_ID}], "deployment_branch_policy": {"protected_branches": true, "custom_branch_policies": false}}
EOF
then
  echo "  dev, test, prod (prod needs your approval, from main only)"
else
  gh api -X PUT "repos/$REPO/environments/prod" --silent
  echo "  dev, test, prod created. Required reviewers weren't allowed: on a free account they need a PUBLIC repo."
fi

echo "==> GitHub variables (identifiers, not secrets)"
gh variable set AZURE_CLIENT_ID --body "$APP_ID"
gh variable set AZURE_TENANT_ID --body "$TENANT_ID"
gh variable set AZURE_SUBSCRIPTION_ID --body "$SUBSCRIPTION_ID"
gh variable set TFSTATE_STORAGE_ACCOUNT --body "$TFSTATE_STORAGE_ACCOUNT"
gh variable set TFSTATE_RESOURCE_GROUP --body "$TFSTATE_RESOURCE_GROUP"

echo
echo "Done. Test it: GitHub > Actions > 'Azure login check' > Run workflow."
echo "Note: role assignments can take a few minutes to apply."
