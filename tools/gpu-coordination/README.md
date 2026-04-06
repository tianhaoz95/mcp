# GPU Coordination MCP Server

A zero-dependency MCP server to coordinate GPU usage across multiple agent instances on a single host.

## Features
- **Atomic Locking**: Uses SQLite transactions to ensure exclusive GPU ID allocation.
- **Shared State**: All agents on the same host share the same GPU inventory state.
- **Auto-Detection**: Automatically detects the number of GPUs using `nvidia-smi` or `/dev/nvidia*`.
- **Auto-Release**: Automatically releases locks after a timeout to prevent deadlocks from crashed agents.

## Usage

### Gemini CLI
Add via `gemini mcp add`:
```bash
gemini mcp add gpu-coordination python3 tools/gpu-coordination/gpu_mcp_server.py --env GPU_COUNT=8
```

### Claude Code
Add via `claude mcp add`:
```bash
claude mcp add gpu-coordination python3 tools/gpu-coordination/gpu_mcp_server.py --env GPU_COUNT=8 --scope user
```

## Tools

### `list_gpus`
Returns the status of all GPUs.

### `acquire_gpus`
Arguments:
- `count` (integer): Number of GPUs to acquire.
- `timeout_seconds` (integer, optional): How long to hold the lock (default: 3600).

### `release_gpus`
Arguments:
- `gpu_ids` (array of integers): The IDs to release.

## Testing
```bash
python3 tools/gpu-coordination/test_gpu_mcp.py
```
