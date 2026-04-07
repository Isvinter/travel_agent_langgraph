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

if __name__ == "__main__":    
    main()
