import os

from dotenv import load_dotenv
from fastmcp import FastMCP

from hydro_mcp.tools import register_tools
from hydro_mcp.routes import register_routes

load_dotenv()  # loads .env before any code reads env vars

# Initialize FastMCP server
mcp = FastMCP(
    "hydro_mcp",
    instructions=(
        "Wraps the USGS NHDPlus High Resolution (NHDPlus HR) ArcGIS REST MapServer so an "
        "LLM can query official U.S. hydrography — streams, rivers, lakes, gages, water "
        "features, and watershed boundaries — for a point or arbitrary GeoJSON geometry.\n\n"
        "TOOL SELECTION GUIDE:\n"
        "- What river/stream is here, or crosses this area? -> hydro_find_waterways "
        "(streams/rivers/canals with stream order, drainage area, slope, elevation, and modeled flow)\n"
        "- Lakes, ponds, reservoirs, swamps, or wide-river/bay polygons here? -> hydro_find_waterbodies\n"
        "- Stream gages in this area (with NWIS linkage / drainage area)? -> hydro_find_gages\n"
        "- Springs, waterfalls, dams/weirs, gates, levees, wells? -> hydro_find_water_features\n"
        "- Which HUC12 watershed contains this location (and where does it drain)? -> hydro_identify_watershed\n"
        "- How many features of a layer intersect here (size guardrail before a find_*)? -> hydro_count_features\n"
        "- Discover all service layers / confirm layer IDs -> hydro_list_layers\n\n"
        "CONVENTIONS:\n"
        "- All coordinates are WGS84 decimal degrees (lat, lon). Convert addresses/place names to coordinates first.\n"
        "- Geometry input is a GeoJSON string: Point, MultiPoint, LineString, MultiLineString, Polygon, MultiPolygon,\n"
        "  or BoundingBox shorthand {\"type\": \"BoundingBox\", \"bbox\": [minLon, minLat, maxLon, maxLat]}.\n"
        "- For point/line feature layers (gages, water features), pass a Polygon or BoundingBox to find nearby features;\n"
        "  a bare point rarely coincides exactly with a point/line feature.\n"
        "- ftype/fcode are integer feature codes; results add ftype_label/fcode_label with readable names.\n"
        "- Drainage area units differ: gages report dasqmi in SQUARE MILES; flowlines/watersheds use AreaSqKm / TotalDrainageAreaSqKm.\n"
        "- Each layer caps at 2000 records per request; results paginate automatically and set truncated=true if capped.\n"
        "- Results include provenance (source agency USGS, dataset, service URL, layer, CRS, retrieval time).\n"
        "- No authentication required — the NHDPlus HR service is publicly accessible."
    ),
)

# Register custom tools
register_tools(mcp)

# Register custom routes
register_routes(mcp)

if __name__ == "__main__":
    port_env = os.getenv("DATABRICKS_APP_PORT") or os.getenv("PORT")
    if port_env:
        mcp.run(transport="http", host="0.0.0.0", port=int(port_env), path="/mcp")
    else:
        mcp.run(transport="stdio")
