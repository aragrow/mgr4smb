"""
Knowledge Worker - Retrieves company context from embedded MongoDB collection

Provides:
- Company information (business details, contact info)
- Service descriptions (residential, commercial, specialty)
- Sales vs Support examples
- Resolution approaches

Uses MongoDB's vector search to find relevant knowledge based on query.
"""

import logging
from typing import List, Dict, Any, Optional
from google import genai
from src.workers.db_worker.mongo_client import MongoDBClient
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class KnowledgeClient:
    """
    Client for retrieving company knowledge from MongoDB collection

    Uses semantic search to find relevant company information,
    service descriptions, examples, and resolution approaches.
    """

    def __init__(self):
        """Initialize knowledge client"""
        self.settings = get_settings()
        self.collection_name = "knowledge_base"

        # Initialize Google Gemini client for embeddings
        self.genai_client = genai.Client(api_key=self.settings.google_api_key)

    async def get_company_context(self) -> Optional[Dict[str, Any]]:
        """
        Get company context information

        **USE CASE:** When you need to include company details in responses
        Examples: "Who are we?", "What's your phone number?", "Where are you located?"

        Returns:
            Dict with company information:
            - name: Company name (e.g., "Jill of All Trades Cleaning Inc.")
            - tagline: Business tagline
            - location: Physical address
            - phone: Contact phone number
            - service_area: Geographic coverage area
            - type: "company_context"

        Example:
            context = await client.get_company_context()
            print(f"Company: {context['name']}")
            print(f"Phone: {context['phone']}")
            print(f"Service Area: {context['service_area']}")
        """
        try:
            db = MongoDBClient.get_database()
            collection = db[self.collection_name]

            result = await collection.find_one({"type": "company_context"})

            if result:
                logger.info("Retrieved company context")
                return result
            else:
                logger.warning("Company context not found in knowledge base")
                return None

        except Exception as e:
            logger.error(f"Error retrieving company context: {e}", exc_info=True)
            return None

    async def get_services(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get service descriptions

        **USE CASE:** When customer asks "What services do you offer?" or needs pricing/details
        Examples: "Do you do move-out cleaning?", "What's included in deep cleaning?", "Do you clean offices?"

        Args:
            category: Optional filter by category
                - "residential": Home cleaning services
                - "commercial": Office/business cleaning
                - "specialty": Move-out, post-construction, etc.
                - None: All services

        Returns:
            List of service dictionaries:
            - type: "service"
            - title: Service name
            - category: "residential", "commercial", or "specialty"
            - description: What's included
            - estimated_time: Typical duration
            - pricing_notes: Pricing guidance

        Example:
            services = await client.get_services(category="residential")
            for service in services:
                print(f"{service['title']}: {service['description']}")
        """
        try:
            db = MongoDBClient.get_database()
            collection = db[self.collection_name]

            query = {"type": "service"}
            if category:
                query["category"] = category

            results = await collection.find(query).to_list(length=100)

            logger.info(f"Retrieved {len(results)} services (category={category})")
            return results

        except Exception as e:
            logger.error(f"Error retrieving services: {e}", exc_info=True)
            return []

    async def get_examples(self, example_type: str) -> List[Dict[str, Any]]:
        """
        Get examples (sales vs support, routing, etc.)

        **USE CASE:** When agents need reference examples for classification/routing decisions
        Used internally by agents to understand patterns and make better routing decisions

        Args:
            example_type: Type of example to retrieve
                - "sales_vs_support": Examples distinguishing sales from support inquiries
                - "routing": Examples of correct agent routing
                - "response_tone": Examples of appropriate response styles

        Returns:
            List of example dictionaries:
            - type: "example"
            - example_type: Category of example
            - title: Example title
            - description: Detailed explanation
            - reasoning: Why this classification was made
            - correct_agent: Which agent should handle (for routing examples)

        Example:
            examples = await client.get_examples("sales_vs_support")
            for ex in examples:
                print(f"{ex['title']}: {ex['reasoning']}")

        **Note:** Primarily used by agent prompts and internal logic, not customer-facing
        """
        try:
            db = MongoDBClient.get_database()
            collection = db[self.collection_name]

            results = await collection.find({
                "type": "example",
                "example_type": example_type
            }).to_list(length=100)

            logger.info(f"Retrieved {len(results)} examples (type={example_type})")
            return results

        except Exception as e:
            logger.error(f"Error retrieving examples: {e}", exc_info=True)
            return []

    async def get_resolution_approaches(self, issue_category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get resolution approaches for support issues

        **USE CASE:** When customer service agent needs guidance on resolving common issues
        Examples: Missed appointments, quality concerns, billing disputes, scheduling conflicts

        Args:
            issue_category: Optional filter by category
                - "missed_appointment": Cleaner didn't show up
                - "quality_concern": Customer unhappy with cleaning quality
                - "billing_dispute": Invoice/payment disagreement
                - "scheduling_conflict": Date/time issues
                - "property_damage": Damage claim
                - None: All resolution approaches

        Returns:
            List of resolution approach dictionaries:
            - type: "resolution_approach"
            - issue_category: Type of issue
            - title: Approach name
            - description: Step-by-step resolution guide
            - estimated_time: How long resolution typically takes
            - escalation_criteria: When to escalate to manager

        Example:
            approaches = await client.get_resolution_approaches("missed_appointment")
            for approach in approaches:
                print(f"{approach['title']}: {approach['description']}")

        **Note:** Used by customer_service_agent to provide consistent, effective resolutions
        """
        try:
            db = MongoDBClient.get_database()
            collection = db[self.collection_name]

            query = {"type": "resolution_approach"}
            if issue_category:
                query["issue_category"] = issue_category

            results = await collection.find(query).to_list(length=100)

            logger.info(f"Retrieved {len(results)} resolution approaches (category={issue_category})")
            return results

        except Exception as e:
            logger.error(f"Error retrieving resolution approaches: {e}", exc_info=True)
            return []

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for query text using Google Gemini

        **USE CASE:** Internal function for converting text to vector embeddings
        Used by vector_search() to enable semantic similarity search

        Args:
            text: Query text to embed (e.g., "How do I schedule a deep clean?")

        Returns:
            Embedding vector (list of floats, typically 768 dimensions)
            Used for semantic similarity comparison in MongoDB Atlas Vector Search

        Example:
            embedding = client.generate_embedding("What services do you offer?")
            # Returns: [0.123, -0.456, 0.789, ...] (768 values)

        **Note:** Internal helper function - agents should use vector_search() directly
        """
        result = self.genai_client.models.embed_content(
            model=self.settings.embedding_model,
            contents=text,
        )

        return result.embeddings[0].values

    async def vector_search(
        self,
        query: str,
        knowledge_type: Optional[str] = None,
        limit: int = 5,
        min_score: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search using MongoDB Atlas Vector Search

        **USE CASE:** When you need to find relevant knowledge based on semantic meaning
        Examples: "How to handle missed appointments?", "What's included in deep cleaning?", "Office cleaning options?"

        This uses AI embeddings to find contextually relevant knowledge even when exact keywords don't match

        Args:
            query: Natural language query (e.g., "customer wants eco-friendly cleaning")
            knowledge_type: Optional filter by type
                - "company_context": Company information only
                - "service": Service descriptions only
                - "example": Example scenarios only
                - "resolution_approach": Resolution guides only
                - None: Search all knowledge types
            limit: Maximum number of results to return (default 5)
            min_score: Minimum similarity score 0-1 (default 0.7 = 70% match)
                - 0.9-1.0: Very high relevance
                - 0.7-0.9: Good relevance
                - 0.5-0.7: Moderate relevance
                - <0.5: Low relevance (filtered out by default)

        Returns:
            List of matching knowledge items with scores:
            - type: Knowledge type
            - title: Item title
            - description: Detailed description
            - content: Full content
            - category: Category if applicable
            - score: Similarity score (0-1, higher = more relevant)

        Example:
            results = await client.vector_search(
                query="customer unhappy with cleaning quality",
                knowledge_type="resolution_approach",
                limit=3,
                min_score=0.75
            )
            for result in results:
                print(f"[{result['score']:.2f}] {result['title']}")
                print(f"  {result['description']}")

        **Note:** Preferred over search_knowledge() for semantic/contextual search
        """
        try:
            db = MongoDBClient.get_database()
            collection = db[self.collection_name]

            # Generate embedding for query
            query_embedding = self.generate_embedding(query)

            # Build vector search pipeline
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": self.settings.knowledge_vector_index_name,
                        "path": "embedding",
                        "queryVector": query_embedding,
                        "numCandidates": limit * 10,
                        "limit": limit,
                    }
                },
                {
                    "$project": {
                        "type": 1,
                        "title": 1,
                        "description": 1,
                        "content": 1,
                        "category": 1,
                        "example_type": 1,
                        "issue_category": 1,
                        "estimated_time": 1,
                        "reasoning": 1,
                        "score": {"$meta": "vectorSearchScore"},
                    }
                },
                {"$match": {"score": {"$gte": min_score}}},
            ]

            # Add type filter if specified
            if knowledge_type:
                pipeline.append({"$match": {"type": knowledge_type}})

            results = []
            async for doc in collection.aggregate(pipeline):
                # Remove MongoDB _id from results
                if "_id" in doc:
                    del doc["_id"]
                results.append(doc)

            logger.info(f"Vector search for '{query}' returned {len(results)} results (type={knowledge_type})")
            return results

        except Exception as e:
            logger.error(f"Error in vector search: {e}", exc_info=True)
            return []

    async def search_knowledge(self, query: str, knowledge_type: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search knowledge base using text search (fallback method)

        **USE CASE:** Simple keyword-based search when you have exact terms to match
        Examples: Search for "move-out", "commercial", "hourly rate"

        Args:
            query: Search query with specific keywords (e.g., "move-out cleaning")
            knowledge_type: Optional filter by type
                - "company_context": Company information only
                - "service": Service descriptions only
                - "example": Example scenarios only
                - "resolution_approach": Resolution guides only
                - None: Search all knowledge types
            limit: Maximum number of results to return (default 5)

        Returns:
            List of matching knowledge items (exact keyword matches):
            - type: Knowledge type
            - title: Item title
            - description: Detailed description
            - content: Full content
            - category: Category if applicable
            - No score (exact match only)

        Example:
            results = await client.search_knowledge(
                query="deep clean",
                knowledge_type="service",
                limit=3
            )
            for result in results:
                print(f"{result['title']}: {result['description']}")

        **Note:** For semantic/contextual search, use vector_search() instead
        This method only matches exact keywords, not meaning/context
        """
        try:
            db = MongoDBClient.get_database()
            collection = db[self.collection_name]

            # Build search query
            search_filter = {}
            if knowledge_type:
                search_filter["type"] = knowledge_type

            # Use text search if available, otherwise use regex
            if query:
                search_filter["$or"] = [
                    {"title": {"$regex": query, "$options": "i"}},
                    {"description": {"$regex": query, "$options": "i"}},
                    {"content": {"$regex": query, "$options": "i"}}
                ]

            results = await collection.find(search_filter).limit(limit).to_list(length=limit)

            # Remove MongoDB _id and embedding from results
            for result in results:
                if "_id" in result:
                    del result["_id"]
                if "embedding" in result:
                    del result["embedding"]

            logger.info(f"Text search for '{query}' returned {len(results)} results (type={knowledge_type})")
            return results

        except Exception as e:
            logger.error(f"Error searching knowledge base: {e}", exc_info=True)
            return []
