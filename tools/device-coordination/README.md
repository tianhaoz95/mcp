# Device Coordination MCP Server

A zero-dependency MCP server to coordinate access to connected mobile/web devices via **Flutter**.

## Features
- **Live Sync**: Automatically discovers devices using `flutter devices --machine`.
- **Atomic Locking**: Prevents multiple agents from deploying to the same device simultaneously.
- **Shared State**: All agents on the same host share the same device inventory state.

## Usage

### Gemini CLI
Add via `gemini mcp add`:
```bash
gemini mcp add device-coordination python3 tools/device-coordination/device_mcp_server.py
```

### Claude Code
Add via `claude mcp add`:
```bash
claude mcp add device-coordination python3 tools/device-coordination/device_mcp_server.py --scope user
```

## Tools

### `list_devices`
Returns the status of all connected Flutter devices.

### `acquire_device`
Arguments:
- `device_id` (string, optional): Specific ID to lock.
- `platform` (string, optional): Lock any device of this type (e.g., "ios").
- `timeout_seconds` (integer, optional): Lock duration.

### `release_device`
Arguments:
- `device_id` (string): The ID to release.

## Testing
```bash
python3 tools/device-coordination/test_device_mcp.py
```
