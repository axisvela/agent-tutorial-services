import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class OrderServer(ThreadingHTTPServer):
    def __init__(self, address):
        super().__init__(address, Handler)
        self.lock = threading.Lock()
        self.drafts = {}
        self.orders = {
            "order-100": {"id": "order-100", "tenant": "demo-a", "status": "delayed", "shipment": "awaiting_carrier"},
            "order-200": {"id": "order-200", "tenant": "demo-b", "status": "shipped", "shipment": "in_transit"},
        }
        self.dependency_available = True


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def reply(self, status, body):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.dispatch(False)

    def do_POST(self):
        self.dispatch(True)

    def dispatch(self, write):
        if not write and self.path == "/healthz":
            return self.reply(200, {"status": "ok", "fixture_version": "1"})
        scopes = {"Bearer demo-a-token": "demo-a", "Bearer demo-b-token": "demo-b"}
        tenant = scopes.get(self.headers.get("Authorization"))
        if tenant is None:
            return self.reply(401, {"error": "unauthenticated"})
        parts = self.path.split("/")
        if len(parts) not in (4, 5) or parts[1:3] != ["v1", "orders"]:
            return self.reply(404, {"error": "not_found"})
        order = self.server.orders.get(parts[3])
        if order is None:
            return self.reply(404, {"error": "not_found"})
        if order["tenant"] != tenant:
            return self.reply(403, {"error": "scope_denied"})
        if not write and len(parts) == 4:
            return self.reply(200, order)
        if not write or len(parts) != 5 or parts[4] != "drafts":
            return self.reply(404, {"error": "not_found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 4096 or self.headers.get("Transfer-Encoding"):
                return self.reply(400, {"error": "invalid_length"})
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict) or set(body) != {"recommendation"}:
                raise ValueError()
            text = body["recommendation"]
            if not isinstance(text, str) or not text.strip() or len(text) > 500:
                raise ValueError()
            key = self.headers.get("Idempotency-Key", "")
            if not key or len(key) > 80:
                raise ValueError()
        except (ValueError, UnicodeError):
            return self.reply(400, {"error": "invalid_request"})
        with self.server.lock:
            identity = (tenant, order["id"], key)
            previous = self.server.drafts.get(identity)
            if previous:
                if previous["recommendation"] != text:
                    return self.reply(409, {"error": "idempotency_conflict"})
                return self.reply(200, previous)
            if not self.server.dependency_available:
                return self.reply(503, {"error": "draft_store_unavailable"})
            draft = {"id": f"draft-{len(self.server.drafts) + 1}", "order_id": order["id"],
                     "recommendation": text, "status": "draft_only"}
            self.server.drafts[identity] = draft
            return self.reply(201, draft)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    with OrderServer(("127.0.0.1", args.port)) as server:
        print(f"Synthetic orders service: http://127.0.0.1:{args.port}", flush=True)
        server.serve_forever()
