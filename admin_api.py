#!/usr/bin/env python3
import base64
import json
import os
import re
import shlex
import socket
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

try:
    import paramiko
except ModuleNotFoundError:
    paramiko = None


ROOT = Path(__file__).resolve().parent
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
SERVICE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
DOMAIN_RE = re.compile(r"^[a-zA-Z0-9.-]+$")
REMOTE_STATE_SCRIPT = r"""
import glob
import json
import os
import re
import subprocess
import time
from pathlib import Path

CONFIG_DIR = Path(os.getenv("SGDEV_APPS_CONFIG_DIR", "/etc/sgdev-infra/apps"))
INFRA_ROOT = Path(os.getenv("SGDEV_INFRA_ROOT", "/opt/sgdev-infra"))
LOG_DIR = Path(os.getenv("SGDEV_WEBHOOK_LOG_DIR", "/var/log/sgdev-infra"))


def run(command, timeout=10):
    try:
        completed = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        return completed.returncode, completed.stdout, completed.stderr
    except Exception as exc:
        return 99, "", str(exc)


def parse_env(path):
    values = {}
    try:
        for raw in Path(path).read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return values


def parse_percent(value):
    try:
        return float(str(value).replace("%", "").strip())
    except Exception:
        return 0.0


def upstream_host(value):
    value = str(value or "")
    value = re.sub(r"^https?://", "", value)
    return value.split("/", 1)[0].split(":", 1)[0]


def load_containers():
    code, stdout, stderr = run("docker ps -aq", timeout=8)
    ids = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not ids:
        return []
    safe_ids = " ".join(ids)
    code, stdout, stderr = run(f"docker inspect {safe_ids}", timeout=20)
    if code != 0:
        return []
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return []


def load_stats():
    code, stdout, stderr = run("docker stats --no-stream --format '{{json .}}'", timeout=15)
    stats = {}
    for line in stdout.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        names = [item.get("Name", ""), item.get("Container", "")]
        for name in names:
            if name:
                stats[name] = item
    return stats


def container_names_for_app(app, containers):
    slug = app["slug"]
    upstream = upstream_host(app.get("upstream"))
    matches = []
    for container in containers:
        name = container.get("Name", "").lstrip("/")
        config = container.get("Config") or {}
        labels = config.get("Labels") or {}
        project = labels.get("com.docker.compose.project", "")
        service = labels.get("com.docker.compose.service", "")
        aliases = []
        for network in (container.get("NetworkSettings") or {}).get("Networks", {}).values():
            aliases.extend(network.get("Aliases") or [])

        haystack = " ".join([name, project, service] + aliases)
        if slug in haystack or (upstream and upstream in haystack):
            matches.append(container)
    return matches


def compose_contains_wordpress(repo_dir, compose_files):
    for compose_file in str(compose_files or "compose.yml").split():
        path = Path(repo_dir) / compose_file
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
        except FileNotFoundError:
            continue
        if "wordpress:" in text or "image: wordpress" in text:
            return True
    return False


containers = load_containers()
stats = load_stats()
apps = []

for config_path in sorted(CONFIG_DIR.glob("*.env")):
    config = parse_env(config_path)
    slug = config.get("APP_SLUG") or config_path.stem
    repo_dir = config.get("REPO_DIR") or f"/opt/apps/{slug}/repo"
    app = {
        "slug": slug,
        "name": config.get("APP_NAME") or slug.replace("-", " ").replace("_", " ").title(),
        "appId": config.get("APP_ID") or f"app_{slug.replace('-', '_')}",
        "domain": config.get("APP_DOMAIN") or os.getenv("SGDEV_PRIMARY_DOMAIN", "sgdev.com.ar"),
        "path": config.get("APP_PATH") or f"/{slug}",
        "repo": config.get("GIT_REMOTE_URL") or f"local:{repo_dir}",
        "branch": config.get("BRANCH") or "main",
        "upstream": config.get("APP_UPSTREAM") or "",
        "compose": config.get("COMPOSE_FILES") or config.get("COMPOSE_FILE") or "compose.yml",
        "env": config.get("ENV_FILE") or ".env",
        "status": "idle",
        "cpu": 0,
        "memory": 0,
        "disk": 0,
        "restarts": 0,
        "containers": [],
        "updatedAt": "",
        "kind": "wordpress" if config.get("WORDPRESS_CONTENT_REPO") is not None else "app",
    }
    if app["kind"] != "wordpress" and compose_contains_wordpress(repo_dir, app["compose"]):
        app["kind"] = "wordpress"

    matched = container_names_for_app({"slug": slug, "upstream": app["upstream"]}, containers)
    app["containers"] = [item.get("Name", "").lstrip("/") for item in matched]
    app["restarts"] = sum(int((item.get("RestartCount") or 0)) for item in matched)
    running = [item for item in matched if (item.get("State") or {}).get("Running")]
    if running:
        app["status"] = "running"
    elif matched:
        app["status"] = "stopped"

    cpu_total = 0.0
    mem_total = 0.0
    for name in app["containers"]:
        stat = stats.get(name) or {}
        cpu_total += parse_percent(stat.get("CPUPerc"))
        mem_total += parse_percent(stat.get("MemPerc"))
    app["cpu"] = round(cpu_total, 1)
    app["memory"] = round(mem_total, 1)

    try:
        app["updatedAt"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(config_path.stat().st_mtime))
    except OSError:
        app["updatedAt"] = ""
    apps.append(app)


def first_line(command):
    code, stdout, stderr = run(command, timeout=6)
    return (stdout or stderr).strip().splitlines()[0] if (stdout or stderr).strip() else ""


operations = []
for log_path in sorted(LOG_DIR.glob("*-deploy.log"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)[:10]:
    slug = log_path.name.replace("-deploy.log", "")
    try:
        at = time.strftime("%Y-%m-%d %H:%M", time.localtime(log_path.stat().st_mtime))
    except OSError:
        at = ""
    operations.append({
        "app": slug,
        "action": "deploy-log",
        "status": "ok",
        "at": at,
        "command": f"tail -n 80 {log_path}",
    })


disk_root = first_line("df -h / | awk 'NR==2 {print $5}'")
mem_line = first_line("free -m | awk 'NR==2 {printf \"%s/%sMB %.0f%%\", $3, $2, $3*100/$2}'")
load_avg = first_line("cat /proc/loadavg")
docker_version = first_line("docker --version")


def read_meminfo():
    values = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, raw = line.split(":", 1)
            number = int(raw.strip().split()[0]) * 1024
            values[key] = number
    except Exception:
        pass
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", 0)
    used = max(total - available, 0)
    swap_total = values.get("SwapTotal", 0)
    swap_free = values.get("SwapFree", 0)
    swap_used = max(swap_total - swap_free, 0)
    return {
        "used_percent": round((used * 100 / total) if total else 0, 1),
        "used_bytes": used,
        "available_bytes": available,
        "swap_used_percent": round((swap_used * 100 / swap_total) if swap_total else 0, 1),
        "swap_used_bytes": swap_used,
        "swap_total_bytes": swap_total,
    }


def disk_snapshot():
    rows = []
    seen = set()
    for path in ["/", "/opt", "/var/lib/docker"]:
        code, stdout, stderr = run(f"df -B1 {path} 2>/dev/null | awk 'NR==2 {{print $6, $2, $3, $4, $5}}'", timeout=4)
        if code != 0 or not stdout.strip():
            continue
        mount, total, used, available, percent = stdout.strip().split()[:5]
        if mount in seen:
            continue
        seen.add(mount)
        rows.append({
            "path": mount,
            "used_percent": parse_percent(percent),
            "used_bytes": int(used),
            "available_bytes": int(available),
        })
    return rows


def process_snapshot():
    code, count_out, count_err = run("ps -e --no-headers | wc -l", timeout=4)
    count = int(count_out.strip() or 0) if code == 0 else 0
    code, stdout, stderr = run("ps -eo pid,user,state,pcpu,pmem,rss,comm --sort=-pcpu | head -n 11", timeout=5)
    top = []
    for line in stdout.splitlines()[1:]:
        parts = line.split(None, 6)
        if len(parts) < 7:
            continue
        top.append({
            "pid": int(parts[0]),
            "user": parts[1],
            "state": parts[2],
            "cpu_percent": parse_percent(parts[3]),
            "memory_percent": parse_percent(parts[4]),
            "rss_bytes": int(parts[5]) * 1024,
            "command": parts[6],
        })
    return {"count": count, "top": top, "error": "" if code == 0 else stderr.strip()}


def network_snapshot():
    rows = []
    try:
        for line in Path("/proc/net/dev").read_text(encoding="utf-8").splitlines()[2:]:
            name, raw = line.split(":", 1)
            parts = raw.split()
            rows.append({
                "name": name.strip(),
                "rx_bytes": int(parts[0]),
                "rx_packets": int(parts[1]),
                "tx_bytes": int(parts[8]),
                "tx_packets": int(parts[9]),
            })
    except Exception:
        pass
    return {"interfaces": rows}


def docker_snapshot():
    rows = []
    for container in containers:
        name = container.get("Name", "").lstrip("/")
        state = container.get("State") or {}
        config = container.get("Config") or {}
        labels = config.get("Labels") or {}
        stat = stats.get(name) or {}
        rows.append({
            "name": name,
            "image": config.get("Image") or "",
            "state": state.get("Status") or ("running" if state.get("Running") else "stopped"),
            "cpu_percent": parse_percent(stat.get("CPUPerc")),
            "memory_percent": parse_percent(stat.get("MemPerc")),
            "memory_usage": stat.get("MemUsage") or "",
            "restart_count": container.get("RestartCount") or 0,
            "compose_project": labels.get("com.docker.compose.project", ""),
        })
    return {
        "available": True,
        "running": sum(1 for item in rows if item["state"] == "running"),
        "total": len(rows),
        "containers": rows,
    }


def uptime_seconds():
    try:
        return int(float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0]))
    except Exception:
        return 0


def os_pretty_name():
    try:
        values = parse_env("/etc/os-release")
        return values.get("PRETTY_NAME") or "Linux"
    except Exception:
        return "Linux"


snapshot = {
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "host": {
        "hostname": first_line("hostname"),
        "os": os_pretty_name(),
        "kernel": first_line("uname -r"),
        "architecture": first_line("uname -m"),
        "uptime_seconds": uptime_seconds(),
    },
    "cpu": {
        "cores": first_line("nproc") or "-",
        "usage_percent": round(sum(float(app.get("cpu") or 0) for app in apps), 1),
        "load_average": (load_avg.split()[:3] if load_avg else ["0", "0", "0"]),
    },
    "memory": read_meminfo(),
    "disks": disk_snapshot(),
    "docker": docker_snapshot(),
    "processes": process_snapshot(),
    "network": network_snapshot(),
    "security": {
        "process_args_included": False,
    },
}

print(json.dumps({
    "remote": {
        "hostname": first_line("hostname"),
        "generatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        "diskRoot": disk_root,
        "memory": mem_line,
        "loadAvg": load_avg,
        "docker": docker_version,
        "infraRoot": str(INFRA_ROOT),
        "configDir": str(CONFIG_DIR),
    },
    "settings": {
        "controlDomain": os.getenv("SGDEV_PRIMARY_DOMAIN", "sgdev.com.ar"),
        "adminPath": "/admin",
        "proxyNetwork": os.getenv("PROXY_NETWORK", "sgdev-proxy"),
        "appsRoot": os.getenv("SGDEV_APPS_ROOT", "/opt/apps"),
        "configRoot": str(CONFIG_DIR),
        "backupsRoot": os.getenv("SGDEV_BACKUPS_ROOT", "/opt/backups"),
        "deployHookPath": "/__deploy/github/",
    },
    "apps": apps,
    "operations": operations,
    "snapshot": snapshot,
}))
"""


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(ROOT / ".env.admin.local")
load_env_file(ROOT / ".env")

