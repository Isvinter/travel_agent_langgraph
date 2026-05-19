"""Kalender-Pipeline: Orchestriert den gesamten Generierungs-Flow."""
import logging

from app.config import OLLAMA_BASE_URL
from app.state import ImageData
from app.shared.image_selector import select_images
from app.calendar.layouts import get_total_image_slots
from app.calendar.models import (
    CalendarConfig, CalendarResult,
    CALENDAR_PRESET_CRITERIA,
)
from app.calendar.month_assigner import assign_photos_to_months
from app.calendar.renderer import render_calendar

logger = logging.getLogger(__name__)


def run_calendar_pipeline(
    images: list[ImageData],
    config: CalendarConfig,
    base_url: str = OLLAMA_BASE_URL,
) -> CalendarResult:
    if not images:
        logger.warning("Keine Bilder vorhanden, generiere leeren Kalender")
        from app.calendar.month_assigner import _fallback_assignment
        pages = _fallback_assignment([], config.year)
        html = render_calendar(pages, config.year, [])
        return CalendarResult(
            year=config.year,
            preset=config.preset,
            pages=pages,
            html_content=html,
            selected_image_count=0,
        )

    criteria = CALENDAR_PRESET_CRITERIA.get(
        config.preset,
        CALENDAR_PRESET_CRITERIA["mixed"],
    )

    target_slots = get_total_image_slots()
    selection_target = min(target_slots + 5, len(images))

    logger.info("Stufe 1: Bildauswahl (%d Fotos → ~%d)", len(images), selection_target)
    selected = select_images(
        images,
        criteria=criteria,
        target_count=selection_target,
        model=config.model,
        base_url=base_url,
        custom_instructions=config.custom_instructions,
    )
    logger.info("Stufe 1 abgeschlossen: %d Fotos ausgewählt", len(selected))

    # Orientierungen der ausgewählten Bilder ermitteln
    from app.calendar.orientation import get_orientations
    orientations = get_orientations([img.path for img in selected])
    logger.info(
        "Orientierungen: %d landscape, %d portrait, %d square",
        orientations.count("landscape"),
        orientations.count("portrait"),
        orientations.count("square"),
    )

    logger.info("Stufe 2: Monats-Zuweisung")
    pages = assign_photos_to_months(
        selected_photos=selected,
        year=config.year,
        preset=config.preset,
        model=config.model,
        base_url=base_url,
        custom_instructions=config.custom_instructions,
        orientations=orientations,
    )
    logger.info("Stufe 2 abgeschlossen: %d Seiten", len(pages))

    # Bildpfade aus den ausgewählten Fotos (nicht allen!), da die
    # image_index-Werte in den MonthSlots auf selected_photos zeigen.
    image_paths = [img.path for img in selected]

    logger.info("Rendering: HTML-Erzeugung")
    html = render_calendar(pages, config.year, image_paths)

    return CalendarResult(
        year=config.year,
        preset=config.preset,
        pages=pages,
        html_content=html,
        selected_image_count=len(selected),
        selected_image_paths=image_paths,
    )
