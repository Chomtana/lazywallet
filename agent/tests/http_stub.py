import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


def serve(routes, request_headers: list | None = None):
    """Local HTTP stand-in: path prefix → (status, body bytes, headers) or a list of those served in turn.
    Returns (server, seen request paths). Pass `request_headers` (a list) to also collect each request's headers."""
    seen: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.path)
            if request_headers is not None:
                request_headers.append(dict(self.headers))
            match = next((k for k in sorted(routes, key=len, reverse=True) if self.path.startswith(k)), None)
            reply = routes.get(match, (404, b"{}", {}))
            if isinstance(reply, list):
                reply = reply.pop(0) if len(reply) > 1 else reply[0]
            status, body, headers = reply
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for k, v in headers.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, seen
