"""
Knowledge Enrichment Helper

Provides helper methods for agents to enrich their prompts with relevant
knowledge base context using vector semantic search.
"""

import logging
from typing import Dict, Any, Optional, List
from src.workers.knowledge_worker.knowledge_client import KnowledgeClient

logger = logging.getLogger(__name__)


class KnowledgeEnrichment:
    """
    Helper class for enriching agent prompts with knowledge base context

    Uses vector semantic search to find relevant information based on
    the conversation context (subject + body).
    """

    def __init__(self):
        """Initialize knowledge enrichment helper"""
        self.knowledge_client = KnowledgeClient()

    async def get_company_context_formatted(self) -> str:
        """
        Get formatted company context for agent prompts

        Returns:
            Formatted string with company information
        """
        context = await self.knowledge_client.get_company_context()

        if not context or 'content' not in context:
            return "Company information not available"

        content = context['content']

        return f"""**COMPANY CONTEXT:**
- Business: {content.get('business_name', 'N/A')} (since {content.get('established', 'N/A')}, {content.get('experience_years', 'N/A')} years experience)
- Tagline: "{content.get('tagline', 'N/A')}"
- Service Area: {content.get('service_area', 'N/A')}
- Phone: {content.get('phone', 'N/A')}
- Location: {content.get('location', 'N/A')}"""

    async def get_relevant_services(self, query: str, limit: int = 3) -> str:
        """
        Get relevant services based on conversation context

        Args:
            query: Conversation context (subject + body)
            limit: Maximum number of services to return

        Returns:
            Formatted string with relevant services
        """
        try:
            services = await self.knowledge_client.vector_search(
                query=query,
                knowledge_type="service",
                limit=limit,
                min_score=0.6
            )

            if not services:
                return ""

            formatted_services = ["**RELEVANT SERVICES:**"]
            for service in services:
                score = service.get('score', 0)
                category = service.get('category', 'N/A')
                title = service.get('title', 'N/A')
                description = service.get('description', 'N/A')
                formatted_services.append(f"- [{category.upper()}] {title}: {description} (relevance: {score:.2f})")

            return "\n".join(formatted_services)

        except Exception as e:
            logger.error(f"Error getting relevant services: {e}", exc_info=True)
            return ""

    async def get_relevant_examples(self, query: str, example_type: str = "sales_vs_support", limit: int = 3) -> str:
        """
        Get relevant examples based on conversation context

        Args:
            query: Conversation context (subject + body)
            example_type: Type of examples to search for
            limit: Maximum number of examples to return

        Returns:
            Formatted string with relevant examples
        """
        try:
            examples = await self.knowledge_client.vector_search(
                query=query,
                knowledge_type="example",
                limit=limit,
                min_score=0.6
            )

            # Filter by example_type
            examples = [ex for ex in examples if ex.get('example_type') == example_type]

            if not examples:
                return ""

            formatted_examples = ["**RELEVANT EXAMPLES:**"]
            for example in examples:
                score = example.get('score', 0)
                category = example.get('category', 'N/A')
                title = example.get('title', 'N/A')
                reasoning = example.get('reasoning', 'N/A')
                formatted_examples.append(f"- [{category}] {title}")
                formatted_examples.append(f"  Reasoning: {reasoning} (relevance: {score:.2f})")

            return "\n".join(formatted_examples)

        except Exception as e:
            logger.error(f"Error getting relevant examples: {e}", exc_info=True)
            return ""

    async def get_relevant_resolution_approaches(self, query: str, limit: int = 2) -> str:
        """
        Get relevant resolution approaches based on conversation context

        Args:
            query: Conversation context (subject + body)
            limit: Maximum number of approaches to return

        Returns:
            Formatted string with relevant resolution approaches
        """
        try:
            approaches = await self.knowledge_client.vector_search(
                query=query,
                knowledge_type="resolution_approach",
                limit=limit,
                min_score=0.6
            )

            if not approaches:
                return ""

            formatted_approaches = ["**SUGGESTED RESOLUTION APPROACHES:**"]
            for approach in approaches:
                score = approach.get('score', 0)
                title = approach.get('title', 'N/A')
                description = approach.get('description', 'N/A')
                content = approach.get('content', 'N/A')
                estimated_time = approach.get('estimated_time', 'N/A')

                formatted_approaches.append(f"\n{title} (ETA: {estimated_time}, relevance: {score:.2f})")
                formatted_approaches.append(f"  {description}")
                formatted_approaches.append(f"  Steps: {content}")

            return "\n".join(formatted_approaches)

        except Exception as e:
            logger.error(f"Error getting resolution approaches: {e}", exc_info=True)
            return ""

    async def enrich_for_orchestrator(self, subject: str, body: str) -> Dict[str, Any]:
        """
        Enrich context for orchestrator when answering customer questions directly

        Fetches company context and relevant services/resolution approaches based
        on the customer's message so the orchestrator can answer questions about
        the company, services, pricing, and support topics.

        Args:
            subject: Message subject (empty string for chat/form messages)
            body: Customer message body

        Returns:
            Dict with company context and relevant knowledge
        """
        query = f"{subject}\n{body}".strip()

        company_context = await self.get_company_context_formatted()
        relevant_services = await self.get_relevant_services(query, limit=5)
        resolution_approaches = await self.get_relevant_resolution_approaches(query, limit=2)

        return {
            "company_context": company_context,
            "relevant_services": relevant_services,
            "resolution_approaches": resolution_approaches,
            "enrichment_query": query
        }

    async def enrich_for_lead_agent(self, subject: str, body: str) -> Dict[str, Any]:
        """
        Enrich context for lead agent (new potential customers)

        Args:
            subject: Email subject
            body: Email body

        Returns:
            Dict with company context and relevant services
        """
        query = f"{subject}\n{body}"

        company_context = await self.get_company_context_formatted()
        relevant_services = await self.get_relevant_services(query, limit=5)

        return {
            "company_context": company_context,
            "relevant_services": relevant_services,
            "enrichment_query": query
        }

    async def enrich_for_sales_manager(self, subject: str, body: str) -> Dict[str, Any]:
        """
        Enrich context for sales manager agent (upsells, quotes, pricing)

        Args:
            subject: Email subject
            body: Email body

        Returns:
            Dict with company context, services, and sales examples
        """
        query = f"{subject}\n{body}"

        company_context = await self.get_company_context_formatted()
        relevant_services = await self.get_relevant_services(query, limit=5)
        sales_examples = await self.get_relevant_examples(query, example_type="sales_vs_support", limit=3)

        return {
            "company_context": company_context,
            "relevant_services": relevant_services,
            "sales_examples": sales_examples,
            "enrichment_query": query
        }

    async def enrich_for_customer_service(self, subject: str, body: str) -> Dict[str, Any]:
        """
        Enrich context for customer service agent (support, complaints, issues)

        Args:
            subject: Email subject
            body: Email body

        Returns:
            Dict with resolution approaches and support examples
        """
        query = f"{subject}\n{body}"

        resolution_approaches = await self.get_relevant_resolution_approaches(query, limit=2)
        support_examples = await self.get_relevant_examples(query, example_type="sales_vs_support", limit=2)

        return {
            "resolution_approaches": resolution_approaches,
            "support_examples": support_examples,
            "enrichment_query": query
        }

    async def enrich_for_vendor_agent(self, subject: str, body: str) -> Dict[str, Any]:
        """
        Enrich context for vendor agent (cleaning contractors/teams)

        Args:
            subject: Email subject
            body: Email body

        Returns:
            Dict with company context (currently minimal enrichment needed)
        """
        company_context = await self.get_company_context_formatted()

        return {
            "company_context": company_context,
            "enrichment_query": f"{subject}\n{body}"
        }

    def format_enrichment(self, enrichment_data: Dict[str, Any]) -> str:
        """
        Format enrichment data into a string for agent prompts

        Args:
            enrichment_data: Enrichment data from enrich_for_* methods

        Returns:
            Formatted string to inject into agent prompts
        """
        parts = []

        # Add each enrichment section if present and non-empty
        if enrichment_data.get('company_context'):
            parts.append(enrichment_data['company_context'])

        if enrichment_data.get('relevant_services'):
            parts.append(enrichment_data['relevant_services'])

        if enrichment_data.get('sales_examples'):
            parts.append(enrichment_data['sales_examples'])

        if enrichment_data.get('support_examples'):
            parts.append(enrichment_data['support_examples'])

        if enrichment_data.get('resolution_approaches'):
            parts.append(enrichment_data['resolution_approaches'])

        return "\n\n".join(parts) if parts else ""