HOST = os.getenv("SGDEV_ADMIN_API_HOST", "127.0.0.1")
PORT = int(os.getenv("SGDEV_ADMIN_API_PORT", "9101"))
ADMIN_TOKEN = os.getenv("SGDEV_ADMIN_TOKEN", "")
ADMIN_API_TOKEN = os.getenv("SGDEV_ADMIN_API_TOKEN", "")
ADMIN_PASSWORD = os.getenv("SGDEV_ADMIN_PASSWORD", "")
VPS_HOST = os.getenv("SGDEV_VPS_HOST", "")
VPS_PORT = int(os.getenv("SGDEV_VPS_PORT", "22"))
VPS_USER = os.getenv("SGDEV_VPS_USER", "root")
VPS_PASSWORD = os.getenv("SGDEV_VPS_PASSWORD", "")
REMOTE_INFRA_ROOT = os.getenv("SGDEV_REMOTE_INFRA_ROOT", "/opt/sgdev-infra")
API_MODE = os.getenv("SGDEV_ADMIN_API_MODE", "ssh" if VPS_HOST else "local").lower()
PORTFOLIO_API_BASE_URL = os.getenv("SGDEV_PORTFOLIO_API_BASE_URL", "http://127.0.0.1:8787/api").rstrip("/")
PORTFOLIO_USAGE_ADMIN_TOKEN = os.getenv(
    "SGDEV_PORTFOLIO_USAGE_ADMIN_TOKEN",
    os.getenv("PORTFOLIO_USAGE_ADMIN_TOKEN", ""),
)


