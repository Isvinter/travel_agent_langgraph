from typing import List, Optional
from pydantic import BaseModel

class ImageData(BaseModel):
    path: str
    timestamp: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class ImageDataList(BaseModel):
    images: List[ImageData]

