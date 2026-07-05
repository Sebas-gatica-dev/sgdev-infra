#!/usr/bin/env python3
import json
import os
import platform
import shutil
import socket
import subprocess
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


HOST = os.getenv("SGDEV_ADMIN_API_HOST", "127.0.0.1")
PORT = int(os.getenv("SGDEV_ADMIN_API_PORT", "9100"))
API_TOKEN = os.getenv("SGDEV_ADMIN_API_TOKEN", "").strip()
PROCESS_LIMIT = int(os.getenv("SGDEV_MONITOR_PROCESS_LIMIT", "12"))
PROCESS_ARGS = os.getenv("SGDEV_MONITOR_PROCESS_ARGS", "false").lower() in {"1", "true", "yes"}
DOCKER_MODE = os.getenv("SGDEV_MONITOR_DOCKER", "auto").lower()
DISK_PATHS = [path.strip() for path in os.getenv("SGDEV_MONITOR_DISK_PATHS", "/,/opt,/opt/apps,/opt/backups").split(",") if path.strip()]
INFRA_ROOT = Path(os.getenv("SGDEV_INFRA_ROOT", "/opt/sgdev-infra"))
APPS_CONFIG_DIR = Path(os.getenv("SGDEV_APPS_CONFIG_DIR", "/etc/sgdev-infra/apps"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_text(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def parse_key_value_file(path: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in read_text(path).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip('"')
    return values


def run_command(args: list[str], timeout: float = 4.0) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, str(error)
    output = completed.stdout if completed.returncode == 0 else completed.stderr
    return completed.returncode == 0, output.strip()


def read_cpu_times() -> list[int]:
    lines = read_text("/proc/stat").splitlines()
    if not lines:
        return [0, 0, 0, 0, 0, 0, 0, 0]
    first_line = lines[0]
    return [int(value) for value in first_line.split()[1:]]


def cpu_usage_percent() -> float:
    first = read_cpu_times()
    time.sleep(0.08)
    second = read_cpu_times()
    idle_a = first[3] + (first[4] if len(first) > 4 else 0)
    idle_b = second[3] + (second[4] if len(second) > 4 else 0)
    total_a = sum(first)
    total_b = sum(second)
    total_delta = total_b - total_a
    idle_delta = idle_b - idle_a
    if total_delta <= 0:
        return 0.0
    return round(max(0.0, min(100.0, (total_delta - idle_delta) * 100.0 / total_delta)), 1)


def load_average() -> list[float]:
    try:
        return [round(value, 2) for value in os.getloadavg()]
    except (AttributeError, OSError):
        return [0.0, 0.0, 0.0]


def uptime_seconds() -> int:
    raw = read_text("/proc/uptime").split()
    if not raw:
        return 0
    return int(float(raw[0]))


def memory_snapshot() -> dict[str, Any]:
    meminfo: dict[str, int] = {}
    for line in read_text("/proc/meminfo").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        parts = value.strip().split()
        if parts and parts[0].isdigit():
            meminfo[key] = int(parts[0]) * 1024

    total = meminfo.get("MemTotal", 0)
    available = meminfo.get("MemAvailable", 0)
    free = meminfo.get("MemFree", 0)
    used = max(0, total - available)
    swap_total = meminfo.get("SwapTotal", 0)
    swap_free = meminfo.get("SwapFree", 0)
    swap_used = max(0, swap_total - swap_free)
    return {
        "total_bytes": total,
        "available_bytes": available,
        "free_bytes": free,
        "used_bytes": used,
        "used_percent": round((used * 100.0 / total), 1) if total else 0.0,
        "swap_total_bytes": swap_total,
        "swap_used_bytes": swap_used,
        "swap_used_percent": round((swap_used * 100.0 / swap_total), 1) if swap_total else 0.0,
    }


def disk_snapshot() -> list[dict[str, Any]]:
    disks: list[dict[str, Any]] = []
    if not hasattr(os, "statvfs"):
        return disks
    seen: set[str] = set()
    for raw_path in DISK_PATHS:
        path = Path(raw_path)
        if not path.exists():
            continue
        try:
            stat = os.statvfs(path)
        except OSError:
            continue
        total = stat.f_blocks * stat.f_frsize
        free = stat.f_bfree * stat.f_frsize
        available = stat.f_bavail * stat.f_frsize
        used = max(0, total - free)
        resolved = str(path.resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        disks.append(
            {
                "path": str(path),
                "resolved_path": resolved,
                "total_bytes": total,
                "used_bytes": used,
                "available_bytes": available,
                "used_percent": round((used * 100.0 / total), 1) if total else 0.0,
            }
        )
    return disks


def process_count() -> int:
    try:
        return sum(1 for entry in Path("/proc").iterdir() if entry.name.isdigit())
    except OSError:
        return 0


def process_snapshot() -> dict[str, Any]:
    args_column = "args" if PROCESS_ARGS else "comm"
    ok, output = run_command(
        ["ps", "-eo", f"pid=,ppid=,user=,stat=,pcpu=,pmem=,rss=,{args_column}=", "--sort=-pcpu"],
        timeout=3.0,
    )
    processes: list[dict[str, Any]] = []
    if ok:
        for line in output.splitlines()[:PROCESS_LIMIT]:
            parts = line.strip().split(None, 7)
            if len(parts) < 8:
                continue
            pid, ppid, user, stat, cpu, mem, rss, command = parts
            processes.append(
                {
                    "pid": int(pid),
                    "ppid": int(ppid),
                    "user": user,
                    "state": stat,
                    "cpu_percent": float(cpu),
                    "memory_percent": float(mem),
                    "rss_bytes": int(rss) * 1024,
                    "command": command[:160],
                }
            )
    return {
        "count": process_count(),
        "top": processes,
        "args_included": PROCESS_ARGS,
        "error": None if ok else output,
    }


def network_snapshot() -> list[dict[str, Any]]:
    interfaces: list[dict[str, Any]] = []
    for line in read_text("/proc/net/dev").splitlines()[2:]:
        if ":" not in line:
            continue
        name, data = line.split(":", 1)
        fields = data.split()
        if len(fields) < 16:
            continue
        interfaces.append(
            {
                "name": name.strip(),
                "rx_bytes": int(fields[0]),
                "rx_packets": int(fields[1]),
                "tx_bytes": int(fields[8]),
                "tx_packets": int(fields[9]),
            }
        )
    return interfaces


def registered_apps() -> list[dict[str, str]]:
    apps: list[dict[str, str]] = []
    if not APPS_CONFIG_DIR.exists():
        return apps
    for env_file in sorted(APPS_CONFIG_DIR.glob("*.env")):
        config = parse_key_value_file(str(env_file))
        slug = config.get("APP_SLUG", env_file.stem)
        apps.append(
            {
                "slug": slug,
                "path": config.get("APP_PATH", f"/{slug}"),
                "upstream": config.get("APP_UPSTREAM", ""),
                "domain": config.get("APP_DOMAIN", ""),
            }
        )
    return apps


def parse_percent(value: str) -> float:
    try:
        return float(value.strip().replace("%", ""))
    except ValueError:
        return 0.0


def docker_snapshot() -> dict[str, Any]:
    if DOCKER_MODE == "off":
        return {"available": False, "containers": [], "running": 0, "total": 0, "error": "disabled"}
    if not shutil.which("docker"):
        return {"available": False, "containers": [], "running": 0, "total": 0, "error": "docker command not found"}

    ok, ps_output = run_command(["docker", "ps", "--all", "--format", "{{json .}}"], timeout=4.0)
    if not ok:
        return {"available": False, "containers": [], "running": 0, "total": 0, "error": ps_output}

    containers: list[dict[str, Any]] = []
    ids: list[str] = []
    for line in ps_output.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        container_id = item.get("ID", "")
        if container_id:
            ids.append(container_id)
        containers.append(
            {
                "id": container_id,
                "name": item.get("Names", ""),
                "image": item.get("Image", ""),
                "status": item.get("Status", ""),
                "state": "running" if item.get("State") == "running" or str(item.get("Status", "")).lower().startswith("up") else "stopped",
                "ports": item.get("Ports", ""),
                "networks": item.get("Networks", ""),
                "cpu_percent": 0.0,
                "memory_percent": 0.0,
                "memory_usage": "",
                "network_io": "",
                "block_io": "",
                "pids": "",
                "restart_count": 0,
                "compose_project": "",
                "compose_service": "",
            }
        )

    by_name = {item["name"]: item for item in containers}
    ok_stats, stats_output = run_command(["docker", "stats", "--no-stream", "--format", "{{json .}}"], timeout=5.0)
    if ok_stats:
        for line in stats_output.splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            name = item.get("Name") or item.get("Container") or ""
            target = by_name.get(name)
            if not target:
                continue
            target["cpu_percent"] = parse_percent(item.get("CPUPerc", "0"))
            target["memory_percent"] = parse_percent(item.get("MemPerc", "0"))
            target["memory_usage"] = item.get("MemUsage", "")
            target["network_io"] = item.get("NetIO", "")
            target["block_io"] = item.get("BlockIO", "")
            target["pids"] = item.get("PIDs", "")

    if ids:
        ok_inspect, inspect_output = run_command(["docker", "inspect", *ids], timeout=6.0)
        if ok_inspect:
            try:
                inspected = json.loads(inspect_output)
            except json.JSONDecodeError:
                inspected = []
            for item in inspected:
                name = str(item.get("Name", "")).lstrip("/")
                target = by_name.get(name)
                if not target:
                    continue
                state = item.get("State", {})
                labels = item.get("Config", {}).get("Labels", {}) or {}
                target["state"] = state.get("Status", target["state"])
                target["restart_count"] = int(item.get("RestartCount", 0) or 0)
                target["compose_project"] = labels.get("com.docker.compose.project", "")
                target["compose_service"] = labels.get("com.docker.compose.service", "")

    running = sum(1 for item in containers if item["state"] == "running")
    return {
        "available": True,
        "containers": containers,
        "running": running,
        "total": len(containers),
        "error": None if ok_stats else stats_output,
    }


def host_snapshot() -> dict[str, Any]:
    os_release = parse_key_value_file("/etc/os-release")
    return {
        "hostname": socket.gethostname(),
        "fqdn": socket.getfqdn(),
        "os": os_release.get("PRETTY_NAME", platform.platform()),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "cpu_count": os.cpu_count() or 1,
        "uptime_seconds": uptime_seconds(),
        "infra_root": str(INFRA_ROOT),
    }


def snapshot() -> dict[str, Any]:
    return {
        "ok": True,
        "generated_at": utc_now(),
        "security": {
            "token_required": bool(API_TOKEN),
            "process_args_included": PROCESS_ARGS,
        },
        "host": host_snapshot(),
        "cpu": {
            "usage_percent": cpu_usage_percent(),
            "load_average": load_average(),
            "cores": os.cpu_count() or 1,
        },
        "memory": memory_snapshot(),
        "disks": disk_snapshot(),
        "processes": process_snapshot(),
        "network": {
            "interfaces": network_snapshot(),
        },
        "docker": docker_snapshot(),
        "apps": {
            "registered": registered_apps(),
        },
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "SgdevAdminMonitor/1.0"

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, status: int, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def is_authorized(self) -> bool:
        if not API_TOKEN:
            return True
        header_token = self.headers.get("X-SGDEV-Admin-Token", "").strip()
        auth = self.headers.get("Authorization", "").strip()
        bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        return header_token == API_TOKEN or bearer == API_TOKEN

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path == "/health":
            self.send_text(200, "ok\n")
            return
        if not self.is_authorized():
            self.send_json(401, {"ok": False, "error": "unauthorized"})
            return
        if path in {"/v1/snapshot", "/snapshot"}:
            self.send_json(200, snapshot())
            return
        self.send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        self.send_json(405, {"ok": False, "error": "method not allowed"})

    def log_message(self, fmt: str, *args: Any) -> None:
        print("%s - - [%s] %s" % (self.address_string(), self.log_date_time_string(), fmt % args), flush=True)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Listening on {HOST}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
