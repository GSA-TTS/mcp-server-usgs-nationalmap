"""
utils.py
--------
Shared utilities: timestamp helper, GeoJSON->Esri conversion, coded-value
translation, and the NHDPlus HR ArcGIS HTTP client.

The client functions use only the stdlib (urllib) to keep dependencies minimal
and remain unit-testable in isolation from MCP.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from .models import (
    BASE_URL,
    DEFAULT_MAX_RECORDS,
    DEFAULT_TIMEOUT,
    FCODE_LABELS,
    FTYPE_LABELS,
    HUTYPE_LABELS,
    PURPCODE_LABELS,
    WGS84,
    Provenance,
    QueryResult,
)

_USER_AGENT = "hydro-mcp/0.1 (USGS NHDPlus HR MCP server)"


# ---------------------------------------------------------------------------
# Timestamp helper
# ---------------------------------------------------------------------------

def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class HydroError(RuntimeError):
    """Raised when the NHDPlus HR service errors or returns something unusable."""


# ---------------------------------------------------------------------------
# Coded-value translation
# ---------------------------------------------------------------------------

def _coerce_int(value: Any) -> int | None:
    """Best-effort int coercion (server may return codes as float/str)."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def enrich_codes(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add human-readable label fields alongside raw coded values, in place-safe copy.

    Adds:
      - ftype_label       when 'ftype' present
      - fcode_label       when 'fcode' present
      - hutype_label      when 'hutype' present
      - purpcode_label    when 'purpcode' present
    Raw codes are always preserved so downstream WHERE clauses still work.
    """
    enriched: list[dict[str, Any]] = []
    for f in features:
        out = dict(f)
        if "ftype" in out:
            code = _coerce_int(out.get("ftype"))
            if code is not None and code in FTYPE_LABELS:
                out["ftype_label"] = FTYPE_LABELS[code]
        if "fcode" in out:
            code = _coerce_int(out.get("fcode"))
            if code is not None and code in FCODE_LABELS:
                out["fcode_label"] = FCODE_LABELS[code]
        if "hutype" in out and out.get("hutype") in HUTYPE_LABELS:
            out["hutype_label"] = HUTYPE_LABELS[out["hutype"]]
        if "purpcode" in out and out.get("purpcode") in PURPCODE_LABELS:
            out["purpcode_label"] = PURPCODE_LABELS[out["purpcode"]]
        enriched.append(out)
    return enriched


# ---------------------------------------------------------------------------
# GeoJSON -> Esri geometry conversion
# ---------------------------------------------------------------------------

# Maps GeoJSON geometry type to the Esri geometryType parameter value.
_GEOJSON_TO_ESRI_TYPE: dict[str, str] = {
    "Point":           "esriGeometryPoint",
    "MultiPoint":      "esriGeometryMultipoint",
    "LineString":      "esriGeometryPolyline",
    "MultiLineString": "esriGeometryPolyline",
    "Polygon":         "esriGeometryPolygon",
    "MultiPolygon":    "esriGeometryPolygon",
}

# Convenience alias accepted as a shorthand in the tool layer.
_BBOX_TYPE = "BoundingBox"


def geojson_to_esri(geojson: dict[str, Any]) -> tuple[str, str]:
    """Convert a GeoJSON geometry object to (esri_json_str, esri_geometry_type).

    Supports: Point, MultiPoint, LineString, MultiLineString, Polygon,
    MultiPolygon. Also accepts a synthetic {"type": "BoundingBox",
    "bbox": [minLon, minLat, maxLon, maxLat]} shorthand that maps to
    esriGeometryEnvelope.

    All coordinates must be WGS84 (EPSG:4326).

    Raises HydroError on unknown or malformed geometry.
    """
    geo_type = geojson.get("type")
    sr = {"wkid": WGS84}

    # ---- BoundingBox shorthand ----------------------------------------
    if geo_type == _BBOX_TYPE:
        bbox = geojson.get("bbox")
        if not bbox or len(bbox) != 4:
            raise HydroError(
                "BoundingBox geometry requires a 'bbox' array of "
                "[minLon, minLat, maxLon, maxLat]."
            )
        min_lon, min_lat, max_lon, max_lat = bbox
        esri = {
            "xmin": min_lon, "ymin": min_lat,
            "xmax": max_lon, "ymax": max_lat,
            "spatialReference": sr,
        }
        return json.dumps(esri), "esriGeometryEnvelope"

    if geo_type not in _GEOJSON_TO_ESRI_TYPE:
        raise HydroError(
            f"Unsupported geometry type '{geo_type}'. "
            f"Supported types: {', '.join(sorted(_GEOJSON_TO_ESRI_TYPE))} or BoundingBox."
        )

    esri_type = _GEOJSON_TO_ESRI_TYPE[geo_type]
    coords = geojson.get("coordinates")
    if coords is None:
        raise HydroError(f"GeoJSON geometry of type '{geo_type}' is missing 'coordinates'.")

    if geo_type == "Point":
        # GeoJSON: [lon, lat] -- Esri: {x, y}
        esri = {"x": coords[0], "y": coords[1], "spatialReference": sr}

    elif geo_type == "MultiPoint":
        # GeoJSON: [[lon, lat], ...] -- Esri: {points: [[lon, lat], ...]}
        esri = {"points": [[c[0], c[1]] for c in coords], "spatialReference": sr}

    elif geo_type == "LineString":
        # GeoJSON: [[lon, lat], ...] -- Esri: {paths: [[[lon, lat], ...]]}
        esri = {"paths": [[[c[0], c[1]] for c in coords]], "spatialReference": sr}

    elif geo_type == "MultiLineString":
        # GeoJSON: [[[lon, lat], ...], ...] -- Esri: {paths: [[[lon, lat], ...], ...]}
        esri = {"paths": [[[c[0], c[1]] for c in line] for line in coords], "spatialReference": sr}

    elif geo_type == "Polygon":
        # GeoJSON: [exterior_ring, *hole_rings] -- Esri: {rings: [...]}
        esri = {"rings": [[[c[0], c[1]] for c in ring] for ring in coords], "spatialReference": sr}

    elif geo_type == "MultiPolygon":
        # GeoJSON: [[rings], [rings], ...] -- flatten all rings into one Esri polygon
        rings = []
        for polygon in coords:
            for ring in polygon:
                rings.append([[c[0], c[1]] for c in ring])
        esri = {"rings": rings, "spatialReference": sr}

    else:  # pragma: no cover -- unreachable, guarded above
        raise HydroError(f"Unhandled geometry type '{geo_type}'.")

    return json.dumps(esri), esri_type


def parse_geometry_input(
    lat: float | None,
    lon: float | None,
    geometry: str | None,
) -> dict[str, Any]:
    """Resolve the (lat, lon | geometry) tool inputs into a GeoJSON dict.

    Accepts EITHER lat+lon (wrapped into a Point) OR a GeoJSON string.
    Raises HydroError on invalid combinations or malformed JSON.
    """
    if lat is not None and lon is not None and geometry is None:
        return {"type": "Point", "coordinates": [lon, lat]}
    if geometry is not None and lat is None and lon is None:
        try:
            return json.loads(geometry)
        except json.JSONDecodeError as exc:
            raise HydroError(f"'geometry' is not valid JSON: {exc}") from exc
    raise HydroError("supply either lat+lon or geometry, not both (or neither).")


# ---------------------------------------------------------------------------
# NHDPlus HR HTTP client
# ---------------------------------------------------------------------------

def _get_json(url: str, params: dict[str, Any], timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """GET a URL with query params and parse JSON, with clear error handling.

    ArcGIS returns HTTP 200 even for logical errors, embedding an "error"
    object in the body -- so we check for that explicitly.
    """
    query = urllib.parse.urlencode(params, doseq=True)
    full_url = f"{url}?{query}"
    req = urllib.request.Request(full_url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as exc:  # noqa: BLE001 -- surface a clean error upward
        raise HydroError(f"Request to NHDPlus HR failed: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HydroError(
            f"NHDPlus HR returned non-JSON (first 200 chars): {raw[:200]!r}"
        ) from exc

    if isinstance(data, dict) and "error" in data:
        raise HydroError(f"NHDPlus HR service error: {data['error']}")
    return data


def count_at_geometry(
    geometry_json: str,
    geometry_type: str,
    layer_id: int,
    where: str = "1=1",
    timeout: int = DEFAULT_TIMEOUT,
) -> int:
    """Return ONLY the number of features intersecting an arbitrary geometry.

    This is the cost/completeness guardrail: check size before fetching.
    geometry_json and geometry_type should come from geojson_to_esri().
    """
    params = {
        "geometry": geometry_json,
        "geometryType": geometry_type,
        "inSR": WGS84,
        "spatialRel": "esriSpatialRelIntersects",
        "where": where,
        "returnCountOnly": "true",
        "f": "json",
    }
    data = _get_json(f"{BASE_URL}/{layer_id}/query", params, timeout=timeout)
    return int(data.get("count", 0))


def query_geometry(
    geometry_json: str,
    geometry_type: str,
    layer_id: int,
    out_fields: list[str],
    where: str = "1=1",
    max_records: int = DEFAULT_MAX_RECORDS,
    timeout: int = DEFAULT_TIMEOUT,
) -> QueryResult:
    """Return features intersecting an arbitrary Esri geometry, with provenance.

    geometry_json and geometry_type should come from geojson_to_esri().
    Geometry is intentionally NOT returned (returnGeometry=false) to keep the
    payload small for the agent's context window. Paginates automatically.
    """
    base_params = {
        "geometry": geometry_json,
        "geometryType": geometry_type,
        "inSR": WGS84,
        "spatialRel": "esriSpatialRelIntersects",
        "where": where,
        "outFields": ",".join(out_fields),
        "returnGeometry": "false",
        "f": "json",
    }

    features: list[dict[str, Any]] = []
    offset = 0
    truncated = False
    while True:
        params = dict(base_params)
        params["resultOffset"] = offset
        params["resultRecordCount"] = DEFAULT_MAX_RECORDS
        data = _get_json(f"{BASE_URL}/{layer_id}/query", params, timeout=timeout)
        page = [f.get("attributes", {}) for f in data.get("features", [])]
        features.extend(page)

        if len(features) >= max_records:
            features = features[:max_records]
            truncated = True
            break
        if not data.get("exceededTransferLimit") and len(page) < DEFAULT_MAX_RECORDS:
            break  # got everything
        if not page:
            break
        offset += len(page)

    return QueryResult(
        features=features,
        count=len(features),
        truncated=truncated,
        provenance=Provenance(layer_id=layer_id, retrieved_utc=_now_utc()),
    )


def list_layers(timeout: int = DEFAULT_TIMEOUT) -> list[dict[str, Any]]:
    """Return the layer catalog (id, name, geometry type) for discovery."""
    data = _get_json(BASE_URL, {"f": "json"}, timeout=timeout)
    return [
        {"id": l.get("id"), "name": l.get("name"), "geometry_type": l.get("geometryType")}
        for l in data.get("layers", [])
    ]
