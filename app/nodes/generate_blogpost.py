# app/nodes/generate_blog_post.py
import logging

from app.state import AppState, BlogPostResult
from app.services.blog_generator import generate_blog_post

logger = logging.getLogger(__name__)


def generate_blog_post_node(state: AppState) -> AppState:
    """
    Generiert einen Blogpost basierend auf dem AppState.
    
    Nutzt:
        - state.gpx_stats: GPX-Statistiken
        - state.images: Liste der Bilder
        - state.map_image_path: Pfad zur Kartenabbildung
    
    Fügt hinzu:
        - state.blog_post: Ergebnis des Blog-Generators (Markdown, HTML, etc.)
    """
    logger.info("Starting blog post generation...")
    
    # Validierung: nutze selected_images wenn vorhanden, sonst alle
    images = state.selected_images if state.selected_images else state.images
    if not images:
        logger.warning("No images available for blog generation.")
        state.blog_post = BlogPostResult(success=False, error="No images")
        return state

    if not state.gpx_stats:
        logger.warning("No GPX stats available for blog generation.")
        state.blog_post = BlogPostResult(success=False, error="No GPX stats")
        return state

    map_image_path = state.map_image_path
    logger.info("Using %s images for blog generation", len(images))

    try:
        result = generate_blog_post(
            images=[img.model_dump() for img in images],
            map_image_path=map_image_path,
            elevation_profile_path=state.elevation_profile_path,
            gpx_stats=state.gpx_stats.model_dump() if hasattr(state.gpx_stats, "model_dump") else state.gpx_stats,
            notes=state.notes,
            model=state.model,
            enrichment_context=state.enrichment_context,
            weather=state.weather,
            poi_list=state.poi_list,
            output_config=state.output_config,
        )

        state.selected_images_list = result.selected_images
        state.blog_post = result
        
        if result.success:
            logger.info("Blog post generated successfully!")
            logger.info("   - Markdown length: %s", len(result.markdown or ''))
            logger.info("   - HTML length: %s", len(result.html or ''))
            logger.info("   - Selected images: %s", len(result.selected_images))
        else:
            logger.error("Blog generation failed: %s", result.error)
            
    except Exception as e:
        logger.error("Error generating blog post: %s", e)
        state.blog_post = BlogPostResult(
            success=False,
            error=str(e),
            markdown="",
            html="",
            selected_images=[],
            descriptions={},
        )
    
    return state