def ssh_exec(command: str, timeout: int = 30) -> tuple[int, str, str]:
    if not VPS_HOST:
        return 2, "", "SGDEV_VPS_HOST is not configured"
    if paramiko is None:
        return 2, "", "paramiko is required for SGDEV_ADMIN_API_MODE=ssh"
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=VPS_HOST,
            port=VPS_PORT,
            username=VPS_USER,
            password=VPS_PASSWORD or None,
            timeout=12,
            banner_timeout=12,
            auth_timeout=12,
        )
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        return exit_code, stdout.read().decode("utf-8", "replace"), stderr.read().decode("utf-8", "replace")
    finally:
        client.close()


def local_exec(command: str, timeout: int = 30) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout,
            executable="/bin/bash" if os.name != "nt" else None,
        )
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout or "", exc.stderr or "command timed out"
    except OSError as exc:
        return 127, "", str(exc)
    return completed.returncode, completed.stdout, completed.stderr


def target_exec(command: str, timeout: int = 30) -> tuple[int, str, str]:
    if API_MODE == "local":
        return local_exec(command, timeout=timeout)
    if API_MODE == "ssh":
        return ssh_exec(command, timeout=timeout)
    return 2, "", f"unsupported SGDEV_ADMIN_API_MODE: {API_MODE}"


