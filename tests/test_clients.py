import os
from pathlib import Path
import subprocess
import sys
import threading
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
