# GPU Coordination MCP Server

A zero-dependency MCP server to coordinate GPU usage across multiple agent instances (Gemini CLI, Claude Code, etc.) on a single host.

## Features

- **Atomic Locking**: Uses SQLite transactions to ensure exclusive GPU ID allocation.
- **Shared State**: All agents on the same host share the same GPU inventory state.
- **Auto-Release**: Automatically releases locks after a timeout to prevent deadlocks from crashed agents.
- **Zero Dependency**: Requires only a standard Python 3 installation.

## Installation

### 🚀 Automated Installation (Gemini CLI)
If you are using **Gemini CLI**, you can install this directly from GitHub as a native extension. This will automatically clone the repository to your extensions directory and register the MCP server:
```bash
gemini extensions install https://github.com/tianhaoz95/mcp
```
*No further configuration is required. The tools will be available immediately.*

### 🛠️ Manual Installation (Claude Code & others)
For **Claude Code** or if you prefer to manage it manually in Gemini CLI, follow these steps:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/tianhaoz95/mcp
   cd mcp
   ```

2. **Register the MCP server:**

   **For Claude Code:**
   Simply run `claude` inside the cloned directory. Claude Code will automatically detect the `.mcp.json` file and ask for your permission to load the `gpu-coordination` tools.

   **For Gemini CLI (Manual):**
   ```bash
   gemini mcp add gpu-coordination python3 $(pwd)/tools/gpu-coordination/gpu_mcp_server.py --env GPU_COUNT=8
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
cd tools/gpu-coordination
python3 test_gpu_mcp.py
```

To manually test the server using `mcp-get`:

```bash
# List tools
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python3 tools/gpu-coordination/gpu_mcp_server.py

# Acquire 2 GPUs
echo '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"acquire_gpus","arguments":{"count":2}}}' | python3 tools/gpu-coordination/gpu_mcp_server.py
```
