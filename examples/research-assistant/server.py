"""Research Assistant MCP server built with upjack + FastMCP.

Manages research topics, sources, notes, and reports.
"""

from pathlib import Path

from upjack.server import create_server

manifest = Path(__file__).parent / "manifest.json"
mcp = create_server(manifest, root="./workspace")

if __name__ == "__main__":
    mcp.run()
