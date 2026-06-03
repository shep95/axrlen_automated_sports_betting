"""HTTP health check for Railway."""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logger = logging.getLogger(__name__)

_last_cycle_at: str | None = None
_last_cycle_count: int = 0


def record_cycle(count: int) -> None:
    global _last_cycle_at, _last_cycle_count
    _last_cycle_at = datetime.now(timezone.utc).isoformat()
    _last_cycle_count = count


class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        logger.debug(format, *args)

    def do_GET(self) -> None:  # noqa: N802
        if self.path not in ("/", "/health"):
            self.send_response(404)
            self.end_headers()
            return

        payload = {
            "status": "ok",
            "service": "axrlen-polymarket-bot",
            "last_cycle_at": _last_cycle_at,
            "last_cycle_markets": _last_cycle_count,
        }
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_health_server(port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health server listening on port %d", port)
    return server
