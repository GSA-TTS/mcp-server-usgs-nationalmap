"""
identify_watershed tool
------------------------
Registers the hydro_identify_watershed tool on the MCP server.

Identifies the HUC12 watershed(s) (WBDHU12, layer 12) that a point or arbitrary
GeoJSON geometry falls within / intersects. Returns the watershed name, 12-digit
HUC code, downstream HUC (tohuc, for routing), area, and states.

All coordinates are WGS84 (EPSG:4326) decimal degrees. Geometry is not returned.
"""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastmcp import FastMCP
from pydantic import Field

from ..models import LAYER_WBD_HU12, WATERSHED_FIELDS, WGS84
from ..utils import (
    HydroError,
    enrich_codes,
    geojson_to_esri,
    parse_geometry_input,
    query_geometry,
)


def _summarize(features: list[dict[str, Any]]) -> str:
    if not features:
        return "No HUC12 watershed intersects this location (outside WBD coverage)."
    if len(features) == 1:
        f = features[0]
        return (
            f"Location is in HUC12 watershed '{f.get('name')}' "
            f"(HUC12 {f.get('huc12')}), which drains to HUC {f.get('tohuc')}."
        )
    listing = ", ".join(
        f"{f.get('name')} ({f.get('huc12')})" for f in features[:5]
    ) + ("..." if len(features) > 5 else "")
    return f"Geometry intersects {len(features)} HUC12 watershed(s): {listing}."


def register(mcp: FastMCP) -> None:
    """Register the identify_watershed tool with the MCP server."""

    @mcp.tool(
        name="hydro_identify_watershed",
        annotations={
            "title": "Identify HUC12 Watershed",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    def identify_watershed(
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
        """Identify the HUC12 watershed(s) containing/intersecting a geometry (WBDHU12, layer 12).

        Returns the watershed name, 12-digit HUC code, downstream HUC (tohuc, for
        routing), hydrologic-unit type (hutype + label), area, and states.

        Use when: "What watershed is this point in?", "Which HUC12 does this river reach
        drain to?", "List the sub-watersheds this project boundary spans."

        A point returns the single containing HUC12; a polygon/bbox may intersect several.

        Returns:
        {
            "finding": str,
            "count": int,
            "truncated": bool,
            "features": [...],   # huc12, name, tohuc, hutype (+ hutype_label), areasqkm, states, ...
            "provenance": {...},
            "query_geometry": {"type": str, "crs_epsg": int}
        }

        Error responses:
        - "Error: supply either lat+lon or geometry, not both (or neither)"
        - "Error: unsupported geometry type ..."
        - "Error: NHDPlus HR request failed: ..."
        """
        try:
            geojson = parse_geometry_input(lat, lon, geometry)
            geo_type = geojson.get("type", "Unknown")
            geometry_json, esri_type = geojson_to_esri(geojson)

            result = query_geometry(
                geometry_json=geometry_json,
                geometry_type=esri_type,
                layer_id=LAYER_WBD_HU12,
                out_fields=WATERSHED_FIELDS,
            )
            result.features = enrich_codes(result.features)
            result.provenance.layer_name = "WBDHU12"
            out = result.to_dict()
            out["finding"] = _summarize(result.features)
            out["query_geometry"] = {"type": geo_type, "crs_epsg": WGS84}
            return out

        except HydroError as exc:
            return {"error": f"Error: {exc}"}
