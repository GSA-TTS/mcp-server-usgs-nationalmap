# mcp-server-usgs-nationalmap

An MCP (Model Context Protocol) server that wraps the **USGS NHDPlus High
Resolution (NHDPlus HR)** ArcGIS REST MapServer, letting an LLM query official
U.S. hydrography — streams, rivers, lakes, stream gages, water features, and
watershed boundaries — for a point or arbitrary GeoJSON geometry.

- **Service:** `https://hydro.nationalmap.gov/arcgis/rest/services/NHDPlus_HR/MapServer`
- **Source:** USGS — National Hydrography Dataset Plus High Resolution
- **Auth:** none (public service)
- **Package:** `hydro_mcp`

## What the dataset is

NHDPlus HR is a nationally seamless, routed hydrography network built from the
high-resolution NHD, the Watershed Boundary Dataset (WBD), and 3DEP elevation.
The MapServer exposes 13 layers; this server wraps the ones most useful for
site/hydrology analysis.

## Tools

All geometry tools accept **either** a `lat` + `lon` pair (convenience) **or** a
GeoJSON `geometry` string. Supported GeoJSON types: `Point`, `MultiPoint`,
`LineString`, `MultiLineString`, `Polygon`, `MultiPolygon`, plus a `BoundingBox`
shorthand `{"type": "BoundingBox", "bbox": [minLon, minLat, maxLon, maxLat]}`.
All coordinates are **WGS84 decimal degrees**. Feature geometry is not returned
(payloads stay small); results include provenance.

| Tool | Layers | Purpose |
|---|---|---|
| `hydro_find_waterways` | NetworkNHDFlowline (3), optional NonNetworkNHDFlowline (4) | Streams/rivers/canals with stream order, drainage area, slope, elevation, and EROM modeled flow (`qama`, cfs) / velocity (`vama`, fps). `verbose=True` returns all ~80 attributes; `include_non_network=True` adds isolated flowlines. |
| `hydro_find_waterbodies` | NHDWaterbody (9), NHDArea (8) | Lakes, ponds, reservoirs, swamps, and areal water features (wide rivers, bays, rapids, dams). `feature_class` = `waterbody` \| `area` \| `both`. |
| `hydro_find_gages` | NHDPlusGage (0) | Stream gages with NWIS linkage (`sourceid`/`sourceagency`) and drainage area (`dasqmi`, **square miles**). |
| `hydro_find_water_features` | NHDPoint (2), NHDLine (7) | Springs, waterfalls, dams/weirs, gates, levees, wells, etc. `feature_class` = `point` \| `line` \| `both`. |
| `hydro_identify_watershed` | WBDHU12 (12) | HUC12 watershed name, 12-digit code, downstream HUC (`tohuc`), type, area, states. |
| `hydro_count_features` | any of the above | Count-only guardrail; check result size before a `find_*`. `layer` = `waterways` \| `waterbodies` \| `areas` \| `gages` \| `points` \| `lines` \| `watershed`. |
| `hydro_list_layers` | service root | Discover all 13 layers (id, name, geometry type). |

### Conventions & gotchas

- **Coordinates:** WGS84 lat/lon. Convert addresses/place names to coordinates first.
- **Point/line layers** (gages, water features): pass a `Polygon` or `BoundingBox`
  to capture nearby features — a bare point rarely coincides exactly with a point/line feature.
- **Feature codes:** `ftype`/`fcode` are integers; results add `ftype_label` /
  `fcode_label` (e.g. `46006 → "Stream/River: Perennial"`). `hutype` and
  `purpcode` are similarly labeled.
- **Drainage-area units differ:** gages report `dasqmi` in **square miles**;
  flowlines/watersheds use `AreaSqKm` / `TotalDrainageAreaSqKm`.
- **Pagination:** each layer caps at 2000 records/request; results paginate
  automatically and set `truncated: true` if a cap is hit.
- Field names on the service are lowercase; the CamelCase forms are aliases.

## Setup

```bash
uv sync
```

## Run

```bash
# stdio (Claude Desktop, Claude Code, local MCP clients)
uv run python -m hydro_mcp.app

# HTTP (set PORT or DATABRICKS_APP_PORT); served at /mcp, health at /health
PORT=8000 uv run python -m hydro_mcp.app
```

## Project structure

```
src/hydro_mcp/
├── app.py            # FastMCP init, instructions, transport wiring
├── routes.py         # /health endpoint
├── models.py         # constants, layer IDs, curated field lists, code label maps, dataclasses
├── utils.py          # ArcGIS HTTP client (stdlib urllib), GeoJSON->Esri, code translation
└── tools/            # one file per tool
    ├── __init__.py           # register_tools(mcp)
    ├── find_waterways.py
    ├── find_waterbodies.py
    ├── find_gages.py
    ├── find_water_features.py
    ├── identify_watershed.py
    ├── count_features.py
    └── list_layers.py
```

## Possible future add-ons

The current tools are geometry-intersection queries. NHDPlus HR is a fully
**routed** network, which opens up several higher-value tools not yet implemented:

- **Upstream/downstream network tracing** (`hydro_trace_upstream` /
  `hydro_trace_downstream`): walk the flowline network from a starting reach
  using `hydroseq`, `levelpathi`, `uphydroseq`/`dnhydroseq`, and
  `fromnode`/`tonode`. Enables "what's upstream of this point?" and pollutant/
  flow-path questions.
- **Watershed routing traversal:** follow `tohuc` from a starting HUC12 down the
  drainage chain (or accumulate the upstream set) to build drainage lineages.
- **Catchment lookup** (NHDPlusCatchment, layer 10): return the elevation-based
  incremental catchment polygon(s) for a location, and join to flowline VAAs via
  `nhdplusid`.
- **Reach-code / NHDPlusID lookup tools:** fetch a specific reach or feature by
  `reachcode` / `permanent_identifier` / `nhdplusid` rather than by geometry.
- **Gage cross-walk to NWIS:** resolve `sourceid`/`gageidma` to live USGS NWIS
  streamflow observations.
- **Attribute filtering:** expose a `where` filter (e.g. minimum stream order,
  perennial-only) on the `find_*` tools for large-area queries.

## Data source & attribution

USGS The National Map — National Hydrography Dataset Plus High Resolution
(NHDPlus HR). Public domain. See
<https://www.usgs.gov/national-hydrography/national-hydrography-dataset>.
