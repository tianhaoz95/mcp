# Design Document: Device Coordination MCP Server

## 1. Overview
When multiple agents (or multiple instances of the same agent) are working on Flutter/mobile projects, they often compete for the same physical or emulated devices. Running `flutter run` simultaneously on the same device causes conflicts.

This MCP server provides a centralized coordination mechanism to:
1.  **Discover** connected devices (using `flutter devices`).
2.  **Acquire** exclusive locks on a specific device (by ID).
3.  **Release** devices once the task is complete.

## 2. Architecture
Following the zero-dependency model, the server is built in **Python 3** using only the standard library.

### 2.1 State Management
- **SQLite Database**: Stored at `~/.cache/device-mcp/device_state.db`.
- **Inventory Sync**: The server periodically (or on-demand) runs `flutter devices --machine` to sync the current physical state with the logical database state.
- **Table: `device_inventory`**
  - `device_id`: String (Unique ID from Flutter)
  - `name`: String (Human-readable name)
  - `platform`: String (android, ios, web, etc.)
  - `status`: String (`available`, `busy`)
  - `locked_by_pid`: Integer
  - `expires_at`: Timestamp

### 2.2 Concurrency & Atomicity
Uses `BEGIN IMMEDIATE` transactions in SQLite to ensure that if two agents try to grab the same iPhone simulator at once, only one succeeds.

## 3. MCP Interface

### 3.1 Tools

#### `list_devices`
Returns the status of all connected devices. Triggers an internal sync with `flutter devices` if the cache is stale.

#### `acquire_device`
Requests a lock on a specific device ID or the "first available" device of a certain platform.
- **Arguments:**
  - `device_id` (string, optional): Specific ID to lock.
  - `platform` (string, optional): Lock any device of this type (e.g., "android").
  - `timeout_seconds` (number, optional): Default 3600.
- **Returns:**
  - `status`: "granted" | "wait"
  - `device_id`: The ID of the locked device.

#### `release_device`
Releases the lock.
- **Arguments:**
  - `device_id` (string): The ID to release.

## 4. Operational Logic
1. Agent calls `acquire_device(platform: "ios")`.
2. Server runs `flutter devices --machine` to find iOS devices.
3. Server checks SQLite for which of those are `available`.
4. Server locks one and returns the ID.
5. Agent runs `flutter run -d <device_id>`.
6. Agent calls `release_device`.
