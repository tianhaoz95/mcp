#!/usr/bin/env python3
import sys
import json
import sqlite3
import os
import time
from datetime import datetime, timedelta

# Configuration
DB_PATH = os.environ.get("GPU_MCP_DB_PATH", os.path.expanduser("~/.cache/gpu-mcp/gpu_state.db"))

def detect_gpu_count():
    # 1. Check environment variable override
    if "GPU_COUNT" in os.environ:
        try:
            return int(os.environ["GPU_COUNT"])
        except ValueError:
            pass

    # 2. Try to auto-detect using nvidia-smi (fastest)
    try:
        import subprocess
        output = subprocess.check_output(["nvidia-smi", "-L"], stderr=subprocess.DEVNULL, text=True)
        count = len([line for line in output.splitlines() if line.strip()])
        if count > 0:
            return count
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # 3. Try to count /dev/nvidia* devices (Linux specific)
    try:
        import glob
        nvidia_devs = glob.glob("/dev/nvidia[0-9]*")
        # Filter out management/control nodes, keep only numbered devices
        count = len([d for d in nvidia_devs if d.split("/dev/nvidia")[-1].isdigit()])
        if count > 0:
            return count
    except Exception:
        pass

    # 4. Fallback to default
    return 8

DEFAULT_GPU_COUNT = detect_gpu_count()

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gpu_inventory (
            id INTEGER PRIMARY KEY,
            status TEXT DEFAULT 'available',
            locked_by_pid INTEGER,
            expires_at TEXT
        )
    """)
    # Check if inventory is empty
    cursor.execute("SELECT COUNT(*) FROM gpu_inventory")
    if cursor.fetchone()[0] == 0:
        for i in range(DEFAULT_GPU_COUNT):
            cursor.execute("INSERT INTO gpu_inventory (id, status) VALUES (?, 'available')", (i,))
    conn.commit()
    conn.close()

def clean_expired():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        UPDATE gpu_inventory 
        SET status = 'available', locked_by_pid = NULL, expires_at = NULL 
        WHERE status = 'busy' AND expires_at < ?
    """, (now,))
    conn.commit()
    conn.close()

def list_gpus():
    clean_expired()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, status, locked_by_pid, expires_at FROM gpu_inventory")
    gpus = []
    for row in cursor.fetchall():
        gpus.append({
            "id": row[0],
            "status": row[1],
            "locked_by_pid": row[2],
            "expires_at": row[3]
        })
    conn.close()
    return gpus

def acquire_gpus(count, timeout_seconds=3600):
    clean_expired()
    conn = sqlite3.connect(DB_PATH)
    # Use BEGIN IMMEDIATE to lock the database for writing immediately
    conn.execute("BEGIN IMMEDIATE")
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM gpu_inventory WHERE status = 'available' LIMIT ?", (count,))
        available_ids = [row[0] for row in cursor.fetchall()]
        
        if len(available_ids) < count:
            conn.rollback()
            return {"status": "wait", "message": f"Only {len(available_ids)} GPUs available, requested {count}."}
        
        expires_at = (datetime.now() + timedelta(seconds=timeout_seconds)).isoformat()
        pid = os.getpid()
        
        for gpu_id in available_ids:
            cursor.execute("""
                UPDATE gpu_inventory 
                SET status = 'busy', locked_by_pid = ?, expires_at = ? 
                WHERE id = ?
            """, (pid, expires_at, gpu_id))
        
        conn.commit()
        return {
            "status": "granted", 
            "gpu_ids": available_ids, 
            "message": f"Successfully locked {count} GPUs: {available_ids}"
        }
    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()

def release_gpus(gpu_ids):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    placeholders = ','.join(['?'] * len(gpu_ids))
    cursor.execute(f"""
        UPDATE gpu_inventory 
        SET status = 'available', locked_by_pid = NULL, expires_at = NULL 
        WHERE id IN ({placeholders})
    """, gpu_ids)
    conn.commit()
    conn.close()
    return {"success": True}