def remote_state() -> dict:
    command = "python3 - <<'PY'\n" + REMOTE_STATE_SCRIPT + "\nPY"
    code, stdout, stderr = target_exec(command, timeout=45)
    if code != 0:
        raise RuntimeError(stderr or stdout or f"remote state failed with exit {code}")
    return json.loads(stdout)


def remote_logs(slug: str, service: str, tail: int) -> dict:
    if not SLUG_RE.match(slug):
        raise ValueError("invalid slug")
    if service and not SERVICE_RE.match(service):
        raise ValueError("invalid service")
    tail = max(20, min(int(tail or 200), 1000))
    service_arg = shlex.quote(service) if service else ""
    script = f"""
set -euo pipefail
cd {shlex.quote(REMOTE_INFRA_ROOT)}
source scripts/lib.sh
load_app_config {shlex.quote(slug)}
compose_args="$(compose_base_args)"
docker compose $compose_args logs --no-color --tail {tail} {service_arg}
"""
    code, stdout, stderr = target_exec("bash -lc " + shlex.quote(script), timeout=45)
    return {"exitCode": code, "stdout": stdout, "stderr": stderr}


def remote_action(action: str, slug: str, no_pull: bool = False) -> dict:
    if not SLUG_RE.match(slug):
        raise ValueError("invalid slug")
    commands = {
        "deploy": f"./scripts/app-deploy.sh {shlex.quote(slug)}" + (" --no-pull" if no_pull else ""),
        "deploy-local": f"./scripts/app-deploy.sh {shlex.quote(slug)} --no-pull",
        "status": f"./scripts/app-status.sh {shlex.quote(slug)}",
        "backup": f"./scripts/app-backup.sh {shlex.quote(slug)}",
        "db-export": f"./scripts/app-db-export-excel.sh {shlex.quote(slug)}",
        "stop": f"./scripts/app-stop.sh {shlex.quote(slug)}",
        "remove": f"./scripts/app-remove.sh {shlex.quote(slug)}",
        "remove-stop": f"./scripts/app-remove.sh {shlex.quote(slug)} --stop",
    }
    if action not in commands:
        raise ValueError("unsupported action")
    script = f"cd {shlex.quote(REMOTE_INFRA_ROOT)} && {commands[action]}"
    timeout = 600 if action in {"deploy", "deploy-local", "backup", "db-export"} else 90
    code, stdout, stderr = target_exec("bash -lc " + shlex.quote(script), timeout=timeout)
    return {"exitCode": code, "stdout": stdout, "stderr": stderr, "command": commands[action]}


