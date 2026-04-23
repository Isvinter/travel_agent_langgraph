from typing import List, Optional
from pydantic import BaseModel
from typing import Dict, Any
from app.services.gpx_analytics import GPXStats

class ImageData(BaseModel):
    path: str
    timestamp: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class ImageDataList(BaseModel):
    images: List[ImageData]

AVAILABLE_MODELS = [
    "gemma4:26b-ctx128k",
    "gemma4:31b-ctx128k",
    "qwen3.6:35b-ctx128k",
]

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
    model: str = "gemma4:26b-ctx128k"
    
