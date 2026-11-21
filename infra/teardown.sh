#!/usr/bin/env bash
# Delete the resource group created by the deploy workflow, and everything in it.
set -euo pipefail

group="${1:-rg-pv-mcp}"
az group delete --name "$group" --yes --no-wait
echo "Deletion of ${group} has been requested."
