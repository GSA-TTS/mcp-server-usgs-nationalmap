"""
count_features tool
--------------------
Registers the hydro_count_features tool on the MCP server.

A lightweight count-only guardrail. Use before the find_* tools to gauge result
size without fetching full attributes (e.g. dense urban stream networks or large
project footprints).

All coordinates are WGS84 (EPSG:4326) decimal degrees.
"""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastmcp import FastMCP
from pydantic import Field

from ..models import (
    LAYER_NHD_AREA,
    LAYER_NHD_LINE,
    LAYER_NHD_POINT,
    LAYER_NHD_WATERBODY,
    LAYER_NHDPLUS_GAGE,
    LAYER_NETWORK_FLOWLINE,
    LAYER_WBD_HU12,
    Provenance,
    WGS84,
)
from ..utils import (
    HydroError,
    count_at_geometry,
    geojson_to_esri,
    parse_geometry_input,
    _now_utc,
)

# Maps the friendly layer keyword to (layer_id, layer_name).
_LAYER_MAP: dict[str, tuple[int, str]] = {
    "waterways": (LAYER_NETWORK_FLOWLINE, "NetworkNHDFlowline"),
    "waterbodies": (LAYER_NHD_WATERBODY, "NHDWaterbody"),
    "areas": (LAYER_NHD_AREA, "NHDArea"),
    "gages": (LAYER_NHDPLUS_GAGE, "NHDPlusGage"),
    "points": (LAYER_NHD_POINT, "NHDPoint"),
    "lines": (LAYER_NHD_LINE, "NHDLine"),
    "watershed": (LAYER_WBD_HU12, "WBDHU12"),
}


def register(mcp: FastMCP) -> None:
    """Register the count_features tool with the MCP server."""

    @mcp.tool(
        name="hydro_count_features",
        annotations={
            "title": "Count NHDPlus HR Features at Geometry",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    def count_features(
        layer: Annotated[str, Field(
            description=(
                "Which feature layer to count. One of: 'waterways' (flowlines), "
                "'waterbodies', 'areas', 'gages', 'points', 'lines', 'watershed'."
            ),
            pattern="^(waterways|waterbodies|areas|gages|points|lines|watershed)$",
        )],
        lat: Annotated[Optional[float], Field(
            description="Latitude in decimal degrees (WGS84). Use with 'lon'. Omit when supplying 'geometry'.",
        )] = None,
        lon: Annotated[Optional[float], Field(
            description="Longitude in decimal degrees (WGS84). Use with 'lat'. Omit when supplying 'geometry'.",
        )] = None,
        geometry: Annotated[Optional[str], Field(
            description=(
                "GeoJSON geometry object as a JSON string. Supported types: "
                "Point, MultiPoint, LineString, MultiLineString, Polygon, MultiPolygon, "
                'or BoundingBox shorthand {"type": "BoundingBox", "bbox": [minLon, minLat, maxLon, maxLat]}. '
                "All coordinates must be WGS84 decimal degrees. Supply either this OR lat+lon, not both."
            ),
        )] = None,
    ) -> dict[str, Any]:
        """Return ONLY how many features of a layer intersect a point or geometry (size check).

        Use before the find_* tools to gauge result size without fetching full
        attributes -- useful for large polygons or densely mapped areas. A count of 0
        means the geometry is outside coverage or has no features of that type.

        Returns:
        {
            "count": int,
            "layer": str,
            "query_geometry": {"type": str, "crs_epsg": int},
            "provenance": {...}
        }

        Error responses:
        - "Error: supply either lat+lon or geometry, not both (or neither)"
        - "Error: unsupported geometry type ..."
        - "Error: NHDPlus HR request failed: ..."
        """
        try:
            layer_id, layer_name = _LAYER_MAP[layer]
            geojson = parse_geometry_input(lat, lon, geometry)
            geo_type = geojson.get("type", "Unknown")
            geometry_json, esri_type = geojson_to_esri(geojson)

            count = count_at_geometry(
                geometry_json=geometry_json,
                geometry_type=esri_type,
                layer_id=layer_id,
            )
            return {
                "count": count,
                "layer": layer,
                "query_geometry": {"type": geo_type, "crs_epsg": WGS84},
                "provenance": Provenance(
                    layer_id=layer_id,
                    layer_name=layer_name,
                    retrieved_utc=_now_utc(),
                ).to_dict(),
            }

        except HydroError as exc:
            return {"error": f"Error: {exc}"}
