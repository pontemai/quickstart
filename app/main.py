"""Quickstart service: a web page that shows the config Pontem gave it.

GREETING comes from the `quickstart` config namespace. The Pontem daemon
projects it into the container's environment and restarts the stack when the
value changes. Each process start gets a fresh `boot_id`, so the page (and the
quickstart skill) can tell a restart happened and show the new value landing.

The device panel reads the host's /proc, which containers share. The compose
file adds `uts: host` for the real hostname and mounts /etc/os-release for the
OS name; without them those fields fall back to the container's own.

Routes:
  /             the page
  /static/...   its CSS, JS and icon
  /config.json  greeting and process identity, polled by the page and `pontem curl`
  /device.json  live host stats for the device panel
  /health       compose healthcheck
"""

import glob
import html
import json
import os
import platform
import signal
import socket
import sys
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# init() requires a device ID. On a managed device the daemon injects one;
# the fallback keeps `docker run` working for local smoke tests.
os.environ.setdefault("PONTEM_DEVICE_ID", "local-dev")

import pontem  # noqa: E402

LISTEN_PORT = 8080
STATIC_DIR = Path(__file__).parent / "static"
STATIC_TYPES = {
    "app.css": "text/css; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
    "pontem.css": "text/css; charset=utf-8",
    "icon.svg": "image/svg+xml",
}
STATIC = {name: (STATIC_DIR / name).read_bytes() for name in STATIC_TYPES}
INDEX = (STATIC_DIR / "index.html").read_text()

STATE = {
    "greeting": os.environ.get("GREETING", "Hello World!"),
    "device_id": os.environ["PONTEM_DEVICE_ID"],
    "package_version": os.environ.get("PONTEM_PACKAGE_VERSION", ""),
    "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "boot_id": uuid.uuid4().hex[:12],
}

pontem.init(service_name="quickstart")
log = pontem.logger
metrics = pontem.metrics


def read(path: str) -> str | None:
    try:
        return Path(path).read_text()
    except OSError:
        return None


def os_name() -> str | None:
    text = read("/host/etc/os-release") or ""
    for line in text.splitlines():
        if line.startswith("PRETTY_NAME="):
            return line.split("=", 1)[1].strip().strip('"')
    return None


def cpu_model() -> str | None:
    # x86 reports "model name"; Raspberry Pi reports the board as "Model".
    found = None
    for line in (read("/proc/cpuinfo") or "").splitlines():
        key, _, value = line.partition(":")
        key = key.strip().lower()
        if key == "model" and not value.strip().isdigit():
            return value.strip()
        if key == "model name" and found is None:
            found = value.strip()
    return found


def meminfo() -> dict[str, int]:
    fields = {}
    for line in (read("/proc/meminfo") or "").splitlines():
        key, _, value = line.partition(":")
        if key in ("MemTotal", "MemAvailable"):
            fields[key] = int(value.split()[0]) * 1024
    return fields


def temperature_c() -> float | None:
    temps = []
    for zone in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
        raw = read(zone)
        if raw and raw.strip().lstrip("-").isdigit():
            temps.append(int(raw) / 1000)
    return round(max(temps), 1) if temps else None


def device_stats() -> dict:
    mem = meminfo()
    load = (read("/proc/loadavg") or "").split()
    uptime = (read("/proc/uptime") or "").split()
    return {
        "hostname": socket.gethostname(),
        "os": os_name(),
        "arch": platform.machine(),
        "kernel": platform.release(),
        "cpu": cpu_model(),
        "cores": os.cpu_count(),
        "mem_total": mem.get("MemTotal"),
        "mem_available": mem.get("MemAvailable"),
        "load1": float(load[0]) if load else None,
        "uptime_s": int(float(uptime[0])) if uptime else None,
        "temp_c": temperature_c(),
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        with metrics.timer("request.duration"):
            metrics.count("requests")
            path = self.path.split("?", 1)[0]
            if path == "/health":
                self._send(200, "text/plain; charset=utf-8", b"ok\n")
            elif path == "/config.json":
                self._json(STATE)
            elif path == "/device.json":
                self._json(device_stats())
            elif path.startswith("/static/") and path[8:] in STATIC:
                name = path[8:]
                self._send(200, STATIC_TYPES[name], STATIC[name])
            elif path == "/":
                self._send(200, "text/html; charset=utf-8", self._page())
                log.info("served page", greeting=STATE["greeting"])
            else:
                self._send(404, "text/plain; charset=utf-8", b"not found\n")

    def _page(self) -> bytes:
        # The app proxy adds X-Pontem-User-Email on browser requests it has
        # authenticated; it strips any copy the caller sends.
        viewer = self.headers.get("X-Pontem-User-Email", "")
        boot = {**STATE, "viewer": viewer}
        page = INDEX.replace("{{greeting}}", html.escape(STATE["greeting"]))
        # json.dumps does not escape "</", which would end the script tag early.
        page = page.replace("{{boot}}", json.dumps(boot).replace("</", "<\\/"))
        return page.encode()

    def _json(self, body: dict) -> None:
        payload = json.dumps(body, indent=2).encode() + b"\n"
        self._send(200, "application/json", payload, cache=False)

    def _send(self, status: int, content_type: str, body: bytes, cache: bool = True) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if not cache:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        # The SDK logs requests that matter; skip the stdlib access log.
        pass


def main() -> None:
    # Python as PID 1 ignores SIGTERM, so without this a config restart waits
    # out Docker's 10-second stop timeout before the new value can start.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    log.info("service starting", port=LISTEN_PORT, **STATE)
    server = ThreadingHTTPServer(("", LISTEN_PORT), Handler)
    try:
        server.serve_forever()
    finally:
        pontem.shutdown()


if __name__ == "__main__":
    main()
