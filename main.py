from app.graph import build_graph

def main():
    graph = build_graph()
    
    # Set the GPX file path
    initial_state = {
        "gpx_file": "/home/stephan-zeibig/Coding/travel_agent_langgraph/data/gpx/Tour.gpx",
        "gpx_stats": None,
        "gpx_pauses": [],
        "elevation_profile_path": None,
        "metadata": {},
        "images": []
    }
    
    result = graph.invoke(initial_state)
    
    print("\n" + "="*50)
    print("GPX ANALYSIS RESULTS")
    print("="*50)
    
    if result.get("metadata"):
        for key, value in result["metadata"].items():
            print(f"{key}: {value}")
    else:
        print("No metadata generated.")
    
    if result.get("gpx_pauses"):
        print(f"\nDetected {len(result['gpx_pauses'])} pause(s):")
        for i, pause in enumerate(result["gpx_pauses"], 1):
            print(f"  Pause {i}: {pause.get('duration_minutes')} min")
    
    # Display loaded images
    print("\n" + "="*50)
    print("IMAGE PROCESSING RESULTS")
    print("="*50)
    
    if result.get("images"):
        print(f"\nLoaded {len(result['images'])} images:")
        for i, image in enumerate(result["images"][:5], 1):  # Show first 5
            print(f"  {i}. {image.path}")
            if image.timestamp:
                print(f"     Timestamp: {image.timestamp}")
            if image.latitude and image.longitude:
                print(f"     Location: {image.latitude}, {image.longitude}")
        
        if len(result["images"]) > 5:
            print(f"  ... and {len(result['images']) - 5} more images")
    else:
        print("No images were loaded.")

if __name__ == "__main__":    
    main()
