"""Todo List MCP server built with upjack + FastMCP."""

from pathlib import Path

from upjack.server import create_server

manifest = Path(__file__).parent / "manifest.json"
mcp = create_server(manifest)

if __name__ == "__main__":
    mcp.run()
