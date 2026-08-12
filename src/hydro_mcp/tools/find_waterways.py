"""
find_waterways tool
--------------------
Registers the hydro_find_waterways tool on the MCP server.

Queries NHDPlus HR flowlines (streams, rivers, canals, artificial paths) that
intersect a point or arbitrary GeoJSON geometry. By default uses the
network-attributed NetworkNHDFlowline layer (stream order, drainage area,
slope, elevation, modeled flow/velocity). Optionally also includes the
NonNetworkNHDFlowline layer.

All coordinates are WGS84 (EPSG:4326) decimal degrees. Geometry is not returned.
"""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastmcp import FastMCP
from pydantic import Field

from ..models import (
    FLOWLINE_CORE_FIELDS,
    FLOWLINE_VERBOSE_FIELDS,
    LAYER_NETWORK_FLOWLINE,
    LAYER_NONNETWORK_FLOWLINE,
    NONNETWORK_FLOWLINE_FIELDS,
    WGS84,
)
from ..utils import (
    HydroError,
    enrich_codes,
    geojson_to_esri,
    parse_geometry_input,
    query_geometry,
)


def _summarize(features: list[dict[str, Any]]) -> str:
    if not features:
        return "No NHD flowlines intersect this location."
    names = sorted({f["gnis_name"] for f in features if f.get("gnis_name")})
    orders = [f.get("streamorde") for f in features if f.get("streamorde") is not None]
    total_km = sum(f.get("lengthkm") or 0 for f in features)
    parts = [f"{len(features)} flowline feature(s) intersect this location."]
    if names:
        shown = ", ".join(names[:5]) + ("..." if len(names) > 5 else "")
        parts.append(f"Named waterway(s): {shown}.")
    if orders:
        parts.append(f"Max Strahler stream order: {max(orders)}.")
    parts.append(f"Total flowline length: {total_km:.2f} km.")
    return " ".join(parts)


def register(mcp: FastMCP) -> None:
    """Register the find_waterways tool with the MCP server."""

    @mcp.tool(
        name="hydro_find_waterways",
        annotations={
            "title": "Find NHD Waterways (Flowlines)",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    def find_waterways(
        lat: Annotated[Optional[float], Field(
            description=(
                "Latitude in decimal degrees (WGS84). Use with 'lon' for a quick point query. "
                "Omit when supplying 'geometry'."
            ),
        )] = None,
        lon: Annotated[Optional[float], Field(
            description=(
                "Longitude in decimal degrees (WGS84). Use with 'lat' for a quick point query. "
                "Omit when supplying 'geometry'."
            ),
        )] = None,
        geometry: Annotated[Optional[str], Field(
            description=(
                "GeoJSON geometry object as a JSON string. Supported types: "
                "Point, MultiPoint, LineString, MultiLineString, Polygon, MultiPolygon. "
                "Also accepts a BoundingBox shorthand: "
                '{"type": "BoundingBox", "bbox": [minLon, minLat, maxLon, maxLat]}. '
                "All coordinates must be WGS84 decimal degrees. "
                "Supply either this OR lat+lon, not both."
            ),
        )] = None,
        include_non_network: Annotated[bool, Field(
            description=(
                "Also query the NonNetworkNHDFlowline layer (isolated flowlines with "
                "identity attributes only, no stream order / drainage area / flow). Default False."
            ),
        )] = False,
        verbose: Annotated[bool, Field(
            description=(
                "Return ALL flowline attributes (~80 fields incl. full EROM modeled-flow "
                "suite and network-navigation IDs) instead of the curated core set. "
                "Only applies to the network flowline layer. Default False."
            ),
        )] = False,
    ) -> dict[str, Any]:
        """Find NHD flowlines (streams, rivers, canals, artificial paths) intersecting a geometry.

        Uses NHDPlus HR NetworkNHDFlowline (layer 3), which carries stream order,
        total drainage area (totdasqkm), slope, smoothed elevation, and EROM
        mean-annual flow (qama, cfs) / velocity (vama, fps) estimates.

        Use lat+lon when: "What river runs through 45.5, -122.6?"
        Use geometry when: "What streams cross this project polygon / pipeline corridor?"
        Set include_non_network=True to also capture isolated (non-routed) flowlines.
        Set verbose=True for the full attribute set (network IDs + full EROM suite).

        Returns:
        {
            "finding": str,          # plain-language summary
            "count": int,
            "truncated": bool,       # true if capped at max_records
            "features": [...],       # flowline attributes (+ ftype_label / fcode_label)
            "non_network": {...},    # present only when include_non_network=True
            "provenance": {...},
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

            fields = FLOWLINE_VERBOSE_FIELDS if verbose else FLOWLINE_CORE_FIELDS
            result = query_geometry(
                geometry_json=geometry_json,
                geometry_type=esri_type,
                layer_id=LAYER_NETWORK_FLOWLINE,
                out_fields=fields,
            )
            result.features = enrich_codes(result.features)
            result.provenance.layer_name = "NetworkNHDFlowline"
            out = result.to_dict()
            out["finding"] = _summarize(result.features)
            out["query_geometry"] = {"type": geo_type, "crs_epsg": WGS84}

            if include_non_network:
                nn = query_geometry(
                    geometry_json=geometry_json,
                    geometry_type=esri_type,
                    layer_id=LAYER_NONNETWORK_FLOWLINE,
                    out_fields=NONNETWORK_FLOWLINE_FIELDS,
                )
                nn.features = enrich_codes(nn.features)
                nn.provenance.layer_name = "NonNetworkNHDFlowline"
                out["non_network"] = nn.to_dict()

            return out

        except HydroError as exc:
            return {"error": f"Error: {exc}"}