def safe_text(payload: dict, key: str, default: str = "", max_len: int = 500) -> str:
    value = str(payload.get(key, default) or "").strip()
    if "\n" in value or "\r" in value:
        raise ValueError(f"{key} cannot contain newlines")
    if len(value) > max_len:
        raise ValueError(f"{key} is too long")
    return value


def remote_create_app(payload: dict) -> dict:
    slug = safe_text(payload, "slug", max_len=80)
    if not SLUG_RE.match(slug):
        raise ValueError("invalid slug")

    name = safe_text(payload, "name", max_len=120)
    repo_url = safe_text(payload, "repoUrl", max_len=400)
    domain = safe_text(payload, "domain", max_len=180)
    app_path = safe_text(payload, "path", f"/{slug}", max_len=160)
    upstream = safe_text(payload, "upstream", f"http://{slug}-nginx:80", max_len=240)
    repo_dir = safe_text(payload, "repoDir", f"/opt/apps/{slug}/repo", max_len=260)
    app_root_default = repo_dir.rsplit("/", 1)[0] if "/" in repo_dir.strip("/") else f"/opt/apps/{slug}"
    app_root = safe_text(payload, "appRoot", app_root_default, max_len=260)
    branch = safe_text(payload, "branch", "main", max_len=160)
    app_id = safe_text(payload, "appId", f"app_{slug.replace('-', '_')}", max_len=120)
    compose_files = safe_text(payload, "composeFiles", "compose.yml", max_len=400)
    env_file = safe_text(payload, "envFile", ".env", max_len=120)

    if not repo_url:
        raise ValueError("repoUrl is required")
    if not domain or not DOMAIN_RE.match(domain):
        raise ValueError("invalid domain")
    if not app_path.startswith("/") or app_path == "/":
        raise ValueError("path must start with / and cannot be /")
    if not upstream.startswith(("http://", "https://")):
        raise ValueError("upstream must start with http:// or https://")
    if not repo_dir.startswith("/"):
        raise ValueError("repoDir must be absolute")
    if not compose_files:
        raise ValueError("composeFiles is required")

    env_values = {
        "APP_NAME": name,
        "APP_ID": app_id,
        "APP_DOMAIN": domain,
        "APP_ROOT": app_root,
        "GIT_REMOTE_URL": repo_url,
        "BRANCH": branch,
        "COMPOSE_FILES": compose_files,
        "ENV_FILE": env_file,
        "STRIP_PREFIX": "true" if payload.get("stripPrefix", True) else "false",
        "APP_NEW_CLONE": "true" if payload.get("cloneRepo", True) else "false",
        "CLIENT_MAX_BODY_SIZE": safe_text(payload, "clientMaxBodySize", "25m", max_len=40),
        "PROXY_CONNECT_TIMEOUT": safe_text(payload, "proxyConnectTimeout", "10s", max_len=40),
        "PROXY_READ_TIMEOUT": safe_text(payload, "proxyReadTimeout", "120s", max_len=40),
        "PROXY_SEND_TIMEOUT": safe_text(payload, "proxySendTimeout", "120s", max_len=40),
        "BACKUP_VOLUMES": safe_text(payload, "backupVolumes", max_len=400),
        "BACKUP_PATHS": safe_text(payload, "backupPaths", max_len=400),
        "DB_EXCEL_ENGINE": safe_text(payload, "dbEngine", max_len=40),
        "DB_EXCEL_SERVICE": safe_text(payload, "dbService", max_len=80),
        "DB_EXCEL_DATABASE": safe_text(payload, "dbName", max_len=120),
        "DB_EXCEL_USER": safe_text(payload, "dbUser", max_len=120),
        "DB_EXCEL_APP_ID_COLUMN": safe_text(payload, "dbAppIdColumn", "app_id", max_len=80),
    }
    if not any(env_values[key] for key in ["DB_EXCEL_ENGINE", "DB_EXCEL_SERVICE", "DB_EXCEL_DATABASE", "DB_EXCEL_USER"]):
        env_values["DB_EXCEL_APP_ID_COLUMN"] = ""
    env_parts = [f"{key}={shlex.quote(value)}" for key, value in env_values.items() if value]
    args = " ".join(shlex.quote(value) for value in [slug, repo_dir, upstream, app_path, compose_files, env_file])
    command = " ".join(["env", *env_parts, f"./scripts/app-new.sh {args}"])
    script = f"cd {shlex.quote(REMOTE_INFRA_ROOT)} && {command}"
    code, stdout, stderr = target_exec("bash -lc " + shlex.quote(script), timeout=300)
    return {"exitCode": code, "stdout": stdout, "stderr": stderr, "command": f"./scripts/app-new.sh {args}"}


