import os
import json
from typing import Dict, Any, List
import logging
from datetime import date
from pydantic import BaseModel
from dotenv import load_dotenv, find_dotenv

# Reduce noisy / slow optional dependencies during import
os.environ.setdefault("CHROMADB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

load_dotenv(find_dotenv())


class RAGResult(BaseModel):
    """Pydantic model for RAG query results"""
    query: str
    results: List[Dict[str, Any]]
    total_results: int
    top_match_confidence: float


class RAGRetriever:
    """
    3rd Agent: RAG (Retrieval-Augmented Generation) Agent
    Transforms queries to vectors and searches the knowledge base for similar documents.
    """

    def __init__(self, collection_name: str = "support_client_docs", db_path: str = "chromadb"):
        """
        Initialize the RAG Retriever
        
        Args:
            collection_name: Name of the ChromaDB collection
            db_path: Path to ChromaDB database
        """
        self.logger = logging.getLogger(__name__)
        self.collection_name = collection_name
        self.db_path = db_path
        
        try:
            # Lazy imports to avoid heavy optional deps at module import time
            from sentence_transformers import SentenceTransformer
            import chromadb

            # Initialize embedding model
            self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            self.logger.info("Embedding model loaded successfully")
            
            # Connect to ChromaDB
            self.client = chromadb.PersistentClient(path=db_path)
            self.collection = self.client.get_collection(name=collection_name)
            self.logger.info(f"Connected to ChromaDB collection: {collection_name}")
        except Exception as e:
            self.logger.error(f"Failed to initialize RAG Retriever: {str(e)}")
            raise

    async def retrieve(
        self,
        query: str,
        n_results: int = 5,
        min_confidence: float = 0.0
    ) -> Dict[str, Any]:
        """
        Retrieve relevant documents from knowledge base for a given query
        
        Args:
            query: The search query
            n_results: Number of results to return (default: 5)
            min_confidence: Minimum confidence threshold (0.0-1.0)
            
        Returns:
            Dict containing retrieval results with confidence scores
        """
        try:
            self.logger.info(f"Retrieving documents for query: {query[:100]}...")
            
            # Encode the query to embedding
            query_embedding = self.embedding_model.encode([query], convert_to_numpy=True)[0].tolist()
            
            # Query ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            
            # Process results with confidence scores
            processed_results = self._process_results(results, min_confidence)
            
            # Create structured response
            retrieval_result = {
                "query": query,
                "results": processed_results["documents"],
                "total_results": len(processed_results["documents"]),
                "top_match_confidence": processed_results["top_confidence"],
                "retrieved_at": self._get_timestamp(),
                "retrieval_method": "semantic_search"
            }
            
            self.logger.info(
                f"Retrieved {len(processed_results['documents'])} documents. "
                f"Top confidence: {processed_results['top_confidence']:.2%}"
            )
            
            return retrieval_result
            
        except Exception as e:
            self.logger.error(f"Retrieval failed: {str(e)}")
            return self._create_default_response(query)

    def _process_results(
        self,
        raw_results: Dict[str, Any],
        min_confidence: float
    ) -> Dict[str, Any]:
        """
        Process raw ChromaDB results and calculate confidence scores
        
        Args:
            raw_results: Raw results from ChromaDB query
            min_confidence: Minimum confidence threshold
            
        Returns:
            Dict with processed documents and confidence scores
        """
        processed_documents = []
        confidences = []
        
        if raw_results.get("documents") and raw_results["documents"][0]:
            for doc, distance in zip(raw_results["documents"][0], raw_results["distances"][0]):
                # Convert L2 distance to cosine similarity
                # For normalized vectors: cosine_similarity = 1 - (distance^2 / 2)
                cosine_similarity = max(0, 1 - (distance ** 2) / 2)
                confidence = cosine_similarity
                
                # Filter by minimum confidence
                if confidence >= min_confidence:
                    processed_documents.append({
                        "content": doc,
                        "confidence": confidence,
                        "confidence_percentage": confidence * 100
                    })
                    confidences.append(confidence)
        
        top_confidence = max(confidences) if confidences else 0.0
        
        return {
            "documents": processed_documents,
            "top_confidence": top_confidence,
            "total_filtered": len(processed_documents)
        }

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        from datetime import datetime
        return datetime.now().isoformat()

    def _create_default_response(self, query: str) -> Dict[str, Any]:
        """Create a default response when retrieval fails"""
        return {
            "query": query,
            "results": [],
            "total_results": 0,
            "top_match_confidence": 0.0,
            "retrieved_at": self._get_timestamp(),
            "retrieval_method": "semantic_search",
            "error": "Failed to retrieve documents"
        }

    def get_retrieval_report(self, retrieval_result: Dict[str, Any]) -> str:
        """Generate a human-readable retrieval report"""
        report = f"""
        📚 RAG RETRIEVAL REPORT
        {'=' * 60}
        
        Query: {retrieval_result.get('query', 'N/A')}
        
        Results Found: {retrieval_result.get('total_results', 0)}
        Top Match Confidence: {retrieval_result.get('top_match_confidence', 0):.1%}
        
        {'─' * 60}
        """
        
        results = retrieval_result.get('results', [])
        if results:
            for i, result in enumerate(results, 1):
                report += f"\n        Result {i}:"
                report += f"\n        Confidence: {result.get('confidence_percentage', 0):.2f}%"
                report += f"\n        Content: {result.get('content', 'N/A')[:150]}..."
                report += f"\n        {'─' * 60}\n"
        else:
            report += f"\n        No results found\n        {'─' * 60}\n"
        
        report += f"\n        {'=' * 60}\n        "
        return report