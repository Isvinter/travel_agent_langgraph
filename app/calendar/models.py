"""Kalender-Konfiguration und Ergebnisse (Pydantic)."""
from typing import Optional
from pydantic import BaseModel, Field


CALENDAR_PRESETS = {
    "mixed": "Gemischt",
    "nature_landscape": "Natur & Landschaft",
    "people": "Menschen",
    "culture": "Kultur & Architektur",
}

CALENDAR_PRESET_CRITERIA = {
    "mixed": "starke Motive, gute Belichtung, landschaftliche Vielfalt, verschiedene Perspektiven und Stimmungen",
    "nature_landscape": "Fokussiere auf Landschaften, Natur, Panoramen, Pflanzen, Tiere. Wähle saisonal passende Motive.",
    "people": "Fokussiere auf Menschen: Porträts, Gruppen, emotionale Momente. Vermeide reine Landschaftsbilder ohne Menschen.",
    "culture": "Fokussiere auf Architektur, Stadtansichten, Denkmäler, kulturelle Motive.",
}


class CalendarConfig(BaseModel):
    """Eingabe-Konfiguration für die Kalender-Generierung."""
    preset: str = Field(default="mixed", description="Thematisches Preset")
    year: int = Field(..., ge=2000, le=2100, description="Kalenderjahr")
    custom_instructions: Optional[str] = Field(default=None, description="Freitext-Anweisungen an das LLM")
    model: str = Field(default="gemma4:26b-ctx128k")


class MonthSlot(BaseModel):
    """Ein Bild-Slot innerhalb einer Monatsseite."""
    slot_id: str
    image_index: int  # Index in der ausgewählten Bildliste


class CalendarMonthPage(BaseModel):
    """Eine Monatsseite im Kalender."""
    month: int  # 1–12 (0=Cover)
    month_name: str
    preset_id: str
    slots: list[MonthSlot] = []


class CalendarResult(BaseModel):
    """Ergebnis der Kalender-Generierung."""
    year: int
    preset: str
    pages: list[CalendarMonthPage]
    html_content: str = ""
    pdf_bytes: Optional[bytes] = None
    selected_image_count: int = 0
