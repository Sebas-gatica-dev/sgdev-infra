#!/usr/bin/env python3
import base64
import json
import os
import posixpath
import re
import shlex
import socket
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlparse

try:
    import paramiko
except ModuleNotFoundError:
    paramiko = None


ROOT = Path(__file__).resolve().parent
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
SERVICE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
DOMAIN_RE = re.compile(r"^[a-zA-Z0-9.-]+$")
APP_PATH_RE = re.compile(r"^/[a-zA-Z0-9][a-zA-Z0-9/_-]*$")
BRANCH_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._/-]{0,159}$")
APP_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,119}$")
DOCKER_HOST_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")
DOCKER_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")
SIZE_RE = re.compile(r"^[1-9][0-9]{0,5}[kKmMgG]$")
TIMEOUT_RE = re.compile(r"^[1-9][0-9]{0,5}[smh]$")
UUID_RE = re.compile(r"^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[1-5][a-fA-F0-9]{3}-[89abAB][a-fA-F0-9]{3}-[a-fA-F0-9]{12}$")
MAX_JSON_BODY_BYTES = 8 * 1024 * 1024
RESERVED_APP_PATHS = ("/admin", "/admin-api", "/health", "/__deploy", "/.well-known")
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

OPENCLAW_STATUS_SCRIPT = r"""
import json
import subprocess


def run(command, timeout=30):
    try:
        completed = subprocess.run(command, text=True, capture_output=True, timeout=timeout)
        return completed.returncode, completed.stdout.strip(), completed.stderr.strip()
    except Exception as exc:
        return 99, "", str(exc)


def route_status():
    code, stdout, stderr = run([
        "curl", "-ksS", "-o", "/dev/null", "-w", "%{http_code}",
        "https://sgdev.com.ar/admin-openclaw/",
    ], timeout=15)
    return int(stdout) if code == 0 and stdout.isdigit() else 0


code, stdout, stderr = run(["docker", "ps", "-a", "--format", "{{.Names}}"], timeout=10)
names = {line.strip() for line in stdout.splitlines() if line.strip()}
container_name = next((name for name in ["sg-openclaw-gateway", "moltbot-clawdbot-1"] if name in names), "")

if not container_name:
    print(json.dumps({
        "installed": False,
        "routeStatus": route_status(),
        "routeUrl": "https://sgdev.com.ar/admin-openclaw/",
    }))
    raise SystemExit(0)

code, stdout, stderr = run(["docker", "inspect", container_name], timeout=15)
if code != 0:
    raise SystemExit(stderr or stdout or "docker inspect failed")

container = json.loads(stdout)[0]
config = container.get("Config") or {}
state = container.get("State") or {}
working_dir = config.get("WorkingDir") or "/app"


def openclaw_command(*arguments):
    return run([
        "docker", "exec", "-w", working_dir, container_name,
        "node", "dist/index.js", *arguments,
    ], timeout=90)


version_code, version_stdout, version_stderr = openclaw_command("--version")
audit_code, audit_stdout, audit_stderr = openclaw_command("security", "audit", "--json")
audit = {}
if audit_stdout:
    try:
        audit = json.loads(audit_stdout[audit_stdout.find("{"):])
    except Exception:
        audit = {}

findings = []
for finding in audit.get("findings") or []:
    findings.append({
        "checkId": finding.get("checkId"),
        "severity": finding.get("severity"),
        "title": finding.get("title"),
    })

public_ports = []
for target, bindings in ((container.get("NetworkSettings") or {}).get("Ports") or {}).items():
    for binding in bindings or []:
        host_ip = str(binding.get("HostIp") or "")
        if host_ip not in {"127.0.0.1", "::1"}:
            public_ports.append({
                "target": target,
                "hostIp": host_ip,
                "hostPort": binding.get("HostPort"),
            })

networks = sorted(((container.get("NetworkSettings") or {}).get("Networks") or {}).keys())
health = (state.get("Health") or {}).get("Status") or ("running" if state.get("Running") else state.get("Status"))
version = (version_stdout or version_stderr).splitlines()[-1] if (version_stdout or version_stderr) else "unknown"

print(json.dumps({
    "installed": True,
    "container": container_name,
    "image": config.get("Image") or "",
    "version": version,
    "status": state.get("Status") or "unknown",
    "health": health,
    "user": config.get("User") or "image-default",
    "restartCount": container.get("RestartCount") or 0,
    "networks": networks,
    "publicPorts": public_ports,
    "routeStatus": route_status(),
    "routeUrl": "https://sgdev.com.ar/admin-openclaw/",
    "securitySummary": audit.get("summary") or {},
    "securityFindings": findings,
    "auditExitCode": audit_code,
    "migrationRequired": container_name != "sg-openclaw-gateway",
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
PORTFOLIO_ADMIN_TOKEN = os.getenv("SGDEV_PORTFOLIO_ADMIN_TOKEN", PORTFOLIO_USAGE_ADMIN_TOKEN)


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


def openclaw_status() -> dict:
    command = "python3 - <<'PY'\n" + OPENCLAW_STATUS_SCRIPT + "\nPY"
    code, stdout, stderr = target_exec(command, timeout=120)
    if code != 0:
        raise RuntimeError(stderr or stdout or f"OpenClaw status failed with exit {code}")
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


def normalize_remote_path(value: str, field: str) -> str:
    if not value.startswith("/") or "\x00" in value:
        raise ValueError(f"{field} must be an absolute path")
    normalized = posixpath.normpath(value)
    if normalized == "/" or normalized != value.rstrip("/"):
        raise ValueError(f"invalid {field}")
    return normalized


def ensure_path_within(path: str, parent: str, field: str) -> None:
    if path != parent and not path.startswith(parent + "/"):
        raise ValueError(f"{field} must stay inside {parent}")


def validate_repo_url(value: str) -> None:
    allowed_hosts = {
        host.strip().lower()
        for host in os.getenv("SGDEV_ALLOWED_GIT_HOSTS", "github.com,gitlab.com,bitbucket.org").split(",")
        if host.strip()
    }
    ssh_match = re.fullmatch(r"git@([a-zA-Z0-9.-]+):([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(?:\.git)?)", value)
    if ssh_match:
        if ssh_match.group(1).lower() not in allowed_hosts:
            raise ValueError("repoUrl host is not allowed")
        return
    parsed = urlparse(value)
    path_parts = [part for part in parsed.path.split("/") if part]
    try:
        repo_port = parsed.port
    except ValueError as error:
        raise ValueError("repoUrl has an invalid port") from error
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.hostname.lower() not in allowed_hosts
        or parsed.username
        or parsed.password
        or repo_port not in (None, 443)
        or parsed.query
        or parsed.fragment
        or len(path_parts) != 2
        or not all(re.fullmatch(r"[a-zA-Z0-9_.-]+", part.removesuffix(".git")) for part in path_parts)
    ):
        raise ValueError("repoUrl must be an HTTPS or git SSH repository on an allowed host")


def validate_domain(value: str) -> None:
    labels = value.rstrip(".").split(".")
    if (
        not DOMAIN_RE.match(value)
        or len(value) > 253
        or len(labels) < 2
        or any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-") for label in labels)
    ):
        raise ValueError("invalid domain")


def validate_app_path(value: str) -> None:
    normalized = value.rstrip("/") or "/"
    if value != normalized or not APP_PATH_RE.match(value) or "//" in value or "/../" in value:
        raise ValueError("invalid public path")
    if any(value == reserved or value.startswith(reserved + "/") for reserved in RESERVED_APP_PATHS):
        raise ValueError("public path is reserved by SgInfra")


def validate_upstream(value: str, slug: str) -> None:
    parsed = urlparse(value)
    hostname = parsed.hostname or ""
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("invalid upstream port") from error
    if (
        parsed.scheme != "http"
        or not hostname
        or not DOCKER_HOST_RE.match(hostname)
        or hostname.lower() in {"localhost", "host.docker.internal"}
        or re.fullmatch(r"[0-9.]+", hostname)
        or not (hostname == slug or hostname.startswith(slug + "-"))
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or (port is not None and not 1 <= port <= 65535)
        or parsed.path not in ("", "/")
    ):
        raise ValueError(f"upstream must target an internal {slug}-* Docker service")


def validate_relative_file(value: str, field: str) -> None:
    if len(value) > 240 or value.startswith("/") or "//" in value:
        raise ValueError(f"invalid {field}")
    parts = value.split("/")
    if any(
        part in ("", ".", "..") or not re.fullmatch(r"\.?[a-zA-Z0-9][a-zA-Z0-9._-]*", part)
        for part in parts
    ):
        raise ValueError(f"invalid {field}")


def validate_compose_file(value: str) -> None:
    if not value.startswith("/"):
        validate_relative_file(value, "composeFiles")
        return
    normalized = normalize_remote_path(value, "composeFiles")
    trusted_root = posixpath.normpath(f"{REMOTE_INFRA_ROOT}/examples/project-compose")
    ensure_path_within(normalized, trusted_root, "composeFiles")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*\.ya?ml", posixpath.basename(normalized)):
        raise ValueError("invalid composeFiles")


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
    app_preset = safe_text(payload, "appPreset", "existing-compose", max_len=40)
    compose_files = safe_text(payload, "composeFiles", "compose.yml", max_len=400)
    env_file = safe_text(payload, "envFile", ".env", max_len=120)

    if not repo_url:
        raise ValueError("repoUrl is required")
    validate_repo_url(repo_url)
    validate_domain(domain)
    validate_app_path(app_path)
    apps_root = normalize_remote_path(os.getenv("SGDEV_APPS_ROOT", "/opt/apps"), "apps root")
    expected_app_root = f"{apps_root}/{slug}"
    repo_dir = normalize_remote_path(repo_dir, "repoDir")
    app_root = normalize_remote_path(app_root, "appRoot")
    if app_root != expected_app_root:
        raise ValueError(f"appRoot must be {expected_app_root}")
    ensure_path_within(repo_dir, app_root, "repoDir")
    if app_preset == "vite-static":
        compose_files = f"{app_root}/generated/compose.yml"
        upstream = f"http://{slug}-web:80"
    elif app_preset == "spring-boot":
        compose_files = f"{app_root}/generated/compose.yml"
        upstream = f"http://{slug}-web:8080"
    elif app_preset != "existing-compose":
        raise ValueError("unsupported appPreset")
    validate_upstream(upstream, slug)
    if not BRANCH_RE.match(branch) or ".." in branch or "//" in branch:
        raise ValueError("invalid branch")
    if not APP_ID_RE.match(app_id):
        raise ValueError("invalid appId")
    if not compose_files:
        raise ValueError("composeFiles is required")
    try:
        compose_entries = shlex.split(compose_files)
    except ValueError as error:
        raise ValueError("invalid composeFiles") from error
    if not 1 <= len(compose_entries) <= 5:
        raise ValueError("composeFiles must contain between one and five files")
    for compose_entry in compose_entries:
        if app_preset == "existing-compose":
            validate_compose_file(compose_entry)
        elif compose_entry != f"{app_root}/generated/compose.yml":
            raise ValueError("invalid generated compose path")
    compose_files = " ".join(compose_entries)
    validate_relative_file(env_file, "envFile")

    client_max_body_size = safe_text(payload, "clientMaxBodySize", "25m", max_len=40)
    proxy_connect_timeout = safe_text(payload, "proxyConnectTimeout", "10s", max_len=40)
    proxy_read_timeout = safe_text(payload, "proxyReadTimeout", "120s", max_len=40)
    proxy_send_timeout = safe_text(payload, "proxySendTimeout", "120s", max_len=40)
    if not SIZE_RE.match(client_max_body_size):
        raise ValueError("invalid clientMaxBodySize")
    for key, value in {
        "proxyConnectTimeout": proxy_connect_timeout,
        "proxyReadTimeout": proxy_read_timeout,
        "proxySendTimeout": proxy_send_timeout,
    }.items():
        if not TIMEOUT_RE.match(value):
            raise ValueError(f"invalid {key}")

    backup_volumes = safe_text(payload, "backupVolumes", max_len=400)
    backup_paths = safe_text(payload, "backupPaths", max_len=400)
    for volume in shlex.split(backup_volumes):
        if not DOCKER_NAME_RE.match(volume):
            raise ValueError("invalid backupVolumes")
    for backup_path in shlex.split(backup_paths):
        if backup_path.startswith("/"):
            normalized_backup_path = normalize_remote_path(backup_path, "backupPaths")
            ensure_path_within(normalized_backup_path, app_root, "backupPaths")
        else:
            validate_relative_file(backup_path, "backupPaths")

    db_engine = safe_text(payload, "dbEngine", max_len=40).lower()
    db_service = safe_text(payload, "dbService", max_len=80)
    db_name = safe_text(payload, "dbName", max_len=120)
    db_user = safe_text(payload, "dbUser", max_len=120)
    db_app_id_column = safe_text(payload, "dbAppIdColumn", "app_id", max_len=80)
    if db_engine and db_engine not in {"postgres", "postgresql", "mysql", "mariadb"}:
        raise ValueError("unsupported dbEngine")
    for key, value in {
        "dbService": db_service,
        "dbName": db_name,
        "dbUser": db_user,
        "dbAppIdColumn": db_app_id_column,
    }.items():
        if value and not re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_.@$-]{0,119}", value):
            raise ValueError(f"invalid {key}")
    if db_engine and not all((db_service, db_name, db_user)):
        raise ValueError("dbService, dbName and dbUser are required with dbEngine")

    env_values = {
        "APP_NAME": name,
        "APP_ID": app_id,
        "APP_DOMAIN": domain,
        "APP_ROOT": app_root,
        "GIT_REMOTE_URL": repo_url,
        "BRANCH": branch,
        "APP_PRESET": app_preset,
        "COMPOSE_FILES": compose_files,
        "ENV_FILE": env_file,
        "STRIP_PREFIX": "true" if payload.get("stripPrefix", True) else "false",
        "APP_NEW_CLONE": "true" if payload.get("cloneRepo", True) else "false",
        "CLIENT_MAX_BODY_SIZE": client_max_body_size,
        "PROXY_CONNECT_TIMEOUT": proxy_connect_timeout,
        "PROXY_READ_TIMEOUT": proxy_read_timeout,
        "PROXY_SEND_TIMEOUT": proxy_send_timeout,
        "REJECT_PUBLIC_PORTS": "true",
        "BACKUP_VOLUMES": backup_volumes,
        "BACKUP_PATHS": backup_paths,
        "DB_EXCEL_ENGINE": db_engine,
        "DB_EXCEL_SERVICE": db_service,
        "DB_EXCEL_DATABASE": db_name,
        "DB_EXCEL_USER": db_user,
        "DB_EXCEL_APP_ID_COLUMN": db_app_id_column,
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
    if PORTFOLIO_ADMIN_TOKEN:
        headers["Authorization"] = f"Bearer {PORTFOLIO_ADMIN_TOKEN}"
        headers["X-Sgdev-Portfolio-Admin-Token"] = PORTFOLIO_ADMIN_TOKEN

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


def require_uuid(payload: dict, key: str) -> str:
    value = safe_text(payload, key, max_len=36)
    if not UUID_RE.match(value):
        raise ValueError(f"invalid {key}")
    return value


def portfolio_projects() -> dict:
    return portfolio_api_request("GET", "/admin/projects")


def portfolio_save_project(payload: dict) -> dict:
    return portfolio_api_request("POST", "/admin/projects", payload)


def portfolio_delete_project(payload: dict) -> dict:
    project_id = require_uuid(payload, "projectId")
    return portfolio_api_request("DELETE", f"/admin/projects/{quote(project_id)}")


def portfolio_upload_project_image(payload: dict) -> dict:
    project_id = require_uuid(payload, "projectId")
    image_payload = payload.get("image")
    if not isinstance(image_payload, dict):
        raise ValueError("image is required")
    return portfolio_api_request("POST", f"/admin/projects/{quote(project_id)}/images", image_payload)


def portfolio_delete_project_image(payload: dict) -> dict:
    project_id = require_uuid(payload, "projectId")
    image_id = require_uuid(payload, "imageId")
    return portfolio_api_request(
        "DELETE",
        f"/admin/projects/{quote(project_id)}/images/{quote(image_id)}",
    )


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
            if parsed.path == "/portfolio/projects":
                self.send_json(200, portfolio_projects())
                return
            if parsed.path == "/openclaw/status":
                self.send_json(200, {"ok": True, **openclaw_status()})
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
            if length > MAX_JSON_BODY_BYTES:
                self.send_json(413, {"ok": False, "error": "request body too large"})
                return
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
            if parsed.path == "/portfolio/projects":
                self.send_json(200, portfolio_save_project(payload))
                return
            if parsed.path == "/portfolio/projects/delete":
                self.send_json(200, portfolio_delete_project(payload))
                return
            if parsed.path == "/portfolio/projects/images":
                self.send_json(200, portfolio_upload_project_image(payload))
                return
            if parsed.path == "/portfolio/projects/images/delete":
                self.send_json(200, portfolio_delete_project_image(payload))
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
