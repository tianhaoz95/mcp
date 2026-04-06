#!/usr/bin/env python3
import sys
import json
import sqlite3
import os
import subprocess
from datetime import datetime, timedelta

# Configuration
DB_PATH = os.environ.get("DEVICE_MCP_DB_PATH", os.path.expanduser("~/.cache/device-mcp/device_state.db"))

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS device_inventory (
            device_id TEXT PRIMARY KEY,
            name TEXT,
            platform TEXT,
            status TEXT DEFAULT 'available',
            locked_by_pid INTEGER,
            expires_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def sync_devices():
    """Sync the physical devices from `flutter devices --machine` with our DB."""
    try:
        output = subprocess.check_output(["flutter", "devices", "--machine"], stderr=subprocess.DEVNULL, text=True)
        devices = json.loads(output)
    except (subprocess.SubprocessError, FileNotFoundError, json.JSONDecodeError):
        return []

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Get current IDs in DB
    cursor.execute("SELECT device_id FROM device_inventory")
    db_ids = {row[0] for row in cursor.fetchall()}
    current_ids = {d["id"] for d in devices}
    
    # 2. Add new devices
    for d in devices:
        if d["id"] not in db_ids:
            cursor.execute("""
                INSERT INTO device_inventory (device_id, name, platform, status)
                VALUES (?, ?, ?, 'available')
            """, (d["id"], d["name"], d["targetPlatform"]))
    
    # 3. Mark removed devices as gone (optional: for simplicity, we just keep them but list_devices will only return current ones)
    # For now, let's keep the DB as a cache of all ever-seen devices, but only return current ones in list_devices.
    
    conn.commit()
    conn.close()
    return devices

def clean_expired():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        UPDATE device_inventory 
        SET status = 'available', locked_by_pid = NULL, expires_at = NULL 
        WHERE status = 'busy' AND expires_at < ?
    """, (now,))
    conn.commit()
    conn.close()

def list_devices():
    clean_expired()
    current_physical = sync_devices()
    current_ids = {d["id"] for d in current_physical}
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT device_id, name, platform, status, locked_by_pid, expires_at FROM device_inventory")
    
    all_devices = []
    for row in cursor.fetchall():
        # Only return devices that are actually connected right now
        if row[0] in current_ids:
            all_devices.append({
                "id": row[0],
                "name": row[1],
                "platform": row[2],
                "status": row[3],
                "locked_by_pid": row[4],
                "expires_at": row[5]
            })
    conn.close()
    return all_devices

def acquire_device(device_id=None, platform=None, timeout_seconds=3600):
    clean_expired()
    sync_devices()
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute("BEGIN IMMEDIATE")
    cursor = conn.cursor()
    
    try:
        query = "SELECT device_id FROM device_inventory WHERE status = 'available'"
        params = []
        
        if device_id:
            query += " AND device_id = ?"
            params.append(device_id)
        elif platform:
            query += " AND platform LIKE ?"
            params.append(f"%{platform}%")
            
        query += " LIMIT 1"
        cursor.execute(query, params)
        row = cursor.fetchone()
        
        if not row:
            conn.rollback()
            return {"status": "wait", "message": "No available device matches the criteria."}
        
        target_id = row[0]
        expires_at = (datetime.now() + timedelta(seconds=timeout_seconds)).isoformat()
        pid = os.getpid()
        
        cursor.execute("""
            UPDATE device_inventory 
            SET status = 'busy', locked_by_pid = ?, expires_at = ? 
            WHERE device_id = ?
        """, (pid, expires_at, target_id))
        
        conn.commit()
        return {
            "status": "granted", 
            "device_id": target_id, 
            "message": f"Successfully locked device: {target_id}"
        }
    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()

def release_device(device_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE device_inventory 
        SET status = 'available', locked_by_pid = NULL, expires_at = NULL 
        WHERE device_id = ?
    """, (device_id,))
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
                        "list_devices": {"description": "List all connected Flutter devices and their lock status."},
                        "acquire_device": {
                            "description": "MANDATORY: Acquire exclusive lock on a device before running flutter apps.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "device_id": {"type": "string", "description": "Specific device ID to lock."},
                                    "platform": {"type": "string", "description": "Platform type (e.g., ios, android)."},
                                    "timeout_seconds": {"type": "integer", "description": "Lock duration in seconds."}
                                }
                            }
                        },
                        "release_device": {
                            "description": "MANDATORY: Release device lock after work is finished.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "device_id": {"type": "string", "description": "Device ID to release."}
                                },
                                "required": ["device_id"]
                            }
                        }
                    }
                },
                "serverInfo": {"name": "device-coordination-server", "version": "0.1.0"}
            }
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": "list_devices",
                        "description": "Returns the status of all connected Flutter devices. MUST call this to check availability.",
                        "inputSchema": {"type": "object", "properties": {}}
                    },
                    {
                        "name": "acquire_device",
                        "description": "MANDATORY: Requests a lock on a device BEFORE running `flutter run`. Specify `platform` or `device_id`.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "device_id": {"type": "string"},
                                "platform": {"type": "string", "description": "e.g., android, ios, web"},
                                "timeout_seconds": {"type": "integer"}
                            }
                        }
                    },
                    {
                        "name": "release_device",
                        "description": "MANDATORY: Releases a device lock AFTER work finishes.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "device_id": {"type": "string"}
                            },
                            "required": ["device_id"]
                        }
                    }
                ]
            }
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        if tool_name == "list_devices":
            result = list_devices()
        elif tool_name == "acquire_device":
            result = acquire_device(args.get("device_id"), args.get("platform"), args.get("timeout_seconds", 3600))
        elif tool_name == "release_device":
            result = release_device(args.get("device_id"))
        else:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
        }

    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}

def main():
    init_db()
    while True:
        line = sys.stdin.readline()
        if not line: break
        try:
            request = json.loads(line)
            response = handle_request(request)
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
        except Exception as e:
            sys.stderr.write(f"Error: {str(e)}\n")
            sys.stderr.flush()

if __name__ == "__main__":
    main()
