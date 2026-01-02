"""
Graph API Endpoint for Neo4j queries.

Provides endpoints for:
- Executing Cypher queries (for admin/review purposes)
- Approving/rejecting pending nodes
"""

import logging
from typing import Annotated, Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.services.graph_store import GraphStoreService, get_graph_store_service

router = APIRouter()
logger = logging.getLogger(__name__)


# =============================================================================
# Pending Nodes
# =============================================================================


class PendingNode(BaseModel):
    """A pending node awaiting review."""
    id: str
    type: str
    name: str
    source_file: str | None = None
    source_document_id: str | None = None
    created_at: str | None = None


class PendingNodesResponse(BaseModel):
    """Response model for pending nodes."""
    nodes: List[PendingNode]
    count: int


@router.get("/graph/pending", response_model=PendingNodesResponse)
async def get_pending_nodes(
    graph_store: Annotated[GraphStoreService, Depends(get_graph_store_service)],
) -> PendingNodesResponse:
    """
    Get all nodes with status = 'PENDING' for review in the Wissens-Garten.
    """
    logger.info("Fetching pending nodes...")

    try:
        query = """
        MATCH (n)
        WHERE n.status = 'PENDING'
        RETURN
            elementId(n) as id,
            labels(n)[0] as type,
            n.name as name,
            n.source_file as source_file,
            n.source_document_id as source_document_id,
            n.created_at as created_at
        ORDER BY n.created_at DESC
        LIMIT 200
        """

        records = await graph_store.query(cypher=query)

        nodes = [
            PendingNode(
                id=str(r.get("id", "")),
                type=str(r.get("type", "Unknown")),
                name=str(r.get("name", "Unknown")),
                source_file=r.get("source_file"),
                source_document_id=r.get("source_document_id"),
                created_at=r.get("created_at"),
            )
            for r in records
        ]

        logger.info(f"Found {len(nodes)} pending nodes")

        return PendingNodesResponse(
            nodes=nodes,
            count=len(nodes),
        )

    except Exception as e:
        logger.error(f"Failed to fetch pending nodes: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pending nodes: {str(e)}",
        )


# =============================================================================
# Generic Cypher Query
# =============================================================================


class GraphQueryRequest(BaseModel):
    """Request model for graph query endpoint."""
    cypher: str
    parameters: dict[str, Any] | None = None


class GraphQueryResponse(BaseModel):
    """Response model for graph query endpoint."""
    records: List[dict[str, Any]]
    summary: str | None = None


@router.post("/graph/query", response_model=GraphQueryResponse)
async def execute_graph_query(
    request: GraphQueryRequest,
    graph_store: Annotated[GraphStoreService, Depends(get_graph_store_service)],
) -> GraphQueryResponse:
    """
    Execute a Cypher query against the Neo4j graph.

    This endpoint is intended for admin/review purposes.
    Use with caution - allows arbitrary Cypher execution.
    """
    logger.info(f"Executing Cypher query: {request.cypher[:100]}...")

    try:
        records = await graph_store.query(
            cypher=request.cypher,
            parameters=request.parameters,
        )

        return GraphQueryResponse(
            records=records,
            summary=f"Query returned {len(records)} records",
        )

    except Exception as e:
        logger.error(f"Graph query failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph query failed: {str(e)}",
        )


class ApproveNodesRequest(BaseModel):
    """Request model for approving nodes."""
    node_ids: List[str]


class ApproveNodesResponse(BaseModel):
    """Response model for approving nodes."""
    approved_count: int
    message: str


@router.post("/graph/approve", response_model=ApproveNodesResponse)
async def approve_nodes(
    request: ApproveNodesRequest,
    graph_store: Annotated[GraphStoreService, Depends(get_graph_store_service)],
) -> ApproveNodesResponse:
    """
    Approve pending nodes by setting their status to APPROVED.
    """
    if not request.node_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No node IDs provided",
        )

    logger.info(f"Approving {len(request.node_ids)} nodes...")

    try:
        query = """
        MATCH (n)
        WHERE elementId(n) IN $nodeIds
        SET n.status = 'APPROVED', n.approved_at = datetime()
        RETURN count(n) as updated
        """

        records = await graph_store.query(
            cypher=query,
            parameters={"nodeIds": request.node_ids},
        )

        updated_count = records[0]["updated"] if records else 0

        return ApproveNodesResponse(
            approved_count=updated_count,
            message=f"Successfully approved {updated_count} nodes",
        )

    except Exception as e:
        logger.error(f"Failed to approve nodes: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve nodes: {str(e)}",
        )


class RejectNodesRequest(BaseModel):
    """Request model for rejecting nodes."""
    node_ids: List[str]


class RejectNodesResponse(BaseModel):
    """Response model for rejecting nodes."""
    rejected_count: int
    message: str


@router.post("/graph/reject", response_model=RejectNodesResponse)
async def reject_nodes(
    request: RejectNodesRequest,
    graph_store: Annotated[GraphStoreService, Depends(get_graph_store_service)],
) -> RejectNodesResponse:
    """
    Reject pending nodes by deleting them from the graph.
    """
    if not request.node_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No node IDs provided",
        )

    logger.info(f"Rejecting {len(request.node_ids)} nodes...")

    try:
        # First count how many we'll delete
        count_query = """
        MATCH (n)
        WHERE elementId(n) IN $nodeIds
        RETURN count(n) as count
        """

        count_records = await graph_store.query(
            cypher=count_query,
            parameters={"nodeIds": request.node_ids},
        )

        delete_count = count_records[0]["count"] if count_records else 0

        # Then delete
        delete_query = """
        MATCH (n)
        WHERE elementId(n) IN $nodeIds
        DETACH DELETE n
        """

        await graph_store.query(
            cypher=delete_query,
            parameters={"nodeIds": request.node_ids},
        )

        return RejectNodesResponse(
            rejected_count=delete_count,
            message=f"Successfully rejected {delete_count} nodes",
        )

    except Exception as e:
        logger.error(f"Failed to reject nodes: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject nodes: {str(e)}",
        )
