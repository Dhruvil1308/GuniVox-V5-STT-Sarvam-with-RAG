"""Quick sanity test for the FAISS RAG pipeline."""
import logging
logging.basicConfig(level=logging.WARNING)  # suppress verbose logs during test

import faiss_rag

print("Loading FAISS index...")
faiss_rag.load_index()

stats = faiss_rag.stats()
print(f"\n=== Index Stats ===")
print(f"  Ready:          {stats['ready']}")
print(f"  Total vectors:  {stats['total_vectors']}")
print(f"  Model:          {stats['model']}")
print(f"  Score threshold:{stats['score_threshold']}")

queries = [
    "BCA computer applications fees",
    "MBA marketing finance",
    "marine engineering nautical science",
    "pharmacy B Pharm",
    "data science cyber security IT",
]

print("\n=== Search Tests ===")
for q in queries:
    results = faiss_rag.search(q, top_k=2)
    print(f"\nQuery: '{q}'  ->  {len(results)} hit(s)")
    for r in results:
        prog = r['record'].get('program', '?')
        inst = r['record'].get('institute', '?')
        fees = r['record'].get('fees', 'N/A')
        print(f"  [{r['score']:.3f}] {prog} ({inst}) | fees={fees}")
        print(f"         voice_ctx: {r['voice_context'][:100]}...")

print("\n=== Context Injection Test ===")
sample_query = "interested in BCA, what are the fees?"
ctx = "\n\n".join(
    f"[score={r['score']:.2f}]\n{r['voice_context']}"
    for r in faiss_rag.search(sample_query, top_k=3)
)
print(f"Query: '{sample_query}'")
print("--- RETRIEVED_CONTEXT ---")
print(ctx or "(no results)")
print("-------------------------")
print("\n✅ FAISS RAG test complete.")
