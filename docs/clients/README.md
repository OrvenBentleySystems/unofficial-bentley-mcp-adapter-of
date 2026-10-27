# Client configuration samples

Copy the block that matches your client. Stdio needs nothing installed or
running ahead of time; HTTP requires `pwsh scripts\\start-bentley.ps1` first.

| File | For |
|---|---|
| `claude-desktop.json` | Claude Desktop (`%APPDATA%\\Claude\\claude_desktop_config.json`) |
| `vscode-copilot.json` | VS Code / Copilot (`.vscode\\mcp.json` or user `mcp.json`) |
| `http-client.json` | Cursor and any streamable-HTTP MCP client |

After editing Claude Desktop's config, fully quit and restart it.
MicroStation must be running with a DGN open before the tools can do anything.
