from vector_rag_indexing import query_vector_rag

def main():
    index_name = "nestledata"  # Use the default index name

    print("Nestlé RAG Chatbot (type 'exit' to quit)\n")
    while True:
        user_query = input("You: ").strip()
        if user_query.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break
        try:
            answer = query_vector_rag(user_query, index_name)
            print(f"Bot: {answer}\n")
        except Exception as e:
            print(f"Error: {e}\n")

if __name__ == "__main__":
    main()