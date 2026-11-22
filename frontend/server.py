"""
SwasthyaVaani — Frontend Static Server (Python fallback)
Serves frontend/static on port 3000.
"""

from __future__ import annotations

import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = int(os.environ.get("PORT", 3000))
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


class StaticHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), StaticHandler)
    print(f"SwasthyaVaani Frontend server running at http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping frontend server.")
        server.server_close()
