"""Exercise a normalized Coolify stack in a NEW disposable Docker project.

Requires PyYAML, Docker Compose and locally available release images. Publishes
only a random loopback HTTP port for this test. Removes only its own containers
and test volume in finally. Does not test the Coolify parser, proxy or TLS.
"""

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "scripts"))
from release_smoke import request_json  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-image", required=True)
    parser.add_argument("--frontend-image", required=True)
    args = parser.parse_args()
    source = (ROOT / "docker-compose.coolify.yml").read_text(encoding="utf-8")
    document = yaml.safe_load(source)
    document["services"]["migrate"].pop("exclude_from_hc")
    document["services"]["frontend"]["ports"] = ["127.0.0.1::8080"]
    project = "buy-coolify-smoke-" + uuid.uuid4().hex[:12]
    env = os.environ.copy()
    for key in re.findall(r"\$\{([A-Z_]+)", source):
        env.pop(key, None)
    password = secrets.token_hex(24)
    env.update(
        BACKEND_IMAGE=args.backend_image,
        FRONTEND_IMAGE=args.frontend_image,
        RELEASE_VERSION="coolify-local-smoke",
        POSTGRES_DB="buy_smoke",
        POSTGRES_USER="buy_smoke",
        POSTGRES_PASSWORD=password,
        DATABASE_URL=f"postgresql+psycopg://buy_smoke:{password}@postgres:5432/buy_smoke",
        AUTH_SECRET_KEY=secrets.token_hex(32),
        CORS_ORIGINS="https://coolify-smoke.example.com",
        BOOTSTRAP_ADMIN_EMAIL="coolify-smoke@example.com",
        BOOTSTRAP_ADMIN_PASSWORD=secrets.token_hex(24),
    )
    with tempfile.TemporaryDirectory(prefix=project + "-") as directory:
        config = Path(directory) / "compose.json"
        config.write_text(json.dumps(document), encoding="utf-8")
        empty_env = Path(directory) / "empty.env"
        empty_env.touch()
        command = ["docker", "compose", "--env-file", str(empty_env),
                   "-p", project, "-f", str(config)]

        def compose(*arguments: str, check: bool = True) -> subprocess.CompletedProcess:
            result = subprocess.run(command + list(arguments), env=env, text=True,
                                    capture_output=True, check=False, timeout=240)
            if check and result.returncode:
                # Docker output here contains only synthetic test credentials.
                print(result.stdout, result.stderr, file=sys.stderr)
                result.check_returncode()
            return result

        def base_url() -> str:
            return "http://" + compose("port", "frontend", "8080").stdout.strip()

        def smoke(base: str, admin_password: str) -> None:
            smoke_env = dict(env, SMOKE_BASE_URL=base,
                             SMOKE_EMAIL=env["BOOTSTRAP_ADMIN_EMAIL"],
                             SMOKE_PASSWORD=admin_password)
            subprocess.run([sys.executable, str(ROOT / "backend/scripts/release_smoke.py")],
                           env=smoke_env, check=True, timeout=90)

        # A random project name is also checked before any mutations/cleanup.
        existing = subprocess.check_output(
            ["docker", "ps", "-aq", "--filter",
             f"label=com.docker.compose.project={project}"], env=env, text=True)
        if existing.strip():
            raise RuntimeError("Generated test project unexpectedly exists")
        print(f"Disposable test project: {project}", flush=True)
        try:
            compose("up", "-d", "--wait", "--wait-timeout", "150", "--pull", "never")
            compose("exec", "-T", "-e", "BOOTSTRAP_ADMIN_EMAIL", "-e",
                    "BOOTSTRAP_ADMIN_PASSWORD", "backend", "python", "scripts/bootstrap_admin.py")
            base = base_url()
            _, login = request_json(base, "/api/v1/auth/login", method="POST", payload={
                "email": env["BOOTSTRAP_ADMIN_EMAIL"],
                "password": env["BOOTSTRAP_ADMIN_PASSWORD"],
            })
            new_password = secrets.token_hex(24)
            _, user = request_json(base, "/api/v1/auth/change-password", method="POST",
                                   token=login["access_token"], payload={
                                       "current_password": env["BOOTSTRAP_ADMIN_PASSWORD"],
                                       "new_password": new_password,
                                   })
            assert user["must_change_password"] is False
            smoke(base, new_password)
            print("PASS: migration, nginx routing, bootstrap, password change and login", flush=True)
            compose("down")  # Keep the newly created test volume for persistence check.
            compose("up", "-d", "--wait", "--wait-timeout", "150", "--pull", "never")
            smoke(base_url(), new_password)
            print("PASS: account survives full container/network recreation", flush=True)
            compose("down")
            document["services"]["migrate"]["command"] = ["python", "-c", "raise SystemExit(7)"]
            config.write_text(json.dumps(document), encoding="utf-8")
            failed = compose("up", "-d", "--pull", "never", check=False)
            assert failed.returncode != 0, "Migration failure must fail deployment"
            migration_id = compose("ps", "-a", "-q", "migrate").stdout.strip()
            exit_code = subprocess.check_output(
                ["docker", "inspect", "--format", "{{.State.ExitCode}}", migration_id],
                env=env, text=True,
            ).strip()
            assert exit_code == "7", "Expected the deliberate migration failure"
            running = compose("ps", "--status", "running", "--services").stdout.splitlines()
            assert "backend" not in running and "frontend" not in running
            print("PASS: failed migration blocks backend and frontend startup", flush=True)
        finally:
            compose("down", "--volumes", "--remove-orphans")
            print(f"Removed disposable containers/network/volume for {project}", flush=True)


if __name__ == "__main__":
    main()
