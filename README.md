# GPU Coordination MCP Server

A zero-dependency MCP server to coordinate GPU usage across multiple agent instances (Gemini CLI, Claude Code, etc.) on a single host.

## Features

- **Atomic Locking**: Uses SQLite transactions to ensure exclusive GPU ID allocation.
- **Shared State**: All agents on the same host share the same GPU inventory state.
- **Auto-Release**: Automatically releases locks after a timeout to prevent deadlocks from crashed agents.
- **Zero Dependency**: Requires only a standard Python 3 installation.

## Installation

No installation is required. Just ensure you have Python 3 installed.

## Usage with Gemini CLI

Add the following to your `~/.gemini/config.json` (or equivalent config file):

```json
{
  "mcpServers": {
    "gpu-coordination": {
      "command": "python3",
      "args": ["/path/to/mcp/gpu_mcp_server.py"],
      "env": {
        "GPU_COUNT": "8"
      }
    }
  }
}
```

## Usage with Claude Code

Add the following to your Claude Code configuration:

```json
{
  "mcpServers": {
    "gpu-coordination": {
      "command": "python3",
      "args": ["/path/to/mcp/gpu_mcp_server.py"],
      "env": {
        "GPU_COUNT": "8"
      }
    }
  }
}
```

## Tools

### `list_gpus`
Returns the status of all GPUs.

### `acquire_gpus`
Arguments:
- `count` (integer): Number of GPUs to acquire.
- `timeout_seconds` (integer, optional): How long to hold the lock (default: 3600).

Returns a list of `gpu_ids` if successful, or a `wait` status if resources are unavailable.

### `release_gpus`
Arguments:
- `gpu_ids` (array of integers): The IDs to release.

## How it works

The server maintains a SQLite database at `~/.cache/gpu-mcp/gpu_state.db`. This file serves as the single source of truth for all agents on the host. When an agent requests GPUs, the server uses atomic transactions to mark the IDs as busy.

## Testing

To run the automated tests:

```bash
python3 test_gpu_mcp.py
```

To manually test the server using `mcp-get`:

```bash
# List tools
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python3 gpu_mcp_server.py

# Acquire 2 GPUs
echo '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"acquire_gpus","arguments":{"count":2}}}' | python3 gpu_mcp_server.py
```
