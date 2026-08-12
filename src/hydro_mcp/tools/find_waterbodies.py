"""
find_waterbodies tool
----------------------
Registers the hydro_find_waterbodies tool on the MCP server.

Queries NHDPlus HR polygon water features intersecting a point or arbitrary
GeoJSON geometry:
  - NHDWaterbody (layer 9): lakes, ponds, reservoirs, swamps/marshes, estuaries
  - NHDArea (layer 8): areal water features (wide rivers, bays, rapids, dams, ...)

All coordinates are WGS84 (EPSG:4326) decimal degrees. Geometry is not returned.
"""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastmcp import FastMCP
from pydantic import Field

from ..models import (
    AREA_FIELDS,
    LAYER_NHD_AREA,
    LAYER_NHD_WATERBODY,
    WATERBODY_FIELDS,
    WGS84,
)
from ..utils import (
    HydroError,
    enrich_codes,
    geojson_to_esri,
    parse_geometry_input,
    query_geometry,
)


def _summarize(waterbodies: list[dict[str, Any]], areas: list[dict[str, Any]]) -> str:
    total = len(waterbodies) + len(areas)
    if total == 0:
        return "No NHD waterbodies or areal water features intersect this location."
    names = sorted({
        f["gnis_name"] for f in (waterbodies + areas) if f.get("gnis_name")
    })
    parts = [
        f"{len(waterbodies)} waterbody polygon(s) and {len(areas)} areal water "
        f"feature(s) intersect this location."
    ]
    if names:
        shown = ", ".join(names[:5]) + ("..." if len(names) > 5 else "")
        parts.append(f"Named feature(s): {shown}.")
    return " ".join(parts)


def register(mcp: FastMCP) -> None:
    """Register the find_waterbodies tool with the MCP server."""

    @mcp.tool(
        name="hydro_find_waterbodies",
        annotations={
            "title": "Find NHD Waterbodies & Areal Water Features",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    def find_waterbodies(
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
        feature_class: Annotated[str, Field(
            description=(
                "Which polygon layer(s) to query: 'waterbody' (lakes/ponds/reservoirs/swamps), "
                "'area' (wide rivers/bays/rapids/dams), or 'both'. Default 'both'."
            ),
            pattern="^(waterbody|area|both)$",
        )] = "both",
    ) -> dict[str, Any]:
        """Find NHD waterbodies (lakes, ponds, reservoirs, swamps) and areal water features.

        Queries NHDWaterbody (layer 9) and/or NHDArea (layer 8) polygons intersecting
        the geometry. Both carry gnis_name, ftype/fcode, areasqkm, and elevation.

        Use when: "Is there a lake within this parcel?", "What reservoirs intersect this
        bounding box?", "Name the waterbody at this point."

        Returns:
        {
            "finding": str,
            "waterbody": {count, truncated, features, provenance},   # if requested
            "area": {count, truncated, features, provenance},        # if requested
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
            wb_features: list[dict[str, Any]] = []
            area_features: list[dict[str, Any]] = []

            if feature_class in ("waterbody", "both"):
                wb = query_geometry(
                    geometry_json=geometry_json,
                    geometry_type=esri_type,
                    layer_id=LAYER_NHD_WATERBODY,
                    out_fields=WATERBODY_FIELDS,
                )
                wb.features = enrich_codes(wb.features)
                wb.provenance.layer_name = "NHDWaterbody"
                wb_features = wb.features
                out["waterbody"] = wb.to_dict()

            if feature_class in ("area", "both"):
                ar = query_geometry(
                    geometry_json=geometry_json,
                    geometry_type=esri_type,
                    layer_id=LAYER_NHD_AREA,
                    out_fields=AREA_FIELDS,
                )
                ar.features = enrich_codes(ar.features)
                ar.provenance.layer_name = "NHDArea"
                area_features = ar.features
                out["area"] = ar.to_dict()

            out["finding"] = _summarize(wb_features, area_features)
            return out

        except HydroError as exc:
            return {"error": f"Error: {exc}"}
