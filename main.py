from app.graph import build_graph

def main():
    graph = build_graph()
    
    result = graph.invoke({})
    print("Final State:", result)

if __name__ == "__main__":    
    main()


