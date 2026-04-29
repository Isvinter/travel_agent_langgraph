from app.state import AppState
from app.services.gpx_analytics import analyze_track
from app.services.generate_elevation_profile import generate_elevation_profile

def process_gpx_node(state: AppState) -> AppState:
    """Process GPX file using existing services."""
    
    gpx_file = state.gpx_file
    print(f"DEBUG: GPX file = {gpx_file}")
    
    if not gpx_file:
        print("DEBUG: No GPX file provided, returning early")
        return state
    
    try:
        print("DEBUG: Starting GPX analysis...")
        # Use existing analyze_track function
        stats, pauses = analyze_track(gpx_file)
        
        print(f"DEBUG: Analysis complete - distance: {stats.total_distance_m}m")
        
        # Use existing elevation profile generator
        elevation_path = "output/elevation_profile.png"
        print(f"DEBUG: Generating elevation profile to {elevation_path}")
        generate_elevation_profile(stats.points, elevation_path)
        
        # Create metadata
        metadata = {
            "file": gpx_file,
            "distance_km": round(stats.total_distance_m / 1000, 2),
            "elevation_gain_m": round(stats.elevation_gain_m, 2),
            "elevation_loss_m": round(stats.elevation_loss_m, 2),
            "avg_speed_kmh": round(stats.avg_speed_kmh, 2),
            "max_speed_kmh": round(stats.max_speed_kmh, 2),
            "total_points": len(stats.points),
            "pauses_count": len(pauses),
            "elevation_profile": elevation_path
        }
        
        print("DEBUG: Returning with metadata")
        return AppState(
            images=state.images,
            selected_images=state.selected_images,
            image_clusters=state.image_clusters,
            gpx_file=state.gpx_file,
            gpx_stats=stats,
            gpx_pauses=pauses,
            elevation_profile_path=elevation_path,
            metadata=metadata,
            blog_post=state.blog_post,
            notes=state.notes,
            model=state.model,
        )
    
    except Exception as e:
        print(f"DEBUG: Error processing GPX: {e}")
        import traceback
        traceback.print_exc()
        return state
