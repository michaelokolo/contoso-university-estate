#!/usr/bin/env bash
# Delete ALL Contoso vendor resources in Azure (registry, environment, four apps). Cannot be undone.
set -euo pipefail
cd "$(dirname "$0")/.."
read -r -p "Delete resource group rg-contoso-vendors and everything in it? [y/N] " ok
[ "$ok" = "y" ] || [ "$ok" = "Y" ] || exit 1
az group delete -n rg-contoso-vendors --yes --no-wait
rm -f deploy/.vendors.env
echo "Deletion started (takes a few minutes). Secrets file removed."
