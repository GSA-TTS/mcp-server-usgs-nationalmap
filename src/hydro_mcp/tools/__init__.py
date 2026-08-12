from . import (
    count_features,
    find_gages,
    find_water_features,
    find_waterbodies,
    find_waterways,
    identify_watershed,
    list_layers,
)


def register_tools(mcp):
    """Register all tools with the MCP server."""
    find_waterways.register(mcp)
    find_waterbodies.register(mcp)
    find_gages.register(mcp)
    find_water_features.register(mcp)
    identify_watershed.register(mcp)
    count_features.register(mcp)
    list_layers.register(mcp)
