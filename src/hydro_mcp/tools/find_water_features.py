"""
find_water_features tool
-------------------------
Registers the hydro_find_water_features tool on the MCP server.

Queries NHDPlus HR point and line "structural"/named water features intersecting
a point or arbitrary GeoJSON geometry:
  - NHDPoint (layer 2): springs/seeps, waterfalls, dams/weirs, gates, sink/rise,
    gaging stations, rocks, wells, ...
  - NHDLine (layer 7): dams/weirs, waterfalls, gates, walls, levees, bridges,
    flumes, tunnels, ...

All coordinates are WGS84 (EPSG:4326) decimal degrees. Geometry is not returned.
"""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastmcp import FastMCP
from pydantic import Field

from ..models import (
    LAYER_NHD_LINE,
    LAYER_NHD_POINT,
    NHD_LINE_FIELDS,
    NHD_POINT_FIELDS,
    WGS84,
)
from ..utils import (
    HydroError,
    enrich_codes,
    geojson_to_esri,
    parse_geometry_input,
    query_geometry,
)


def _describe(features: list[dict[str, Any]]) -> list[str]:
    """Human-readable type labels present in a feature set."""
    labels = sorted({
        f["fcode_label"] for f in features if f.get("fcode_label")
    }) or sorted({
        f["ftype_label"] for f in features if f.get("ftype_label")
    })
    return labels


def _summarize(points: list[dict[str, Any]], lines: list[dict[str, Any]]) -> str:
    total = len(points) + len(lines)
    if total == 0:
        return "No NHD point or line water features intersect this location."
    types = _describe(points + lines)
    parts = [
        f"{len(points)} point feature(s) and {len(lines)} line feature(s) intersect "
        f"this location."
    ]
    if types:
        shown = ", ".join(types[:6]) + ("..." if len(types) > 6 else "")
        parts.append(f"Feature type(s): {shown}.")
    return " ".join(parts)


def register(mcp: FastMCP) -> None:
    """Register the find_water_features tool with the MCP server."""

    @mcp.tool(
        name="hydro_find_water_features",
        annotations={
            "title": "Find NHD Point & Line Water Features",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    def find_water_features(
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
                "Use a Polygon or BoundingBox to capture nearby point/line features."
            ),
        )] = None,
        feature_class: Annotated[str, Field(
            description=(
                "Which layer(s) to query: 'point' (springs/waterfalls/dams/gates/wells), "
                "'line' (dams/gates/walls/levees/bridges), or 'both'. Default 'both'."
            ),
            pattern="^(point|line|both)$",
        )] = "both",
    ) -> dict[str, Any]:
        """Find NHD point & line water features (springs, waterfalls, dams, gates, levees, ...).

        Queries NHDPoint (layer 2) and/or NHDLine (layer 7) intersecting the geometry.
        Both carry gnis_name and ftype/fcode; point features also carry reachcode.

        Use when: "Are there any waterfalls or springs near this point?",
        "What dams/weirs cross this river within the bounding box?"

        Because these are point/line features, supply a Polygon or BoundingBox to find
        features within an area.

        Returns:
        {
            "finding": str,
            "point": {count, truncated, features, provenance},   # if requested
            "line": {count, truncated, features, provenance},    # if requested
            "query_geometry": {"type": str, "crs_epsg": int}
        }

        ftype/fcode are integer codes; ftype_label/fcode_label give readable names.

        Error responses:
        - "Error: supply either lat+lon or geometry, not both (or neither)"
        - "Error: unsupported geometry type ..."
        - "Error: NHDPlus HR request failed: ..."
        """
        try:
            geojson = parse_geometry_input(lat, lon, geometry)
            geo_type = geojson.get("type", "Unknown")
            geometry_json, esri_type = geojson_to_esri(geojson)

            out: dict[str, Any] = {"query_geometry": {"type": geo_type, "crs_epsg": WGS84}}
            point_features: list[dict[str, Any]] = []
            line_features: list[dict[str, Any]] = []

            if feature_class in ("point", "both"):
                pt = query_geometry(
                    geometry_json=geometry_json,
                    geometry_type=esri_type,
                    layer_id=LAYER_NHD_POINT,
                    out_fields=NHD_POINT_FIELDS,
                )
                pt.features = enrich_codes(pt.features)
                pt.provenance.layer_name = "NHDPoint"
                point_features = pt.features
                out["point"] = pt.to_dict()

            if feature_class in ("line", "both"):
                ln = query_geometry(
                    geometry_json=geometry_json,
                    geometry_type=esri_type,
                    layer_id=LAYER_NHD_LINE,
                    out_fields=NHD_LINE_FIELDS,
                )
                ln.features = enrich_codes(ln.features)
                ln.provenance.layer_name = "NHDLine"
                line_features = ln.features
                out["line"] = ln.to_dict()

            out["finding"] = _summarize(point_features, line_features)
            return out

        except HydroError as exc:
            return {"error": f"Error: {exc}"}
