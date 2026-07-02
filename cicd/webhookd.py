#!/usr/bin/env python3
import hashlib
import hmac
import json
import os
import re
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


HOST = os.getenv("SGDEV_WEBHOOK_HOST", "127.0.0.1")
PORT = int(os.getenv("SGDEV_WEBHOOK_PORT", "9000"))
INFRA_ROOT = Path(os.getenv("SGDEV_INFRA_ROOT", "/opt/sgdev-infra"))
CONFIG_DIR = Path(os.getenv("SGDEV_CONFIG_DIR", "/etc/sgdev-infra")) / "cicd"
LOG_DIR = Path(os.getenv("SGDEV_WEBHOOK_LOG_DIR", "/var/log/sgdev-infra"))
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def verify_signature(secret: str, body: bytes, signature: str | None) -> bool:
    if not signature or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def run_deploy(slug: str, deploy_script: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"{slug}-deploy.log"
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with log_file.open("ab") as log:
        log.write(f"\n\n===== deploy {slug} {started} =====\n".encode("utf-8"))
        subprocess.run([deploy_script, slug], cwd=str(INFRA_ROOT), stdout=log, stderr=subprocess.STDOUT, check=False)


class Handler(BaseHTTPRequestHandler):
    server_version = "SgdevWebhook/1.0"

    def send_text(self, status: int, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_text(200, "ok\n")
            return
        self.send_text(404, "not found\n")

    def do_POST(self) -> None:
        prefix = "/hooks/github/"
        if not self.path.startswith(prefix):
            self.send_text(404, "not found\n")
            return

        slug = self.path[len(prefix):].strip("/")
        if not SLUG_RE.match(slug):
            self.send_text(400, "invalid slug\n")
            return

        config_path = CONFIG_DIR / f"{slug}.env"
        if not config_path.exists():
            self.send_text(404, "hook config not found\n")
            return

        config = load_env(config_path)
        secret = config.get("GITHUB_WEBHOOK_SECRET", "")
        if not secret:
            self.send_text(500, "missing webhook secret\n")
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length > 2 * 1024 * 1024:
            self.send_text(413, "payload too large\n")
            return

        body = self.rfile.read(content_length)
        signature = self.headers.get("X-Hub-Signature-256")
        if not verify_signature(secret, body, signature):
            self.send_text(401, "bad signature\n")
            return

        event = self.headers.get("X-GitHub-Event", "")
        if event == "ping":
            self.send_text(200, "pong\n")
            return
        if event != "push":
            self.send_text(202, f"ignored event: {event}\n")
            return

        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_text(400, "bad json\n")
            return

        expected_repo = config.get("GITHUB_REPOSITORY", "")
        actual_repo = payload.get("repository", {}).get("full_name", "")
        if expected_repo and expected_repo != actual_repo:
            self.send_text(202, f"ignored repo: {actual_repo}\n")
            return

        branch = config.get("GITHUB_BRANCH", "main")
        ref = payload.get("ref", "")
        if ref != f"refs/heads/{branch}":
            self.send_text(202, f"ignored ref: {ref}\n")
            return

        deploy_script = config.get("DEPLOY_SCRIPT", str(INFRA_ROOT / "scripts" / "app-deploy.sh"))
        thread = threading.Thread(target=run_deploy, args=(slug, deploy_script), daemon=True)
        thread.start()
        self.send_text(202, f"deploy queued for {slug}\n")

    def log_message(self, fmt: str, *args) -> None:
        print("%s - - [%s] %s" % (self.address_string(), self.log_date_time_string(), fmt % args), flush=True)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Listening on {HOST}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()