def remote_db_export(slug: str) -> bytes:
    if not SLUG_RE.match(slug):
        raise ValueError("invalid slug")
    script = f"""
set -euo pipefail
cd {shlex.quote(REMOTE_INFRA_ROOT)}
tmp_file="$(mktemp --suffix=.xlsx)"
log_file="$(mktemp)"
cleanup() {{
  rm -f "$tmp_file" "$log_file"
}}
trap cleanup EXIT
if ./scripts/app-db-export-excel.sh {shlex.quote(slug)} "$tmp_file" >"$log_file" 2>&1; then
  base64 -w 0 "$tmp_file" 2>/dev/null || base64 "$tmp_file" | tr -d '\\n'
else
  cat "$log_file" >&2
  exit 1
fi
"""
    code, stdout, stderr = target_exec("bash -lc " + shlex.quote(script), timeout=600)
    if code != 0:
        raise RuntimeError(stderr or stdout or f"db export failed with exit {code}")
    return base64.b64decode(stdout.strip())


def portfolio_api_request(method: str, path: str, payload=None) -> dict:
    if not PORTFOLIO_API_BASE_URL:
        raise RuntimeError("SGDEV_PORTFOLIO_API_BASE_URL is not configured")
    url = PORTFOLIO_API_BASE_URL + path
    body = None
    headers = {
        "Accept": "application/json",
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if PORTFOLIO_USAGE_ADMIN_TOKEN:
        headers["Authorization"] = f"Bearer {PORTFOLIO_USAGE_ADMIN_TOKEN}"
        headers["X-Sgdev-Portfolio-Admin-Token"] = PORTFOLIO_USAGE_ADMIN_TOKEN

    request = urllib_request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib_request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8", "replace")
            return json.loads(raw or "{}")
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            error_payload = json.loads(raw)
        except json.JSONDecodeError:
            error_payload = {"message": raw}
        raise RuntimeError(error_payload.get("message") or error_payload.get("error") or f"portfolio HTTP {exc.code}")
    except URLError as exc:
        raise RuntimeError(f"portfolio API unavailable: {exc.reason}") from exc


def portfolio_usage() -> dict:
    return portfolio_api_request("GET", "/admin/usage/ips")


def portfolio_grant_tokens(payload: dict) -> dict:
    return portfolio_api_request("POST", "/admin/usage/grant", payload)


class Handler(BaseHTTPRequestHandler):
    server_version = "SgdevAdminAPI/0.1"

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(self, status: int, body: bytes, content_type: str, filename: str = "") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    def authed(self) -> bool:
        valid_tokens = {value for value in [ADMIN_TOKEN, ADMIN_API_TOKEN, ADMIN_PASSWORD, VPS_PASSWORD] if value}
        if not valid_tokens:
            return True
        auth = self.headers.get("Authorization", "")
        token = self.headers.get("X-Sgdev-Admin-Token", "")
        if auth.startswith("Bearer "):
            token = auth.removeprefix("Bearer ").strip()
        return token in valid_tokens

    def reject_if_needed(self) -> bool:
        if self.path.startswith("/health"):
            return False
        if not self.authed():
            self.send_json(401, {"ok": False, "error": "unauthorized"})
            return True
        return False

    def do_GET(self) -> None:
        if self.reject_if_needed():
            return
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/health":
                self.send_json(200, {"ok": True, "host": socket.gethostname()})
                return
            if parsed.path == "/state":
                payload = remote_state()
                payload["ok"] = True
                self.send_json(200, payload)
                return
            if parsed.path == "/logs":
                query = parse_qs(parsed.query)
                slug = (query.get("slug") or [""])[0]
                service = (query.get("service") or [""])[0]
                tail = int((query.get("tail") or ["200"])[0])
                self.send_json(200, {"ok": True, **remote_logs(slug, service, tail)})
                return
            if parsed.path == "/db/export":
                query = parse_qs(parsed.query)
                slug = (query.get("slug") or [""])[0]
                body = remote_db_export(slug)
                stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
                self.send_bytes(
                    200,
                    body,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    f"{slug}-db-{stamp}.xlsx",
                )
                return
            if parsed.path == "/portfolio/usage":
                self.send_json(200, portfolio_usage())
                return
            self.send_json(404, {"ok": False, "error": "not found"})
        except Exception as exc:
            self.send_json(500, {"ok": False, "error": str(exc)})

    def do_POST(self) -> None:
        if self.reject_if_needed():
            return
        parsed = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length else b"{}"
            payload = json.loads(body.decode("utf-8"))
            if parsed.path == "/actions":
                result = remote_action(
                    str(payload.get("action", "")),
                    str(payload.get("slug", "")),
                    bool(payload.get("noPull", False)),
                )
                self.send_json(200, {"ok": result["exitCode"] == 0, **result})
                return
            if parsed.path == "/apps":
                result = remote_create_app(payload)
                self.send_json(200, {"ok": result["exitCode"] == 0, **result})
                return
            if parsed.path == "/portfolio/usage/grant":
                self.send_json(200, portfolio_grant_tokens(payload))
                return
            self.send_json(404, {"ok": False, "error": "not found"})
        except Exception as exc:
            self.send_json(500, {"ok": False, "error": str(exc)})

    def log_message(self, fmt: str, *args) -> None:
        print("%s - - [%s] %s" % (self.address_string(), self.log_date_time_string(), fmt % args), flush=True)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"SGDEV admin API listening on {HOST}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
