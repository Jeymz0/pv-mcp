"""M7 keeps the threat model and the architecture picture in the repository."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_security_model_names_the_four_abuses() -> None:
    text = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    assert "Prompt injection and poisoned tool output" in text
    assert "Data leaving the process" in text
    assert "Denial of service" in text
    assert "Supply chain" in text
    assert "private security advisory" in text
    assert "Entra" in text


def test_readme_shows_the_picture_and_points_at_the_threat_model() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "```mermaid" in text
    assert "openFDA" in text
    assert "SECURITY.md" in text
    assert "What it costs" in text
    assert "docker compose up --build" in text
