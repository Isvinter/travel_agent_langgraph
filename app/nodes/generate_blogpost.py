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
    
    # Validierung
    if not state.images:
        print("⚠️ No images available for blog generation.")
        state.blog_post = {"success": False, "error": "No images"}
        return state
    
    if not state.gpx_stats:
        print("⚠️ No GPX stats available for blog generation.")
        state.blog_post = {"success": False, "error": "No GPX stats"}
        return state
    
    # Map-Bildpfad aus Metadata holen
    map_image_path = state.metadata.get("map_image_path")
    
    print(f"📸 Using {len(state.images)} images for blog generation")
    print(f"🗺️ Map image: {map_image_path}")
    
    try:
        # Blogpost generieren
        result = generate_blog_post(
            images=[img.model_dump() for img in state.images],  # Pydantic to dict
            map_image_path=map_image_path,
            gpx_stats=state.gpx_stats.model_dump() if hasattr(state.gpx_stats, 'model_dump') else state.gpx_stats
        )
        
        # Ergebnis im State speichern
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