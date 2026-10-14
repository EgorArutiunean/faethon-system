"""Validate Coolify source and the standard Compose part without real secrets.

Coolify removes exclude_from_hc during parsing. Docker Compose does not accept
that extension, so validate a temporary normalized copy, not the source file.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    document = yaml.safe_load((ROOT / "docker-compose.coolify.yml").read_text())
    services = document["services"]
    assert set(services) == {"postgres", "migrate", "backend", "frontend"}
    for service in services.values():
        assert "build" not in service, "Coolify must pull published images"
        assert "ports" not in service, "Use the Coolify proxy, not host ports"
        assert "container_name" not in service, "Let Coolify isolate resource names"
    assert services["migrate"].pop("exclude_from_hc") is True
    assert services["migrate"]["restart"] == "no"
    assert services["backend"]["depends_on"]["migrate"]["condition"] == (
        "service_completed_successfully"
    )
    assert services["backend"]["environment"]["APP_ENV"] == "production"
    assert services["frontend"]["expose"] == ["8080"]
    assert services["postgres"]["volumes"] == ["postgres_data:/var/lib/postgresql/data"]
    # Prevent local production env overrides from entering this validation.
    system_keys = {
        "PATH", "SYSTEMROOT", "HOME", "USERPROFILE", "DOCKER_HOST",
        "DOCKER_CONTEXT", "DOCKER_CONFIG", "TEMP", "TMP", "APPDATA",
        "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)",
    }
    env = {k: v for k, v in os.environ.items() if k.upper() in system_keys}
    with tempfile.TemporaryDirectory(prefix="buy-coolify-check-") as directory:
        path = Path(directory) / "compose.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        subprocess.run(
            ["docker", "compose", "--env-file", str(ROOT / ".env.coolify.example"),
             "-p", "buy-coolify-check", "-f", str(path), "config", "--quiet"],
            env=env, check=True,
        )
    print("Coolify source invariants and normalized Docker Compose config passed")


if __name__ == "__main__":
    main()