def handle_request(request):
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "capabilities": {
                    "tools": {
                        "list_gpus": {
                            "description": "List all GPUs and their status. Mandatory check before acquisition.",
                            "inputSchema": {"type": "object", "properties": {}}
                        },
                        "acquire_gpus": {
                            "description": "MANDATORY: Acquire exclusive locks on GPUs BEFORE any GPU-related work (CUDA, PyTorch, etc.). Only use the IDs granted. Hold time defaults to 1 hour.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "count": {"type": "integer", "description": "Number of GPUs to acquire"},
                                    "timeout_seconds": {"type": "integer", "description": "Seconds before lock expires"}
                                },
                                "required": ["count"]
                            }
                        },
                        "release_gpus": {
                            "description": "MANDATORY: Release GPU locks immediately AFTER GPU-related work finishes to allow other agents to use them.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "gpu_ids": {"type": "array", "items": {"type": "integer"}}
                                },
                                "required": ["gpu_ids"]
                            }
                        }
                    },
                    "prompts": {
                        "list_prompts": {
                            "description": "List GPU coordination instructions",
                            "inputSchema": {"type": "object", "properties": {}}
                        }
                    }
                },
                "serverInfo": {"name": "gpu-coordination-server", "version": "0.1.0"}
            }
        }
    
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": "list_gpus",
                        "description": "Returns the current status of all GPUs on the host. MUST call this to check availability.",
                        "inputSchema": {"type": "object", "properties": {}}
                    },
                    {
                        "name": "acquire_gpus",
                        "description": "MANDATORY: Requests a specific number of GPUs BEFORE any GPU work. Use the IDs granted (e.g., set CUDA_VISIBLE_DEVICES).",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "count": {"type": "integer", "description": "Number of GPUs required."},
                                "timeout_seconds": {"type": "integer", "description": "How long the lock should last (default: 3600)."}
                            },
                            "required": ["count"]
                        }
                    },
                    {
                        "name": "release_gpus",
                        "description": "MANDATORY: Releases previously acquired GPUs AFTER work finishes.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "gpu_ids": {"type": "array", "items": {"type": "integer"}, "description": "The IDs to release."}
                            },
                            "required": ["gpu_ids"]
                        }
                    }
                ]
            }
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        
        if tool_name == "list_gpus":
            result = list_gpus()
        elif tool_name == "acquire_gpus":
            count = tool_args.get("count")
            timeout = tool_args.get("timeout_seconds", 3600)
            result = acquire_gpus(count, timeout)
        elif tool_name == "release_gpus":
            gpu_ids = tool_args.get("gpu_ids")
            result = release_gpus(gpu_ids)
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Method not found: {tool_name}"}
            }
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
            }
        }

    elif method == "prompts/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "prompts": [
                    {
                        "name": "gpu-coordination-instructions",
                        "description": "Instructions for coordinating GPU usage.",
                        "arguments": []
                    }
                ]
            }
        }

    elif method == "prompts/get":
        prompt_name = params.get("name")
        if prompt_name == "gpu-coordination-instructions":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "messages": [
                        {
                            "role": "user",
                            "content": {
                                "type": "text",
                                "text": "Before running any GPU-related code (CUDA, PyTorch, etc.), you MUST call the `acquire_gpus` tool. Only use the GPU IDs granted to you (e.g., set `CUDA_VISIBLE_DEVICES`). Once your work is finished, you MUST call `release_gpus` to allow other agents to use the hardware."
                            }
                        }
                    ]
                }
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Prompt not found: {prompt_name}"}
            }


def main():
    init_db()
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        try:
            request = json.loads(line)
            response = handle_request(request)
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
        except json.JSONDecodeError:
            pass
        except Exception as e:
            sys.stderr.write(f"Error: {str(e)}\n")
            sys.stderr.flush()

if __name__ == "__main__":
    main()
