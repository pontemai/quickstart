"""Quickstart service: a web page that shows the config Pontem gave it.

GREETING comes from the `quickstart` config namespace. The Pontem daemon
projects it into the container's environment and restarts the stack when the
value changes, so `started_at` moves forward on every config change. That is
how the quickstart skill shows a change landing.

Routes:
  /             HTML page for the browser link
  /config.json  the same values as JSON, for `pontem curl`
  /health       compose healthcheck
"""

import html
import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# init() requires a device ID. On a managed device the daemon injects one;
# the fallback keeps `docker run` working for local smoke tests.
os.environ.setdefault("PONTEM_DEVICE_ID", "local-dev")

import pontem  # noqa: E402

LISTEN_PORT = 8080

STATE = {
    "greeting": os.environ.get("GREETING", "Hello from Pontem"),
    "device_id": os.environ["PONTEM_DEVICE_ID"],
    "package_version": os.environ.get("PONTEM_PACKAGE_VERSION", ""),
    "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
}

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pontem Quickstart</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ margin: 0; min-height: 100vh; display: grid; place-items: center;
         font-family: system-ui, sans-serif; background: Canvas; color: CanvasText; }}
  main {{ padding: 24px; max-width: 640px; text-align: center; }}
  h1 {{ font-size: clamp(2rem, 6vw, 3.5rem); margin: 0 0 24px; overflow-wrap: anywhere; }}
  dl {{ display: grid; grid-template-columns: auto auto; gap: 4px 16px;
       justify-content: center; margin: 0; opacity: 0.7; font-size: 0.9rem; }}
  dt {{ text-align: right; }}
  dd {{ margin: 0; text-align: left; font-family: ui-monospace, monospace; }}
</style>
</head>
<body>
<main>
  <h1>{greeting}</h1>
  <dl>
    <dt>Device</dt><dd>{device_id}</dd>
    <dt>Package version</dt><dd>{package_version}</dd>
    <dt>Started</dt><dd>{started_at}</dd>
  </dl>
</main>
</body>
</html>
"""

pontem.init(service_name="quickstart")
log = pontem.logger
metrics = pontem.metrics


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        with metrics.timer("request.duration"):
            metrics.count("requests")
            path = self.path.split("?", 1)[0]
            if path == "/health":
                self._send(200, "text/plain; charset=utf-8", b"ok\n")
            elif path == "/config.json":
                self._send(200, "application/json", json.dumps(STATE, indent=2).encode() + b"\n")
            elif path == "/":
                escaped = {k: html.escape(v) for k, v in STATE.items()}
                self._send(200, "text/html; charset=utf-8", PAGE.format(**escaped).encode())
                log.info("served page", greeting=STATE["greeting"])
            else:
                self._send(404, "text/plain; charset=utf-8", b"not found\n")

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        # The SDK logs requests that matter; skip the stdlib access log.
        pass


def main() -> None:
    log.info("service starting", port=LISTEN_PORT, **STATE)
    server = ThreadingHTTPServer(("", LISTEN_PORT), Handler)
    try:
        server.serve_forever()
    finally:
        pontem.shutdown()


if __name__ == "__main__":
    main()
