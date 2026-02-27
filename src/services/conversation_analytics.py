"""
Conversation Analytics Service - Agent performance analysis and reporting

Provides analytics and reporting capabilities for reviewing conversation history,
agent performance, routing patterns, and LLM usage.
"""

import logging
from datetime import datetime as dt, timedelta
from typing import List, Dict, Any, Optional
from src.workers.db_worker.conversation_state_repo import ConversationStateRepository

logger = logging.getLogger(__name__)


class ConversationAnalytics:
    """
    Analytics service for conversation tracking

    Provides methods for analyzing conversation history, agent performance,
    routing patterns, and resource usage.

    Examples:
        analytics = ConversationAnalytics()

        # Get agent performance
        perf = await analytics.get_agent_performance("customer_service_agent")

        # Get routing patterns
        patterns = await analytics.get_routing_patterns()

        # Get LLM usage
        usage = await analytics.get_llm_usage()
    """

    def __init__(self):
        """Initialize with repository"""
        self.repo = ConversationStateRepository()

    async def get_agent_performance(
        self,
        agent_name: str,
        start_date: Optional[dt] = None,
        end_date: Optional[dt] = None,
        channel: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get performance metrics for a specific agent

        Args:
            agent_name: Name of the agent to analyze
            start_date: Start date (defaults to 30 days ago)
            end_date: End date (defaults to now)
            channel: Optional filter by channel

        Returns:
            Dictionary with agent performance metrics
        """
        try:
            if not start_date:
                start_date = dt.utcnow() - timedelta(days=30)
            if not end_date:
                end_date = dt.utcnow()

            # Build query
            query = {
                "created_at": {"$gte": start_date, "$lte": end_date},
                "metadata.agents_involved": agent_name
            }
            if channel:
                query["channel"] = channel

            # Aggregate metrics
            pipeline = [
                {"$match": query},
                {"$group": {
                    "_id": None,
                    "total_conversations": {"$sum": 1},
                    "avg_processing_time": {"$avg": "$metadata.processing_duration_ms"},
                    "avg_llm_calls": {"$avg": "$metadata.llm_calls"},
                    "avg_tokens": {"$avg": "$metadata.total_tokens"},
                    "total_tokens": {"$sum": "$metadata.total_tokens"},
                    "by_status": {"$push": "$status"}
                }}
            ]

            cursor = self.repo.collection.aggregate(pipeline)
            results = await cursor.to_list(length=1)

            if not results:
                return {
                    "agent_name": agent_name,
                    "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
                    "total_conversations": 0
                }

            result = results[0]

            # Calculate status distribution
            statuses = result.get("by_status", [])
            status_dist = {}
            for status in statuses:
                status_dist[status] = status_dist.get(status, 0) + 1

            return {
                "agent_name": agent_name,
                "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
                "channel": channel or "all",
                "total_conversations": result.get("total_conversations", 0),
                "avg_processing_time_ms": int(result.get("avg_processing_time", 0)),
                "avg_llm_calls": round(result.get("avg_llm_calls", 0), 2),
                "avg_tokens_per_conversation": int(result.get("avg_tokens", 0)),
                "total_tokens_used": result.get("total_tokens", 0),
                "status_distribution": status_dist
            }

        except Exception as e:
            logger.error(f"Failed to get agent performance for {agent_name}: {e}", exc_info=True)
            return {"error": str(e)}

    async def get_routing_patterns(
        self,
        start_date: Optional[dt] = None,
        end_date: Optional[dt] = None
    ) -> Dict[str, Any]:
        """
        Analyze routing patterns across conversations

        Args:
            start_date: Start date (defaults to 30 days ago)
            end_date: End date (defaults to now)

        Returns:
            Dictionary with routing pattern analysis
        """
        try:
            if not start_date:
                start_date = dt.utcnow() - timedelta(days=30)
            if not end_date:
                end_date = dt.utcnow()

            # Get all conversations in period
            query = {"created_at": {"$gte": start_date, "$lte": end_date}}
            cursor = self.repo.collection.find(query)
            conversations = await cursor.to_list(length=None)

            # Analyze routing paths
            routing_paths = {}
            agent_frequencies = {}

            for conv in conversations:
                agents = conv.get("metadata", {}).get("agents_involved", [])

                # Count agent frequency
                for agent in agents:
                    agent_frequencies[agent] = agent_frequencies.get(agent, 0) + 1

                # Build routing path
                if agents:
                    path = " → ".join(agents)
                    routing_paths[path] = routing_paths.get(path, 0) + 1

            # Sort by frequency
            sorted_paths = sorted(routing_paths.items(), key=lambda x: x[1], reverse=True)
            sorted_agents = sorted(agent_frequencies.items(), key=lambda x: x[1], reverse=True)

            return {
                "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
                "total_conversations": len(conversations),
                "routing_paths": dict(sorted_paths[:20]),  # Top 20 paths
                "agent_frequencies": dict(sorted_agents),
                "unique_paths": len(routing_paths),
                "most_common_path": sorted_paths[0] if sorted_paths else None
            }

        except Exception as e:
            logger.error(f"Failed to get routing patterns: {e}", exc_info=True)
            return {"error": str(e)}

    async def get_llm_usage(
        self,
        start_date: Optional[dt] = None,
        end_date: Optional[dt] = None,
        group_by: str = "agent"
    ) -> Dict[str, Any]:
        """
        Analyze LLM usage and costs

        Args:
            start_date: Start date (defaults to 30 days ago)
            end_date: End date (defaults to now)
            group_by: Group results by "agent", "day", or "model" (default: agent)

        Returns:
            Dictionary with LLM usage analysis
        """
        try:
            if not start_date:
                start_date = dt.utcnow() - timedelta(days=30)
            if not end_date:
                end_date = dt.utcnow()

            # Get all conversations in period
            query = {"created_at": {"$gte": start_date, "$lte": end_date}}
            cursor = self.repo.collection.find(query)
            conversations = await cursor.to_list(length=None)

            # Analyze LLM calls from events
            llm_usage = {}
            total_tokens = 0
            total_llm_calls = 0

            for conv in conversations:
                events = conv.get("events", [])

                for event in events:
                    if event.get("type") == "llm_call":
                        agent_name = event.get("agent_name", "unknown")
                        data = event.get("data", {})

                        tokens = data.get("total_tokens", 0)
                        model = data.get("model", "unknown")

                        total_tokens += tokens
                        total_llm_calls += 1

                        # Group by criteria
                        if group_by == "agent":
                            key = agent_name
                        elif group_by == "model":
                            key = model
                        elif group_by == "day":
                            timestamp = event.get("timestamp")
                            if isinstance(timestamp, dt):
                                key = timestamp.strftime("%Y-%m-%d")
                            else:
                                key = "unknown"
                        else:
                            key = "all"

                        if key not in llm_usage:
                            llm_usage[key] = {
                                "calls": 0,
                                "total_tokens": 0,
                                "prompt_tokens": 0,
                                "completion_tokens": 0
                            }

                        llm_usage[key]["calls"] += 1
                        llm_usage[key]["total_tokens"] += tokens
                        llm_usage[key]["prompt_tokens"] += data.get("prompt_tokens", 0)
                        llm_usage[key]["completion_tokens"] += data.get("completion_tokens", 0)

            return {
                "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
                "group_by": group_by,
                "total_llm_calls": total_llm_calls,
                "total_tokens": total_tokens,
                "avg_tokens_per_call": int(total_tokens / total_llm_calls) if total_llm_calls > 0 else 0,
                "by_group": llm_usage
            }

        except Exception as e:
            logger.error(f"Failed to get LLM usage: {e}", exc_info=True)
            return {"error": str(e)}

    async def get_channel_breakdown(
        self,
        start_date: Optional[dt] = None,
        end_date: Optional[dt] = None
    ) -> Dict[str, Any]:
        """
        Get breakdown of conversations by channel (email vs phone)

        Args:
            start_date: Start date (defaults to 30 days ago)
            end_date: End date (defaults to now)

        Returns:
            Dictionary with channel breakdown
        """
        try:
            if not start_date:
                start_date = dt.utcnow() - timedelta(days=30)
            if not end_date:
                end_date = dt.utcnow()

            # Aggregate by channel
            pipeline = [
                {"$match": {"created_at": {"$gte": start_date, "$lte": end_date}}},
                {"$group": {
                    "_id": "$channel",
                    "count": {"$sum": 1},
                    "avg_duration": {"$avg": "$metadata.processing_duration_ms"},
                    "avg_events": {"$avg": "$metadata.total_events"},
                    "avg_llm_calls": {"$avg": "$metadata.llm_calls"}
                }}
            ]

            cursor = self.repo.collection.aggregate(pipeline)
            results = await cursor.to_list(length=None)

            channels = {}
            total_conversations = 0

            for result in results:
                channel = result.get("_id", "unknown")
                count = result.get("count", 0)
                total_conversations += count

                channels[channel] = {
                    "count": count,
                    "avg_duration_ms": int(result.get("avg_duration", 0)),
                    "avg_events": round(result.get("avg_events", 0), 1),
                    "avg_llm_calls": round(result.get("avg_llm_calls", 0), 1)
                }

            # Calculate percentages
            for channel in channels:
                channels[channel]["percentage"] = round(
                    (channels[channel]["count"] / total_conversations * 100), 1
                ) if total_conversations > 0 else 0

            return {
                "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
                "total_conversations": total_conversations,
                "by_channel": channels
            }

        except Exception as e:
            logger.error(f"Failed to get channel breakdown: {e}", exc_info=True)
            return {"error": str(e)}

    async def get_completion_rate(
        self,
        start_date: Optional[dt] = None,
        end_date: Optional[dt] = None
    ) -> Dict[str, Any]:
        """
        Calculate conversation completion rates

        Args:
            start_date: Start date (defaults to 30 days ago)
            end_date: End date (defaults to now)

        Returns:
            Dictionary with completion rate analysis
        """
        try:
            if not start_date:
                start_date = dt.utcnow() - timedelta(days=30)
            if not end_date:
                end_date = dt.utcnow()

            # Aggregate by status
            pipeline = [
                {"$match": {"created_at": {"$gte": start_date, "$lte": end_date}}},
                {"$group": {
                    "_id": "$status",
                    "count": {"$sum": 1}
                }}
            ]

            cursor = self.repo.collection.aggregate(pipeline)
            results = await cursor.to_list(length=None)

            status_counts = {}
            total = 0

            for result in results:
                status = result.get("_id", "unknown")
                count = result.get("count", 0)
                status_counts[status] = count
                total += count

            # Calculate rates
            completed = status_counts.get("completed", 0)
            timeout = status_counts.get("timeout", 0)
            error = status_counts.get("error", 0)
            in_progress = status_counts.get("in_progress", 0)

            completion_rate = (completed / total * 100) if total > 0 else 0
            timeout_rate = (timeout / total * 100) if total > 0 else 0
            error_rate = (error / total * 100) if total > 0 else 0

            return {
                "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
                "total_conversations": total,
                "status_counts": status_counts,
                "completion_rate": round(completion_rate, 1),
                "timeout_rate": round(timeout_rate, 1),
                "error_rate": round(error_rate, 1),
                "in_progress": in_progress
            }

        except Exception as e:
            logger.error(f"Failed to get completion rate: {e}", exc_info=True)
            return {"error": str(e)}

    async def get_conversation_duration_stats(
        self,
        start_date: Optional[dt] = None,
        end_date: Optional[dt] = None
    ) -> Dict[str, Any]:
        """
        Get statistics on conversation durations

        Args:
            start_date: Start date (defaults to 30 days ago)
            end_date: End date (defaults to now)

        Returns:
            Dictionary with duration statistics
        """
        try:
            if not start_date:
                start_date = dt.utcnow() - timedelta(days=30)
            if not end_date:
                end_date = dt.utcnow()

            # Aggregate durations
            pipeline = [
                {
                    "$match": {
                        "created_at": {"$gte": start_date, "$lte": end_date},
                        "status": "completed"
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "count": {"$sum": 1},
                        "avg_duration": {"$avg": "$metadata.processing_duration_ms"},
                        "min_duration": {"$min": "$metadata.processing_duration_ms"},
                        "max_duration": {"$max": "$metadata.processing_duration_ms"},
                        "durations": {"$push": "$metadata.processing_duration_ms"}
                    }
                }
            ]

            cursor = self.repo.collection.aggregate(pipeline)
            results = await cursor.to_list(length=1)

            if not results:
                return {
                    "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
                    "count": 0
                }

            result = results[0]
            durations = sorted(result.get("durations", []))

            # Calculate percentiles
            count = len(durations)
            p50 = durations[int(count * 0.50)] if count > 0 else 0
            p90 = durations[int(count * 0.90)] if count > 0 else 0
            p95 = durations[int(count * 0.95)] if count > 0 else 0
            p99 = durations[int(count * 0.99)] if count > 0 else 0

            return {
                "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
                "count": result.get("count", 0),
                "avg_duration_ms": int(result.get("avg_duration", 0)),
                "min_duration_ms": int(result.get("min_duration", 0)),
                "max_duration_ms": int(result.get("max_duration", 0)),
                "percentiles": {
                    "p50": int(p50),
                    "p90": int(p90),
                    "p95": int(p95),
                    "p99": int(p99)
                }
            }

        except Exception as e:
            logger.error(f"Failed to get duration stats: {e}", exc_info=True)
            return {"error": str(e)}
