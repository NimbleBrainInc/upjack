"""CRM MCP server built with upjack + FastMCP.

Demonstrates building a standalone MCP server from an Upjack manifest.
The upjack library handles entity management (CRUD, validation, search).
FastMCP handles the MCP transport layer.
"""

from pathlib import Path

from upjack.server import create_server

manifest = Path(__file__).parent / "manifest.json"
mcp = create_server(manifest, root="./workspace")

# --- Manual wiring (for when you need custom logic) ---
#
# from fastmcp import FastMCP
# from upjack import UpjackApp
#
# app = UpjackApp.from_manifest("manifest.json", root="./workspace")
# mcp = FastMCP("CRM")
#
# @mcp.tool()
# def create_contact(data: dict) -> dict:
#     return app.create_entity("contact", data)
#
# @mcp.tool()
# def list_contacts(status: str = "active", limit: int = 50) -> list[dict]:
#     return app.list_entities("contact", status=status, limit=limit)
#
# ... register tools for each entity type and operation ...

if __name__ == "__main__":
    mcp.run()
