# app/nodes/generate_blog_post.py
from app.state import AppState
from app.services.blog_generator import generate_blog_post

def generate_blog_post_node(state: AppState) -> AppState:
    """
    Generiert einen Blogpost basierend auf dem AppState.
    
    Nutzt:
        - state.gpx_stats: GPX-Statistiken
        - state.images: Liste der Bilder
        - state.metadata: Metadaten (z.B. map_image_path)
    
    Fügt hinzu:
        - state.blog_post: Ergebnis des Blog-Generators (Markdown, HTML, etc.)
    """
    print("📝 Starting blog post generation...")
    
    # Validierung: nutze selected_images wenn vorhanden, sonst alle
    images = state.selected_images if state.selected_images else state.images
    if not images:
        print("⚠️ No images available for blog generation.")
        state.blog_post = {"success": False, "error": "No images"}
        return state

    if not state.gpx_stats:
        print("⚠️ No GPX stats available for blog generation.")
        state.blog_post = {"success": False, "error": "No GPX stats"}
        return state

    map_image_path = state.metadata.get("enriched_map_image_path")
    print(f"📸 Using {len(images)} images for blog generation")

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

        state.metadata["selected_images"] = result.get("selected_images", [])
        state.blog_post = result
        
        if result.get("success"):
            print("✅ Blog post generated successfully!")
            print(f"   - Markdown length: {len(result.get('markdown', ''))}")
            print(f"   - HTML length: {len(result.get('html', ''))}")
            print(f"   - Selected images: {len(result.get('selected_images', []))}")
        else:
            print(f"❌ Blog generation failed: {result.get('error')}")
            
    except Exception as e:
        print(f"❌ Error generating blog post: {e}")
        state.blog_post = {
            "success": False,
            "error": str(e),
            "markdown": "",
            "html": "",
            "selected_images": [],
            "descriptions": {}
        }
    
    return state