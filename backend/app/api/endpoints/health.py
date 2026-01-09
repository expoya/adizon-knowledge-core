"""
Health and Status Endpoints für Monitoring.
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.services.graph_store import GraphStoreService, get_graph_store_service

router = APIRouter()
logger = logging.getLogger(__name__)


class GraphStats(BaseModel):
    """Graph database statistics."""
    total_nodes: int
    total_relationships: int
    node_labels: Dict[str, int]
    relationship_types: Dict[str, int]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    graph_connected: bool
    graph_stats: GraphStats | None = None


@router.get("/health", response_model=HealthResponse)
async def health_check(
    graph_store: GraphStoreService = Depends(get_graph_store_service)
) -> HealthResponse:
    """
    Comprehensive health check with graph statistics.
    
    Returns:
        Health status with graph stats
    """
    try:
        # Get graph statistics
        stats = await get_graph_statistics(graph_store)
        
        return HealthResponse(
            status="healthy",
            graph_connected=True,
            graph_stats=stats
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            graph_connected=False,
            graph_stats=None
        )


@router.get("/graph-stats", response_model=GraphStats)
async def graph_statistics(
    graph_store: GraphStoreService = Depends(get_graph_store_service)
) -> GraphStats:
    """
    Detaillierte Graph-Statistiken.
    
    Returns:
        Umfassende Statistiken über Nodes und Relationships
    """
    return await get_graph_statistics(graph_store)


async def get_graph_statistics(graph_store: GraphStoreService) -> GraphStats:
    """
    Sammelt umfassende Graph-Statistiken.
    
    Args:
        graph_store: Graph store service
        
    Returns:
        GraphStats mit allen Metriken
    """
    # Query 1: Total counts
    count_query = """
    MATCH (n)
    WITH count(n) as node_count
    MATCH ()-[r]->()
    RETURN node_count, count(r) as rel_count
    """
    
    result = await graph_store.query(count_query)
    total_nodes = result[0]["node_count"] if result else 0
    total_relationships = result[0]["rel_count"] if result else 0
    
    # Query 2: Node labels distribution
    labels_query = """
    MATCH (n)
    WITH labels(n) as node_labels
    UNWIND node_labels as label
    RETURN label, count(*) as count
    ORDER BY count DESC
    """
    
    labels_result = await graph_store.query(labels_query)
    node_labels = {
        row["label"]: row["count"] 
        for row in labels_result
    }
    
    # Query 3: Relationship types distribution
    rels_query = """
    MATCH ()-[r]->()
    RETURN type(r) as rel_type, count(*) as count
    ORDER BY count DESC
    """
    
    rels_result = await graph_store.query(rels_query)
    relationship_types = {
        row["rel_type"]: row["count"]
        for row in rels_result
    }
    
    return GraphStats(
        total_nodes=total_nodes,
        total_relationships=total_relationships,
        node_labels=node_labels,
        relationship_types=relationship_types
    )

