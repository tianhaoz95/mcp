import unittest
import json
import os
import subprocess
import shutil
from datetime import datetime

class TestDeviceMCP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_db_dir = os.path.expanduser("~/.cache/device-mcp-test")
        cls.test_db_path = os.path.join(cls.test_db_dir, "device_state.db")
        if os.path.exists(cls.test_db_dir):
            shutil.rmtree(cls.test_db_dir)

    def run_server_command(self, request, mock_devices=None):
        # We'll mock the flutter command by overriding the server script's subprocess call or 
        # just providing a controlled environment.
        # For simplicity in this test, we'll manually inject some data into the DB first
        # and skip the sync part by providing an empty list if flutter is not found.
        env = {
            **os.environ,
            "DEVICE_MCP_DB_PATH": self.test_db_path
        }
        process = subprocess.Popen(
            ["python3", "./tools/device-coordination/device_mcp_server.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        stdout, stderr = process.communicate(input=json.dumps(request) + "\n")
        return json.loads(stdout)

    def test_initialize(self):
        req = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
        res = self.run_server_command(req)
        self.assertIn("capabilities", res["result"])

    def test_acquire_wait_release(self):
        # 1. Manually inject a device into the test DB
        import sqlite3
        os.makedirs(os.path.dirname(self.test_db_path), exist_ok=True)
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS device_inventory (device_id TEXT PRIMARY KEY, name TEXT, platform TEXT, status TEXT DEFAULT 'available', locked_by_pid INTEGER, expires_at TEXT)")
        cursor.execute("INSERT OR REPLACE INTO device_inventory (device_id, name, platform, status) VALUES ('test_id', 'Test Phone', 'ios', 'available')")
        conn.commit()
        conn.close()

        # 2. Acquire the device
        # Note: Since the server runs 'flutter devices' which will likely fail or return nothing in this env,
        # we have a slight issue. The server only returns devices that are 'current'.
        # I will modify the server to allow skipping the sync if it fails.
        # Wait, the current server implementation DOES return empty if flutter fails.
        
        # Actually, let's mock the 'flutter' command for the test.
        # We'll create a dummy 'flutter' script in the path.
        bin_dir = os.path.join(self.test_db_dir, "bin")
        os.makedirs(bin_dir, exist_ok=True)
        flutter_mock = os.path.join(bin_dir, "flutter")
        with open(flutter_mock, "w") as f:
            f.write("#!/bin/sh\necho '[{\"id\":\"test_id\",\"name\":\"Test Phone\",\"targetPlatform\":\"ios\"}]'")
        os.chmod(flutter_mock, 0o755)
        
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = bin_dir + ":" + old_path
        
        try:
            req_acquire = {
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": "acquire_device", "arguments": {"platform": "ios"}}
            }
            res_acquire = self.run_server_command(req_acquire)
            content = json.loads(res_acquire["result"]["content"][0]["text"])
            self.assertEqual(content["status"], "granted")
            self.assertEqual(content["device_id"], "test_id")

            # 3. Try to acquire again (should wait)
            res_wait = self.run_server_command(req_acquire)
            content_wait = json.loads(res_wait["result"]["content"][0]["text"])
            self.assertEqual(content_wait["status"], "wait")

            # 4. Release
            req_release = {
                "jsonrpc": "2.0", "id": 4, "method": "tools/call",
                "params": {"name": "release_device", "arguments": {"device_id": "test_id"}}
            }
            res_release = self.run_server_command(req_release)
            self.assertTrue(json.loads(res_release["result"]["content"][0]["text"])["success"])
        finally:
            os.environ["PATH"] = old_path

if __name__ == "__main__":
    unittest.main()
