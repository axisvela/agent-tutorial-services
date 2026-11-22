import http.client
import json
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "service"))
from orders import OrderServer


class OrderTests(unittest.TestCase):
    def setUp(self):
        self.server = OrderServer(("127.0.0.1", 0))
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def request(self, method="GET", order="order-100", body=None, token="demo-a-token", key="case-1"):
        client = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        path = f"/v1/orders/{order}" + ("/drafts" if method == "POST" else "")
        client.request(method, path, json.dumps(body) if body is not None else None,
                       {"Authorization": f"Bearer {token}", "Idempotency-Key": key})
        response = client.getresponse()
        result = response.status, json.loads(response.read())
        client.close()
        return result

    def test_scope_and_authentication(self):
        self.assertEqual(self.request()[0], 200)
        self.assertEqual(self.request(token="invalid")[0], 401)
        self.assertEqual(self.request(order="order-200")[0], 403)
        self.assertEqual(self.request("POST", "order-200", {"recommendation": "review"})[0], 403)
        self.assertEqual(len(self.server.drafts), 0)

    def test_draft_replay_and_conflict(self):
        first = self.request("POST", body={"recommendation": "Contact carrier"})
        replay = self.request("POST", body={"recommendation": "Contact carrier"})
        self.assertEqual((first[0], replay[0]), (201, 200))
        self.assertEqual(first[1], replay[1])
        self.assertEqual(self.request("POST", body={"recommendation": "Refund"})[0], 409)
        self.assertEqual(len(self.server.drafts), 1)
        self.assertEqual(self.server.orders["order-100"]["status"], "delayed")

    def test_invalid_input_and_dependency_failure(self):
        self.assertEqual(self.request("POST", body={"recommendation": 42})[0], 400)
        self.assertEqual(self.request("POST", body={"recommendation": "x" * 5000})[0], 400)
        self.server.dependency_available = False
        self.assertEqual(self.request("POST", body={"recommendation": "review"})[0], 503)
        self.assertEqual(len(self.server.drafts), 0)


if __name__ == "__main__":
    unittest.main()
