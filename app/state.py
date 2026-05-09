from typing import Any, Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, Field
from app.services.gpx_analytics import GPXStats

class ImageData(BaseModel):
    path: str
    timestamp: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class ImageDataList(BaseModel):
    images: List[ImageData]

class DailyWeather(BaseModel):
    date: str
    temperature_max: float
    temperature_min: float
    precipitation_mm: float         # Niederschlagsmenge
    precipitation_hours: float      # Stunden mit Niederschlag (Intensitätsindikator)
    freezing_level_m: Optional[float] = None  # 0°C-Grenze (Höhe ü. NN)
    weather_code: int               # Open-Meteo WMO code
    wind_speed_kmh: float
    cloud_cover_pct: float


class WeatherInfo(BaseModel):
    daily: List[DailyWeather]
    source: str = "open-meteo"
    summary: str = ""

AVAILABLE_MODELS: Tuple[str, ...] = (
    "gemma4:26b-ctx128k",
    "gemma4:31b-ctx112k",
    "qwen3.6:27b-ctx128k",
    "qwen3.6:35b-ctx128k",
)


class PhotobookConfig(BaseModel):
    """Konfiguration fuer die Fotobuch-Ausgabe."""
    photo_count: int = Field(default=20, ge=5, le=30)
    page_range: str = "14-18"
    size: Literal["short", "normal", "detailed"] = "normal"


PHOTOBOOK_SIZE_MAP = {
    "short":    {"photo_count": 12, "page_range": "8-12"},
    "normal":   {"photo_count": 16, "page_range": "14-18"},
    "detailed": {"photo_count": 20, "page_range": "20-24"},
}


def apply_photobook_size(size: str) -> PhotobookConfig:
    """Erzeugt PhotobookConfig aus Grössenstufe (short/normal/detailed)."""
    mapping = PHOTOBOOK_SIZE_MAP.get(size, PHOTOBOOK_SIZE_MAP["normal"])
    resolved_size = size if size in PHOTOBOOK_SIZE_MAP else "normal"
    return PhotobookConfig(
        photo_count=mapping["photo_count"],
        page_range=mapping["page_range"],
        size=resolved_size,
    )


class OutputConfig(BaseModel):
    """Konfiguration für die Blog-Ausgabe — vom Benutzer vor Pipeline-Start gesetzt."""
    wildcard_max: int = Field(default=12, ge=1, le=50)
    article_length: Literal["short", "normal", "detailed"] = "normal"
    style_persona: Literal["mountain_veteran", "field_reporter"] = "mountain_veteran"
    pdf_export: bool = False
    review_enabled: bool = False
    mode: Literal["blog", "photobook"] = "blog"
    photobook: PhotobookConfig = PhotobookConfig()
    photobook_preset: Literal[
        "nature_outdoor", "culture_architecture", "people", "nature_collage", "mixed"
    ] = "mixed"


# ── Neue Modelle für typisierte State-Fields ──

class ImageCluster(BaseModel):
    """Cluster von geographisch nahen Bildern."""
    id: int
    images: List[str]  # Pfade der Bilder im Cluster
    center_lat: float
    center_lon: float


class POI(BaseModel):
    """Point of Interest entlang der Route."""
    name: str
    type: str
    lat: float
    lon: float
    distance_km: Optional[float] = None
    wiki_extract: Optional[str] = None
    wiki_tag: Optional[str] = None


class PageSlot(BaseModel):
    """Ein Slot (Bild oder Text) innerhalb einer Fotobuch-Seite."""
    slot_id: str
    text: Optional[str] = None
    image_index: Optional[int] = None


class BlogPostResult(BaseModel):
    """Ergebnis der Blogpost-Generierung."""
    success: bool
    markdown: Optional[str] = None
    html: Optional[str] = None
    file_paths: Dict[str, str] = Field(default_factory=dict)
    selected_images: List[str] = Field(default_factory=list)
    descriptions: Dict[str, str] = Field(default_factory=dict)
    pdf_bytes: Optional[bytes] = None
    pdf_error: Optional[str] = None
    error: Optional[str] = None
    html_converted: Optional[bool] = None


class EnrichmentContext(BaseModel):
    """Kuratierter Anreicherungs-Kontext aus dem Content-Review."""
    weather_summary: str = ""
    kept_pois: List[POI] = Field(default_factory=list)
    discarded_weather_fields: List[str] = Field(default_factory=list)
    image_ratings: Dict[str, Any] = Field(default_factory=dict)
    filtered_images: List[ImageData] = Field(default_factory=list)
    coherence_score: float = 0.0
    flags: List[str] = Field(default_factory=list)


class PagePlan(BaseModel):
    """Einzelne Seite im Fotobuch-Layout-Plan."""
    preset_id: str
    position: int = 0
    image_indices: List[int] = Field(default_factory=list)
    purpose: str = ""
    slots: List[PageSlot] = Field(default_factory=list)


class PhotobookPlan(BaseModel):
    """Vollständiger Fotobuch-Layout-Plan."""
    pages: List[PagePlan] = Field(default_factory=list)


class PageDescription(BaseModel):
    """Seitenbeschreibung — Output des LLM (Pass 2), Input des Renderers."""
    template_id: str
    page_type: str  # "single" | "spread"
    slots: List[PageSlot] = Field(default_factory=list)


class AppState(BaseModel):
    images: List[ImageData] = []
    selected_images: List[ImageData] = []
    image_clusters: List[ImageCluster] = Field(default_factory=list)
    gpx_file: str = ""
    gpx_stats: Optional[GPXStats] = None
    gpx_pauses: List[dict] = []
    elevation_profile_path: Optional[str] = None
    # Metadaten als flache typisierte Felder (ersetzt Dict[str, Any])
    article_id: Optional[int] = None
    photobook_id: Optional[int] = None
    map_image_path: Optional[str] = None
    selected_image_count: Optional[int] = None
    selected_images_list: List[str] = Field(default_factory=list)
    blog_post: Optional[BlogPostResult] = None
    notes: Optional[str] = None
    weather: Optional[WeatherInfo] = None
    poi_list: List[POI] = Field(default_factory=list)
    enrichment_context: EnrichmentContext = Field(default_factory=EnrichmentContext)
    model: str = "gemma4:26b-ctx128k"
    output_dir: str = "output"
    output_config: OutputConfig = Field(default_factory=OutputConfig)
    photobook_images: List[ImageData] = []
    photobook_plan: Optional[PhotobookPlan] = None
    photobook_pages: List[PageDescription] = []
    photobook_html: Optional[str] = None
    photobook_html_path: Optional[str] = None  # Pfad zur gespeicherten HTML-Datei
    photobook_timestamp: Optional[str] = None  # Wird von render_photobook_node gesetzt
    photobook_pdf_path: Optional[str] = None

