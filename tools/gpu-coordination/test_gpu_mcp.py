import subprocess
import json
import os
import shutil
import unittest
import time

class TestGPUMCP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use a temporary DB for testing
        cls.test_db_dir = os.path.expanduser("~/.cache/gpu-mcp-test")
        cls.test_db_path = os.path.join(cls.test_db_dir, "gpu_state.db")
        if os.path.exists(cls.test_db_dir):
            shutil.rmtree(cls.test_db_dir)
        os.environ["GPU_COUNT"] = "4"
        os.environ["HOME"] = os.path.expanduser("~") # Ensure HOME is set for DB path expansion

    def setUp(self):
        # Override DB_PATH in the server script by mocking environment if needed
        # But our script uses os.path.expanduser("~/.cache/gpu-mcp/gpu_state.db")
        # To make it testable, I'll temporarily swap the DB_PATH in the script or use a mock.
        # For simplicity, I'll just run it and then clean up.
        # Actually, I'll modify the script to allow DB_PATH override via env var.
        pass

    def run_server_command(self, request):
        process = subprocess.Popen(
            ["python3", "./gpu_mcp_server.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={
                **os.environ, 
                "GPU_COUNT": "4",
                "GPU_MCP_DB_PATH": self.test_db_path
            }
        )
        stdout, stderr = process.communicate(input=json.dumps(request) + "\n")
        if stderr:
            print(f"Server Error: {stderr}")
        return json.loads(stdout)

    def test_initialize(self):
        req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        res = self.run_server_command(req)
        self.assertEqual(res["id"], 1)
        self.assertIn("capabilities", res["result"])

    def test_list_gpus(self):
        req = {
            "jsonrpc": "2.0", 
            "id": 2, 
            "method": "tools/call", 
            "params": {"name": "list_gpus", "arguments": {}}
        }
        res = self.run_server_command(req)
        content = json.loads(res["result"]["content"][0]["text"])
        self.assertEqual(len(content), 4)
        for gpu in content:
            self.assertEqual(gpu["status"], "available")

    def test_acquire_and_release(self):
        # 1. Acquire 2 GPUs
        req_acquire = {
            "jsonrpc": "2.0", 
            "id": 3, 
            "method": "tools/call", 
            "params": {"name": "acquire_gpus", "arguments": {"count": 2}}
        }
        res_acquire = self.run_server_command(req_acquire)
        content_acquire = json.loads(res_acquire["result"]["content"][0]["text"])
        self.assertEqual(content_acquire["status"], "granted")
        gpu_ids = content_acquire["gpu_ids"]
        self.assertEqual(len(gpu_ids), 2)

        # 2. List GPUs to verify they are busy
        req_list = {
            "jsonrpc": "2.0", 
            "id": 4, 
            "method": "tools/call", 
            "params": {"name": "list_gpus", "arguments": {}}
        }
        res_list = self.run_server_command(req_list)
        content_list = json.loads(res_list["result"]["content"][0]["text"])
        busy_count = sum(1 for g in content_list if g["status"] == "busy")
        self.assertEqual(busy_count, 2)

        # 3. Release GPUs
        req_release = {
            "jsonrpc": "2.0", 
            "id": 5, 
            "method": "tools/call", 
            "params": {"name": "release_gpus", "arguments": {"gpu_ids": gpu_ids}}
        }
        res_release = self.run_server_command(req_release)
        content_release = json.loads(res_release["result"]["content"][0]["text"])
        self.assertTrue(content_release["success"])

        # 4. Verify they are available again
        res_list_2 = self.run_server_command(req_list)
        content_list_2 = json.loads(res_list_2["result"]["content"][0]["text"])
        busy_count_2 = sum(1 for g in content_list_2 if g["status"] == "busy")
        self.assertEqual(busy_count_2, 0)

    def test_wait_when_full(self):
        # 1. Acquire all 4 GPUs
        req_acquire_all = {
            "jsonrpc": "2.0", 
            "id": 6, 
            "method": "tools/call", 
            "params": {"name": "acquire_gpus", "arguments": {"count": 4}}
        }
        self.run_server_command(req_acquire_all)

        # 2. Try to acquire 1 more
        req_acquire_more = {
            "jsonrpc": "2.0", 
            "id": 7, 
            "method": "tools/call", 
            "params": {"name": "acquire_gpus", "arguments": {"count": 1}}
        }
        res_more = self.run_server_command(req_acquire_more)
        content_more = json.loads(res_more["result"]["content"][0]["text"])
        self.assertEqual(content_more["status"], "wait")

if __name__ == "__main__":
    unittest.main()
