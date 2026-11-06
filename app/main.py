"""Quickstart service: a web page that shows the config Pontem gave it.

GREETING comes from the `quickstart` config namespace. The Pontem daemon
projects it into the container's environment and restarts the stack when the
value changes. Each process start gets a fresh `boot_id`, so the page (and the
quickstart skill) can tell a restart happened and show the new value landing.

The device panel shows this device as Pontem sees it. ADMIN_URL, the
organization's admin URL (e.g. https://pontem.acme.com/admin/o/acme), names the
control plane, and API_KEY is a service-account key with devices:read that
arrives through a secret-backed namespace key. The server calls the device
endpoint itself and hands the page only the fields the panel shows, so the key
never leaves the container.

Routes:
  /             the page
  /static/...   its CSS, JS and icon
  /config.json  greeting and process identity, polled by the page and `pontem curl`
  /device.json  this device from the Pontem API, for the device panel
  /health       compose healthcheck
"""

import html
import json
import os
import signal
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

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

ADMIN_URL = os.environ.get("ADMIN_URL", "")
ADMIN_URL_OK = ADMIN_URL.startswith(("https://", "http://"))

STATE = {
    "greeting": os.environ.get("GREETING", "Hello World!"),
    "device_id": os.environ["PONTEM_DEVICE_ID"],
    "version": os.environ.get("QUICKSTART_VERSION", ""),
    "package_version": os.environ.get("PONTEM_PACKAGE_VERSION", ""),
    "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "boot_id": uuid.uuid4().hex[:12],
    "device_url": f"{ADMIN_URL.rstrip('/')}/devices/{os.environ['PONTEM_DEVICE_ID']}"
    if ADMIN_URL_OK
    else "",
}

pontem.init(service_name="quickstart")
log = pontem.logger
metrics = pontem.metrics


class DeviceSource:
    """This device from the Pontem API, fetched at most every CACHE_SECONDS.

    Devices heartbeat about every 30 seconds, so polling faster gains nothing.
    `get()` always returns a dict for the page: `ok` with the device, or `ok:
    false` with an error the page shows. After a failed fetch the last good
    reading is kept and marked stale.
    """

    CACHE_SECONDS = 10
    TIMEOUT_SECONDS = 5
    HEARTBEAT_SECTIONS = ("system", "resources", "gpu", "link")

    def __init__(self, admin_url: str, api_key: str, tenant_id: str, device_id: str):
        self._missing = (
            "ADMIN_URL isn't set, so the page doesn't know which Pontem to ask."
            if not ADMIN_URL_OK
            else "API_KEY isn't set, so the page can't call the Pontem API."
            if not api_key
            else "PONTEM_TENANT_ID isn't set."
            if not tenant_id
            else None
        )
        parts = urlsplit(admin_url)
        self._url = f"{parts.scheme}://{parts.netloc}/tenant-api/devices/{device_id}"
        self._headers = {"X-API-Key": api_key, "X-Tenant-Id": tenant_id, "Accept": "application/json"}
        self._lock = threading.Lock()
        self._result: dict = {}
        self._fetched_at = 0.0
        self._last_good: dict | None = None

    def get(self) -> dict:
        if self._missing:
            return {"ok": False, "error": self._missing}
        with self._lock:
            if time.monotonic() - self._fetched_at >= self.CACHE_SECONDS:
                self._result = self._fetch()
                self._fetched_at = time.monotonic()
            return self._result

    def _fetch(self) -> dict:
        request = urllib.request.Request(self._url, headers=self._headers)
        try:
            with urllib.request.urlopen(request, timeout=self.TIMEOUT_SECONDS) as resp:
                device = json.load(resp)
        except urllib.error.HTTPError as err:
            error = (
                f"The Pontem API refused the key (HTTP {err.code}). It needs devices:read."
                if err.code in (401, 403)
                else f"The Pontem API returned HTTP {err.code}."
            )
        except (urllib.error.URLError, OSError) as err:
            error = f"Can't reach the Pontem API: {getattr(err, 'reason', err)}"
        except ValueError:
            error = "The Pontem API returned a response that isn't JSON."
        else:
            self._last_good = self._project(device)
            return {"ok": True, "device": self._last_good}
        log.warn("device fetch failed", error=error)
        if self._last_good:
            return {"ok": True, "stale": True, "error": error, "device": self._last_good}
        return {"ok": False, "error": error}

    def _project(self, device: dict) -> dict:
        heartbeat = device.get("last_heartbeat") or {}
        return {
            "name": device.get("name"),
            "runtime_status": device.get("runtime_status"),
            "sync_status": device.get("sync_status"),
            "labels": device.get("labels") or {},
            "last_heartbeat_at": device.get("last_heartbeat_at"),
            "daemon_version": (heartbeat.get("daemon") or {}).get("version"),
            **{key: heartbeat.get(key) or {} for key in self.HEARTBEAT_SECTIONS},
        }


DEVICE = DeviceSource(
    ADMIN_URL,
    os.environ.get("API_KEY", ""),
    os.environ.get("PONTEM_TENANT_ID", ""),
    STATE["device_id"],
)


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
                self._json(DEVICE.get())
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
