import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from lazyagent.faucet import request_funds


def serve(status: int, body: dict):
    received = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received["path"] = self.path
            received["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            payload = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, received


async def test_returns_summary():
    server, received = serve(200, {"summary": "100 ETH, 10,000 USDC"})
    try:
        url = f"http://127.0.0.1:{server.server_port}"
        assert await request_funds(url, "0xabc") == "100 ETH, 10,000 USDC"
        assert received == {"path": "/fund", "body": {"address": "0xabc"}}
    finally:
        server.shutdown()


async def test_surfaces_faucet_error_detail():
    server, _ = serve(502, {"detail": "Sandbox chain error: boom"})
    try:
        with pytest.raises(RuntimeError, match="Sandbox chain error: boom"):
            await request_funds(f"http://127.0.0.1:{server.server_port}", "0xabc")
    finally:
        server.shutdown()


async def test_unreachable_faucet_raises_connection_error():
    with pytest.raises(ConnectionError):
        await request_funds("http://127.0.0.1:1", "0xabc")
