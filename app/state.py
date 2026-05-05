from typing import Dict, Any, List, Literal, Optional
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

AVAILABLE_MODELS = [
    "gemma4:26b-ctx128k",
    "gemma4:31b-ctx112k",
    "qwen3.6:27b-ctx128k",
    "qwen3.6:35b-ctx128k",
]


class PhotobookConfig(BaseModel):
    """Konfiguration fuer die Fotobuch-Ausgabe."""
    photo_count: int = Field(default=16, ge=5, le=24)


class OutputConfig(BaseModel):
    """Konfiguration für die Blog-Ausgabe — vom Benutzer vor Pipeline-Start gesetzt."""
    wildcard_max: int = Field(default=12, ge=1, le=50)
    article_length: Literal["short", "normal", "detailed"] = "normal"
    style_persona: Literal["mountain_veteran", "field_reporter"] = "mountain_veteran"
    pdf_export: bool = False
    mode: Literal["blog", "photobook"] = "blog"
    photobook: PhotobookConfig = PhotobookConfig()


class PageDescription(BaseModel):
    """Seitenbeschreibung — Output des LLM (Pass 2), Input des Renderers."""
    template_id: str
    page_type: str  # "single" | "spread"
    slots: List[Dict[str, Any]] = []


class AppState(BaseModel):
    images: List[ImageData] = []
    selected_images: List[ImageData] = []
    image_clusters: List[Dict[str, Any]] = []
    gpx_file: str = ""
    gpx_stats: Optional[GPXStats] = None
    gpx_pauses: List[dict] = []
    elevation_profile_path: Optional[str] = None
    metadata: Dict[str, Any] = {}
    blog_post: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    weather: Optional[WeatherInfo] = None
    poi_list: List[Dict[str, Any]] = []
    enrichment_context: Dict[str, Any] = {}
    model: str = "gemma4:26b-ctx128k"
    output_config: OutputConfig = OutputConfig()
    photobook_images: List[ImageData] = []
    photobook_plan: Optional[Dict[str, Any]] = None
    photobook_pages: List[PageDescription] = []
    photobook_html: Optional[str] = None
    photobook_pdf_path: Optional[str] = None

