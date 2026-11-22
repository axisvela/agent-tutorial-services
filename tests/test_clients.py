import os
import http.client
import json
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "service"))
from orders import OrderServer


@unittest.skipUnless(os.getenv("PRAXO_CORE_REPO"), "Set PRAXO_CORE_REPO to run native clients")
class ClientTests(unittest.TestCase):
    def test_native_clients(self):
        core = Path(os.environ["PRAXO_CORE_REPO"])
        with OrderServer(("127.0.0.1", 0)) as server:
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                env = os.environ.copy()
                env["DEMO_BASE_URL"] = f"http://127.0.0.1:{server.server_port}"
                env["PYTHONPATH"] = os.getenv("PRAXO_PYTHON_PACKAGE_PATH", str(core / "language/python"))
                commands = {
                    "python": [sys.executable, str(core / "language/python/Tutorial/order-review/app.py"),
                               "--base-url", env["DEMO_BASE_URL"]],
                    "typescript": ["node", str(core / "language/typescript/Tutorial/order-review/app.js")],
                }
                if os.getenv("PRAXO_JAVA_CLASSPATH"):
                    commands["java"] = [os.getenv("JAVA", "java"), "-cp",
                                        os.environ["PRAXO_JAVA_CLASSPATH"], "tutorial.OrderReview"]
                if os.getenv("PRAXO_DOTNET_DLL"):
                    commands["csharp"] = [os.getenv("DOTNET", "dotnet"), os.environ["PRAXO_DOTNET_DLL"]]
                for language, command in commands.items():
                    with self.subTest(language=language):
                        result = subprocess.run(command, env=env, capture_output=True, text=True,
                                                stdin=subprocess.DEVNULL, timeout=20)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertIn("draft_only", result.stdout)
                        before = len(server.drafts)
                        policy_command = command + ["--order", "order-200"] if language == "python" else command
                        policy_denied = subprocess.run(
                            policy_command, env=dict(env, DEMO_ORDER="order-200"), capture_output=True,
                            text=True, stdin=subprocess.DEVNULL, timeout=20)
                        self.assertNotEqual(policy_denied.returncode, 0)
                        self.assertEqual(len(server.drafts), before)
                        denied_env = dict(env, DEMO_TOKEN="demo-b-token")
                        denied = subprocess.run(command, env=denied_env, capture_output=True, text=True,
                                                stdin=subprocess.DEVNULL, timeout=20)
                        self.assertNotEqual(denied.returncode, 0)
                        self.assertEqual(len(server.drafts), before)
                        server.dependency_available = False
                        server.drafts.clear()
                        failed = subprocess.run(command, env=env, capture_output=True, text=True,
                                                stdin=subprocess.DEVNULL, timeout=20)
                        self.assertNotEqual(failed.returncode, 0)
                        self.assertEqual(len(server.drafts), 0)
                        server.dependency_available = True
            finally:
                server.shutdown()
                thread.join()

    @unittest.skipUnless(os.getenv("PRAXO_DOTNET_DLL"), "Set PRAXO_DOTNET_DLL to test ASP.NET Core")
    def test_csharp_web(self):
        with OrderServer(("127.0.0.1", 0)) as server:
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            process = None
            try:
                with socket.socket() as reservation:
                    reservation.bind(("127.0.0.1", 0))
                    port = reservation.getsockname()[1]
                env = dict(os.environ, DEMO_BASE_URL=f"http://127.0.0.1:{server.server_port}",
                           DEMO_WEB_URL=f"http://127.0.0.1:{port}", DEMO_TOKEN="demo-a-token")
                process = subprocess.Popen(
                    [os.getenv("DOTNET", "dotnet"), os.environ["PRAXO_DOTNET_DLL"], "--serve"],
                    env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

                def request(method, path, token=None):
                    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=6)
                    try:
                        headers = {"Authorization": f"Bearer {token}"} if token else {}
                        connection.request(method, path, headers=headers)
                        response = connection.getresponse()
                        return response.status, json.loads(response.read())
                    finally:
                        connection.close()

                deadline = time.monotonic() + 15
                while True:
                    if process.poll() is not None:
                        self.fail(f"Web process exited: {process.communicate(timeout=2)[1]!r}")
                    try:
                        status, _ = request("GET", "/healthz")
                        if status == 200:
                            break
                    except OSError:
                        pass
                    if time.monotonic() >= deadline:
                        self.fail("ASP.NET Core readiness timed out")
                    time.sleep(0.05)
                self.assertEqual(request("POST", "/review/order-100")[0], 401)
                self.assertEqual(len(server.drafts), 0)
                status, result = request("POST", "/review/order-100", "demo-a-token")
                self.assertEqual(status, 200)
                self.assertEqual(result["draft"]["status"], "draft_only")
                self.assertEqual(len(server.drafts), 1)
                self.assertEqual(request("POST", "/review/order-100", "demo-a-token")[1], result)
                self.assertEqual(len(server.drafts), 1)
                server.drafts.clear()
                server.dependency_available = False
                self.assertEqual(request("POST", "/review/order-100", "demo-a-token")[0], 503)
                self.assertEqual(len(server.drafts), 0)
            finally:
                if process is not None:
                    if process.poll() is None:
                        process.terminate()
                    try:
                        process.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.communicate(timeout=5)
                server.shutdown()
                thread.join()
