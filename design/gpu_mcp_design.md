# Design Document: GPU Coordination MCP Server

## 1. Overview
As coding agents (like Gemini CLI and Claude Code) increasingly perform GPU-intensive tasks (e.g., training models, running local inference, or optimizing CUDA kernels), there is a need for a centralized coordination mechanism to prevent resource contention.

This MCP server provides a standardized interface for agents to:
1.  **Discover** available GPU resources on the host.
2.  **Acquire** exclusive locks on one or more GPUs.
3.  **Release** GPUs once the task is complete.
4.  **Wait/Retry** gracefully when resources are fully utilized.

## 2. Architecture
The server is designed to be **zero-dependency**, requiring only a standard Python 3 installation. It uses the Model Context Protocol (MCP) over standard input/output (stdio).

### 2.1 State Management
To ensure atomicity without requiring an external database (like Postgres or Redis), the server uses **SQLite via Python's built-in `sqlite3` module**. 
- **Storage:** All state is persisted in a single file located at `~/.cache/gpu-mcp/gpu_state.db`. The server will automatically create this directory and initialize the database on first run.
- **Shared State:** By using a fixed path in the user's home directory, multiple agent instances (Claude Code, Gemini CLI, etc.) will naturally point to the same coordination database.
- **No Installation:** No separate database server or `pip` packages are needed.
- **Table: `gpu_inventory`**
  - `id`: Integer (GPU ID, 0-N)
  - `status`: String (`available`, `busy`)
  - `locked_by_pid`: Integer (Process ID of the agent)
  - `expires_at`: Timestamp (ISO 8601)

### 2.2 Concurrency & Atomicity
SQLite's file-level locking ensures that lock acquisitions are atomic. The server uses `BEGIN IMMEDIATE` transactions to prevent race conditions when multiple agents request GPUs simultaneously.

## 3. MCP Interface

### 3.1 Tools

#### `list_gpus`
Returns the current status of all GPUs on the host.
- **Arguments:** None
- **Returns:** An array of GPU objects with their current status and lock information.

#### `acquire_gpus`
Requests a specific number of GPUs.
- **Arguments:**
  - `count` (number): Number of GPUs required.
  - `timeout_seconds` (number, optional): How long the lock should last (default: 3600).
- **Returns:**
  - `status`: "granted" | "wait"
  - `gpu_ids`: Array of integers (if granted)
  - `message`: Helpful text for the agent.

#### `release_gpus`
Releases previously acquired GPUs.
- **Arguments:**
  - `gpu_ids` (number[]): The IDs to release.
- **Returns:**
  - `success`: Boolean

### 3.2 Resources (Optional)
- `gpu://inventory`: A dynamic resource that agents can read to see the real-time status of all GPUs.

## 4. Operational Logic

### 4.1 Acquisition Flow
1. Agent calls `acquire_gpus(count: 4)`.
2. Server opens a transaction.
3. Server checks for `available` GPUs.
4. If `available_count >= count`:
   - Mark `count` GPUs as `busy`.
   - Record Agent ID and expiration time.
   - Commit and return IDs.
5. If `available_count < count`:
   - Rollback and return `status: "wait"`.

### 4.2 Handling Stale Locks
To prevent a "deadlock" if an agent process is killed without calling `release_gpus`, the server will:
- Automatically release GPUs where `expires_at` is in the past during any `acquire_gpus` or `list_gpus` call.
- Provide a `force_release` tool (admin only) if necessary.

## 5. Agent Instructions (System Prompting)
The MCP server will provide a "Prompt" template to instruct agents on the protocol:
> "Before running any GPU-related code (CUDA, PyTorch, etc.), you MUST call the `acquire_gpus` tool. Only use the GPU IDs granted to you (e.g., set `CUDA_VISIBLE_DEVICES`). Once your work is finished, you MUST call `release_gpus` to allow other agents to use the hardware."

## 6. Security & Privacy
- The server runs locally on the host.
- It does not expose sensitive data beyond the host's GPU topology and usage statistics.
- Access is restricted to MCP-compliant clients authorized by the user.
