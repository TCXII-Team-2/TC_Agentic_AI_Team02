import os
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

sbert_model = SentenceTransformer("all-MiniLM-L6-v2")

# Connect directly to ChromaDB using the same model
client = chromadb.PersistentClient(path="chromadb")
collection = client.get_collection(name="support_client_docs")

# Query function
query = "how to reset my password?"
query_embedding = sbert_model.encode([query], convert_to_numpy=True)[0].tolist()

# Query ChromaDB directly
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=5
)

# Display results with cosine similarity
print(f"Query: {query}\n")
if results["documents"]:
    for i, (doc, distance) in enumerate(zip(results["documents"][0], results["distances"][0])):
        # Convert distance to cosine similarity (ChromaDB uses L2 distance by default)
        # For normalized vectors: cosine_similarity = 1 - (distance^2 / 2)
        cosine_similarity = 1 - (distance ** 2) / 2
        
        # Calculate confidence percentage
        confidence = cosine_similarity * 100
        
        print(f"Result {i+1}:")
        print(f"  Cosine Similarity: {cosine_similarity:.4f}")
        print(f"  Confidence: {confidence:.2f}%")
        print(f"  Content: {doc}")
        print("-" * 80)
else:
    print("No results found")