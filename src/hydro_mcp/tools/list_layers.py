"""
list_layers tool
-----------------
Registers the hydro_list_layers tool on the MCP server.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..models import Provenance
from ..utils import HydroError, _now_utc, list_layers as _list_layers


def register(mcp: FastMCP) -> None:
    """Register the list_layers tool with the MCP server."""

    @mcp.tool(
        name="hydro_list_layers",
        annotations={
            "title": "List NHDPlus HR Service Layers",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    def list_nhdplus_layers() -> dict[str, Any]:
        """List the layers available in the NHDPlus HR service (id, name, geometry type).

        Use when: You need to discover available layers beyond those wrapped by the
        find_* tools (e.g. NHDPlusCatchment, NHDPlusSink, FlowDirection,
        NHDPlusBoundaryUnit) or to confirm current layer IDs.

        Returns:
        {
            "layers": [{"id": int, "name": str, "geometry_type": str}, ...],
            "provenance": {...}
        }

        Error responses:
        - "Error: NHDPlus HR request failed: ..." -- network or service error
        """
        try:
            return {
                "layers": _list_layers(),
                "provenance": Provenance(retrieved_utc=_now_utc()).to_dict(),
            }
        except HydroError as exc:
            return {"error": f"Error: {exc}"}
