"""The image workflow and the Azure template stay inside the M6 decision."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_build_scans_the_image_before_publishing_it() -> None:
    text = _text(".github/workflows/build.yml")
    assert "branches:\n      - main" in text
    assert "pull_request" not in text
    assert "aquasecurity/trivy-action@v0.36.0" in text
    assert "format: cyclonedx" in text
    assert "severity: CRITICAL,HIGH" in text
    assert "ignore-unfixed: true" in text
    assert "ghcr.io" in text
    assert "platforms: linux/amd64" in text
    assert text.index("Scan the image") < text.index("Tag and push")
    assert "--extra agent" not in text


def test_deploy_is_manual_oidc_and_can_tear_the_group_down() -> None:
    text = _text(".github/workflows/deploy.yml")
    assert "workflow_dispatch" in text
    assert "\n  push:" not in text
    assert "pull_request" not in text
    assert "azure/login@v3" in text
    assert "id-token: write" in text
    assert "client-secret" not in text.lower()
    assert "AZURE_CLIENT_SECRET" not in text
    assert "teardown" in text
    assert "./infra/teardown.sh" in text
    assert "infra/main.bicep" in text


def test_bicep_scales_to_zero_and_budgets_the_group() -> None:
    text = _text("infra/main.bicep")
    assert "minReplicas: 0" in text
    assert "maxReplicas: 1" in text
    assert "Microsoft.App/containerApps@2025-07-01" in text
    assert "Microsoft.Consumption/budgets@2024-08-01" in text
    assert "threshold: 50" in text
    assert "threshold: 100" in text
    assert "PV_MCP_RESOURCE_URL" in text
    assert "clientSecret" not in text
    script = _text("infra/teardown.sh")
    assert "az group delete" in script


def test_the_image_stays_a_non_root_server() -> None:
    text = _text("Dockerfile")
    assert "useradd --uid 10001" in text
    assert "uv sync --frozen --no-dev --no-editable" in text
    assert "--extra agent" not in text
    assert "org.opencontainers.image.source" in text
    assert "USER pv" in text
