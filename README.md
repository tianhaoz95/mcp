# AI Hardware & Device Coordination MCP Servers

A set of zero-dependency MCP servers to coordinate shared hardware usage across multiple agent instances (Gemini CLI, Claude Code, etc.) on a single host.

## Tools Included

- **[GPU Coordination](./tools/gpu-coordination/README.md)**: Manages atomic locks for NVIDIA GPUs.
- **[Device Coordination](./tools/device-coordination/README.md)**: Manages atomic locks for Flutter mobile/web devices.

## Installation

### 🚀 Automated Installation (Gemini CLI)
Install directly from GitHub as a native extension:
```bash
gemini extensions install https://github.com/tianhaoz95/mcp
```
*This handles cloning and tool registration automatically.*

### 🛠️ Manual Installation (Claude Code & others)
1. **Clone the repository:**
   ```bash
   git clone https://github.com/tianhaoz95/mcp
   cd mcp
   ```
2. **Register the tools:**
   - Refer to the individual tool READMEs for specific `mcp add` commands:
     - [GPU Coordination Setup](./tools/gpu-coordination/README.md#usage)
     - [Device Coordination Setup](./tools/device-coordination/README.md#usage)

## Features
- **Zero Dependency**: Only requires Python 3 (standard library).
- **Atomic Locking**: Prevents resource contention between agents.
- **Shared State**: All agents on the same host share the same inventory.
- **Auto-Release**: Prevents deadlocks if an agent crashes.
