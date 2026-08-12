"""
find_gages tool
---------------
Registers the hydro_find_gages tool on the MCP server.

Queries NHDPlus HR stream gages (NHDPlusGage, layer 0) intersecting a point or
arbitrary GeoJSON geometry. Gages link to NWIS via sourceid / sourceagency.

NOTE: gage drainage area (dasqmi) is in SQUARE MILES, unlike the SqKm fields on
other layers.

All coordinates are WGS84 (EPSG:4326) decimal degrees. Geometry is not returned.
"""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastmcp import FastMCP
from pydantic import Field

from ..models import GAGE_FIELDS, LAYER_NHDPLUS_GAGE, WGS84
from ..utils import (
    HydroError,
    geojson_to_esri,
    parse_geometry_input,
    query_geometry,
)


def _summarize(features: list[dict[str, Any]]) -> str:
    if not features:
        return "No NHDPlus stream gages intersect this location."
    names = sorted({f["station_nm"] for f in features if f.get("station_nm")})
    parts = [f"{len(features)} stream gage(s) intersect this location."]
    if names:
        shown = ", ".join(names[:5]) + ("..." if len(names) > 5 else "")
        parts.append(f"Gage(s): {shown}.")
    return " ".join(parts)


def register(mcp: FastMCP) -> None:
    """Register the find_gages tool with the MCP server."""

    @mcp.tool(
        name="hydro_find_gages",
        annotations={
            "title": "Find NHDPlus Stream Gages",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    def find_gages(
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
                "All coordinates must be WGS84 decimal degrees. Supply either this OR lat+lon, not both. "
                "Gages are points, so use a Polygon or BoundingBox to capture nearby gages."
            ),
        )] = None,
    ) -> dict[str, Any]:
        """Find NHDPlus stream gages intersecting a geometry (NHDPlusGage, layer 0).

        Each gage links to NWIS via sourceid + sourceagency and reports the
        monitored drainage area (dasqmi, in SQUARE MILES) and reach location.

        Use when: "What stream gages are in this watershed / bounding box?",
        "Which gage monitors this river reach?"

        Because gages are point features, supply a Polygon or BoundingBox to find
        gages within an area (a bare point rarely coincides exactly with a gage).

        Returns:
        {
            "finding": str,
            "count": int,
            "truncated": bool,
            "features": [...],   # station_nm, sourceid, sourceagency, dasqmi (SQ MILES), ...
            "provenance": {...},
            "query_geometry": {"type": str, "crs_epsg": int}
        }

        NOTE: dasqmi is drainage area in SQUARE MILES (not sq km).

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
                layer_id=LAYER_NHDPLUS_GAGE,
                out_fields=GAGE_FIELDS,
            )
            result.provenance.layer_name = "NHDPlusGage"
            out = result.to_dict()
            out["finding"] = _summarize(result.features)
            out["query_geometry"] = {"type": geo_type, "crs_epsg": WGS84}
            return out

        except HydroError as exc:
            return {"error": f"Error: {exc}"}
