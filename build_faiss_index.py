import logging
from faiss_rag import build_index_from_json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

if __name__ == "__main__":
    print("Starting FAISS index build process...")
    try:
        build_index_from_json('final_dataset.json')
        print("FAISS index built successfully.")
    except Exception as e:
        print(f"Error building FAISS index: {e}")
