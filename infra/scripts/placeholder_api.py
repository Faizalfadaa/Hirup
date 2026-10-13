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
