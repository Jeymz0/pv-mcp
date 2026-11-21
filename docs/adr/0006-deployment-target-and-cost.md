# 0006. Deployment target and cost

## Status

Accepted for milestone M6.

## Context

The HTTP server already runs in Docker Compose on one machine. A remote copy
has to stay inside a budget of about zero euros: no cluster that runs while
idle, no long-lived Azure password in GitHub, and no second copy of the data.
The production Entra ID verifier is a separate decision and is not built here.

## Decision

Publish one linux/amd64 image to GHCR, and deploy it by hand to Azure
Container Apps in West Europe.

- `.github/workflows/build.yml` runs on a push to `main`. It builds the image,
  writes a CycloneDX SBOM, and scans with Trivy. A fixed HIGH or CRITICAL
  finding fails the job, and that image is not pushed. Unfixed findings are
  reported and do not fail the job, because the base image cannot be patched
  from this repository. The image that is pushed is the image that was scanned.
  The `main` tag moves only from the `main` branch. The workflow asks GitHub
  to mark the package public. A public package is what lets Container Apps
  pull it without a registry password.
- The image stays the server image. It does not install the agent extra, and
  it does not contain a token or an API key.
- `.github/workflows/deploy.yml` runs only when someone starts it. GitHub
  signs in to Azure with OIDC. The federated credential's subject is
  `repo:<owner>/<name>:ref:refs/heads/main`. `AZURE_CLIENT_ID`,
  `AZURE_TENANT_ID`, and `AZURE_SUBSCRIPTION_ID` are repository variables.
  There is no Azure client secret.
- The template is `infra/main.bicep`. One Container Apps environment, one
  app, minimum 0 replicas, maximum 1. The idle timeout is 30 minutes so a
  Streamable HTTP session is not cut at the platform default. The app listens
  on 8000. `PV_MCP_RESOURCE_URL` is the public `https://<fqdn>/mcp`, so the
  Host check and the dev token audience match the URL a client uses.
- The cache file stays on the replica's disk. Scale-to-zero discards it. A
  managed disk would be a standing cost, so there is no volume.
- Logs stay on the process stderr. A Log Analytics workspace is not created.
- A monthly budget on the resource group mails `BUDGET_CONTACT` at 50% and at
  100% of the amount. The default amount is 5, in the subscription's billing
  currency.
- `PV_MCP_TOKEN` is a repository secret passed into the app as a Container
  Apps secret. It is the same dev token the server already requires. Entra
  is not part of this deployment.
- Teardown is `infra/teardown.sh`, also the `teardown` choice of the deploy
  workflow. It deletes the resource group.

## Consequences

An idle deployment should stay near zero euros, and a month that exceeds the
budget sends mail. It does not stop the app. The first Azure setup is still
manual: an app registration, the federated credential, Contributor so the
workflow can create and delete the resource group, and Cost Management
Contributor so it can write the budget. A private GHCR package will fail the
pull until the package is public. The dev token remains a shared secret.
