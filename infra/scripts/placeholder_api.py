"""Local infrastructure readiness placeholder until the real API is merged."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/health":
            self.respond(200, {"status": "placeholder", "data_quality": "approximated"})
        else:
            self.respond(
                503,
                {
                    "type": "about:blank",
                    "title": "API not implemented",
                    "status": 503,
                    "detail": "This service only checks infrastructure readiness.",
                    "data_quality": "approximated",
                },
            )

    def do_POST(self) -> None:
        # Drain without parsing/persisting the body before closing the connection.
        # An unread POST body can reset localhost sockets on Windows.
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if not 0 <= length <= 1024 * 1024:
            self.respond(
                400,
                {
                    "type": "about:blank",
                    "title": "Invalid request body",
                    "status": 400,
                    "data_quality": "approximated",
                },
            )
            return
        self.connection.settimeout(3)
        try:
            while length:
                chunk = self.rfile.read(min(length, 65536))
                if not chunk:
                    return
                length -= len(chunk)
        except OSError:
            return
        self.do_GET()

    def respond(self, status: int, content: dict[str, object]) -> None:
        body = json.dumps(content).encode()
        self.send_response(status)
        self.send_header(
            "Content-Type",
            "application/json" if status == 200 else "application/problem+json",
        )
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        # Do not log request paths, query strings, or coordinates.
        pass


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
