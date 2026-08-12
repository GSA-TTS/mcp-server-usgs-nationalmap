"""
models.py
---------
Shared constants, layer catalog, curated field lists, coded-value label maps,
and lightweight result dataclasses for the USGS NHDPlus High Resolution client.

Kept dependency-free (stdlib only) so the client layer stays unit-testable in
isolation from MCP.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Service constants
# ---------------------------------------------------------------------------

BASE_URL = "https://hydro.nationalmap.gov/arcgis/rest/services/NHDPlus_HR/MapServer"

# WGS84 lon/lat. This is what GPS coordinates are in and what we require callers
# to pass. We NEVER silently assume a CRS.
WGS84 = 4326

# The service caps each response at this many records. Above this you MUST page.
DEFAULT_MAX_RECORDS = 2000

DEFAULT_TIMEOUT = 30  # seconds

# ---------------------------------------------------------------------------
# Layer catalog (discovered live from the service; see list_layers()).
# NOTE: field names on the server are lowercase; aliases are CamelCase. WHERE
# clauses and outFields must use the lowercase physical names.
# ---------------------------------------------------------------------------

LAYER_NHDPLUS_GAGE = 0            # points: stream gages (NWIS linkage)
LAYER_NHDPLUS_SINK = 1           # points: modeling sinks (not exposed as a tool)
LAYER_NHD_POINT = 2              # points: springs, waterfalls, dams, gates, ...
LAYER_NETWORK_FLOWLINE = 3       # polylines: streams/rivers WITH VAA + EROM flow
LAYER_NONNETWORK_FLOWLINE = 4    # polylines: isolated flowlines, identity only
LAYER_FLOW_DIRECTION = 5         # polylines: modeling layer (not exposed)
LAYER_NHDPLUS_WALL = 6           # polylines: modeling layer (not exposed)
LAYER_NHD_LINE = 7              # polylines: dams, waterfalls, gates, walls, ...
LAYER_NHD_AREA = 8              # polygons: wide rivers, bays, dams, rapids
LAYER_NHD_WATERBODY = 9         # polygons: lakes, ponds, reservoirs, swamps
LAYER_NHDPLUS_CATCHMENT = 10    # polygons: catchments (future add-on)
LAYER_NHDPLUS_BOUNDARY_UNIT = 11  # polygons: VPU boundaries (not exposed)
LAYER_WBD_HU12 = 12            # polygons: HUC12 watershed boundaries


# ---------------------------------------------------------------------------
# Curated output field lists (explicit > wildcard: small payloads, stable API).
# ---------------------------------------------------------------------------

# NetworkNHDFlowline (layer 3) — the analytical core. Curated "core" set.
FLOWLINE_CORE_FIELDS = [
    "gnis_name",       # feature name (e.g. "Mississippi River")
    "ftype",           # feature type code (e.g. 460 = StreamRiver)
    "fcode",           # detailed feature code (e.g. 46006 = perennial)
    "reachcode",       # 14-digit NHD reach code
    "lengthkm",        # flowline length in km
    "streamorde",      # Strahler stream order
    "streamleve",      # stream level
    "totdasqkm",       # total upstream drainage area (sq km)
    "areasqkm",        # incremental catchment area (sq km)
    "slope",           # channel slope
    "minelevsmo",      # min smoothed elevation (cm)
    "maxelevsmo",      # max smoothed elevation (cm)
    "qama",            # EROM mean-annual flow estimate (cfs)
    "vama",            # EROM mean-annual velocity estimate (fps)
    "gnis_id",
    "nhdplusid",       # NHDPlus stable ID
    "permanent_identifier",
    "vpuid",
]

# The full attribute set for verbose flowline queries (returnGeometry stays off).
# "*" pulls every field the service exposes for the layer.
FLOWLINE_VERBOSE_FIELDS = ["*"]

# NonNetworkNHDFlowline (layer 4) — identity/geometry only (no VAA/flow).
NONNETWORK_FLOWLINE_FIELDS = [
    "gnis_name",
    "ftype",
    "fcode",
    "reachcode",
    "lengthkm",
    "gnis_id",
    "nhdplusid",
    "permanent_identifier",
    "vpuid",
]

# NHDWaterbody (layer 9) — lakes/ponds/reservoirs/swamps.
WATERBODY_FIELDS = [
    "gnis_name",
    "ftype",
    "fcode",
    "areasqkm",
    "elevation",
    "reachcode",
    "purpcode",
    "gnis_id",
    "nhdplusid",
    "permanent_identifier",
    "vpuid",
]

# NHDArea (layer 8) — areal water features (no reachcode field).
AREA_FIELDS = [
    "gnis_name",
    "ftype",
    "fcode",
    "areasqkm",
    "elevation",
    "purpcode",
    "gnis_id",
    "nhdplusid",
    "permanent_identifier",
    "vpuid",
]

# NHDPlusGage (layer 0). NOTE: drainage area here is in SQUARE MILES (dasqmi).
GAGE_FIELDS = [
    "station_nm",
    "sourceid",
    "sourceagency",
    "sourcedataset",
    "dasqmi",          # drainage area in SQUARE MILES (not sq km!)
    "state",
    "reachcode",
    "measure",
    "hydroaddressid",
    "featuretype",
    "nhdplusid",
    "vpuid",
]

# NHDPoint (layer 2) — springs, waterfalls, dams, gates, sink/rise, wells, ...
NHD_POINT_FIELDS = [
    "gnis_name",
    "ftype",
    "fcode",
    "reachcode",
    "gnis_id",
    "nhdplusid",
    "permanent_identifier",
    "vpuid",
]

# NHDLine (layer 7) — dams, waterfalls, gates, walls, levees, ... (no reachcode)
NHD_LINE_FIELDS = [
    "gnis_name",
    "ftype",
    "fcode",
    "lengthkm",
    "gnis_id",
    "nhdplusid",
    "permanent_identifier",
    "vpuid",
]

# WBDHU12 (layer 12) — HUC12 watershed boundaries.
WATERSHED_FIELDS = [
    "huc12",
    "name",
    "hutype",
    "tohuc",           # downstream HUC (routing)
    "areasqkm",
    "areaacres",
    "states",
    "nhdplusid",
    "vpuid",
    "tnmid",
]


# ---------------------------------------------------------------------------
# Coded-value label maps
# ---------------------------------------------------------------------------
# FType is the coarse feature type; FCode is the detailed code (often FType*100
# plus a subtype). We translate both for human-readable output. Curated from the
# NHDPlus HR subtype coded-value domains.

FTYPE_LABELS: dict[int, str] = {
    307: "Area to be Submerged",
    312: "Bay/Inlet",
    318: "Bridge",
    334: "Connector",
    336: "Canal/Ditch",
    343: "Dam/Weir",
    361: "Playa",
    362: "Flume",
    364: "Foreshore",
    367: "Gaging Station",
    369: "Gate",
    378: "Ice Mass",
    390: "Lake/Pond",
    398: "Lock Chamber",
    403: "Inundation Area",
    411: "Nonearthen Shore",
    420: "Underground Conduit",
    428: "Pipeline",
    431: "Rapids",
    434: "Reef",
    436: "Reservoir",
    441: "Rock",
    445: "Sea/Ocean",
    450: "Sink/Rise",
    455: "Spillway",
    458: "Spring/Seep",
    460: "Stream/River",
    461: "Submerged Stream",
    466: "Swamp/Marsh",
    468: "Drainageway",
    478: "Tunnel",
    483: "Wall",
    484: "Wash",
    485: "Water Intake/Outflow",
    487: "Waterfall",
    488: "Well",
    493: "Estuary",
    503: "Sounding Datum Line",
    537: "Area of Complex Channels",
    558: "Artificial Path",
    566: "Coastline",
    568: "Levee",
}

FCODE_LABELS: dict[int, str] = {
    # Stream/River (460)
    46000: "Stream/River",
    46003: "Stream/River: Intermittent",
    46006: "Stream/River: Perennial",
    46007: "Stream/River: Ephemeral",
    # Artificial Path / Connector / Coastline
    55800: "Artificial Path",
    33400: "Connector",
    56600: "Coastline",
    # Canal/Ditch (336)
    33600: "Canal/Ditch",
    33601: "Canal/Ditch: Aqueduct",
    33603: "Canal/Ditch: Stormwater",
    # Pipeline / Conduit / Drainageway
    42800: "Pipeline",
    42000: "Underground Conduit",
    42001: "Underground Conduit: Aqueduct",
    42002: "Underground Conduit: General",
    42003: "Underground Conduit: Stormwater",
    46800: "Drainageway",
    # Lake/Pond (390)
    39000: "Lake/Pond",
    39001: "Lake/Pond: Intermittent",
    39004: "Lake/Pond: Perennial",
    39009: "Lake/Pond: Perennial, Average Water Elevation",
    39010: "Lake/Pond: Perennial, Normal Pool",
    39011: "Lake/Pond: Perennial, Date of Photography",
    39012: "Lake/Pond: Perennial, Spillway Elevation",
    # Reservoir (436)
    43600: "Reservoir",
    43601: "Reservoir: Aquaculture",
    43607: "Reservoir: Evaporator",
    43609: "Reservoir: Treatment (Sewage)",
    43610: "Reservoir: Disposal",
    43613: "Reservoir: Water Storage",
    43617: "Reservoir: Filtration Pond",
    43618: "Reservoir: Settling Pond",
    43619: "Reservoir: Cooling Pond",
    43621: "Reservoir: Water Storage, Intermittent",
    43624: "Reservoir: Treatment",
    43625: "Reservoir: Tailings Pond",
    # Swamp/Marsh (466)
    46600: "Swamp/Marsh",
    46601: "Swamp/Marsh: Intermittent",
    46602: "Swamp/Marsh: Perennial",
    # Estuary / Playa / Ice Mass
    49300: "Estuary",
    36100: "Playa",
    37800: "Ice Mass",
    # NHDArea features
    44500: "Sea/Ocean",
    31200: "Bay/Inlet",
    36400: "Foreshore",
    43100: "Rapids",
    48400: "Wash",
    40300: "Inundation Area",
    40307: "Inundation Area: Controlled",
    40308: "Inundation Area: Duration",
    40309: "Inundation Area: General",
    31800: "Bridge",
    39800: "Lock Chamber",
    36200: "Flume",
    45500: "Spillway",
    56800: "Levee",
    48500: "Water Intake/Outflow",
    46100: "Submerged Stream",
    53700: "Area of Complex Channels",
    30700: "Area to be Submerged",
    # Dam/Weir (343)
    34300: "Dam/Weir",
    34305: "Dam/Weir: Perennial",
    34306: "Dam/Weir: Intermittent",
    # NHDPoint / NHDLine features
    36700: "Gaging Station",
    36701: "Gaging Station: Stream",
    45000: "Sink/Rise",
    45001: "Sink/Rise: Sink",
    45002: "Sink/Rise: Rise",
    45003: "Sink/Rise: Estavelle",
    45800: "Spring/Seep",
    48700: "Waterfall",
    48800: "Well",
    44100: "Rock",
    43400: "Reef",
    36900: "Gate",
    41100: "Nonearthen Shore",
    47800: "Tunnel",
    48300: "Wall",
    50300: "Sounding Datum Line",
}

# HUType codes for WBDHU12.hutype
HUTYPE_LABELS: dict[str, str] = {
    "S": "Standard",
    "C": "Closed Basin",
    "F": "Frontal",
    "M": "Multiple Outlet",
    "W": "Water",
    "I": "Island",
    "U": "Unclassified",
    "D": "Not Classified (Drains)",
}

# NHDWaterbody / NHDArea purpcode
PURPCODE_LABELS: dict[str, str] = {
    "SE": "Network End",
    "WB": "NHDWaterbody (other)",
}


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class Provenance:
    """Where a result came from -- essential for a hydrology analysis record."""
    source_agency: str = "USGS"
    dataset: str = "NHDPlus High Resolution (NHDPlus HR)"
    service_url: str = BASE_URL
    layer_id: int | None = None
    layer_name: str | None = None
    crs_epsg: int = WGS84
    retrieved_utc: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_agency": self.source_agency,
            "dataset": self.dataset,
            "service_url": self.service_url,
            "layer_id": self.layer_id,
            "layer_name": self.layer_name,
            "crs_epsg": self.crs_epsg,
            "retrieved_utc": self.retrieved_utc,
        }


@dataclass
class QueryResult:
    """A compact, model-friendly answer with provenance attached."""
    features: list[dict[str, Any]] = field(default_factory=list)
    count: int = 0
    truncated: bool = False   # True if there were more records than we fetched
    provenance: Provenance = field(default_factory=Provenance)

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "truncated": self.truncated,
            "features": self.features,
            "provenance": self.provenance.to_dict(),
        }
