"""
Debug Endpoints für Relationship Mapping Analyse.
"""

import logging
from typing import Dict, Any, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.services.graph_store import GraphStoreService, get_graph_store_service

router = APIRouter()
logger = logging.getLogger(__name__)


class SourceIdSample(BaseModel):
    """Sample of source_ids for a label."""
    label: str
    sample_ids: List[str]
    total_count: int


class RelationshipDebug(BaseModel):
    """Debug info for relationship creation."""
    relation_type: str
    expected_count: int
    actual_count: int
    missing_count: int
    sample_broken_relations: List[Dict[str, Any]]


@router.get("/debug/source-ids", response_model=List[SourceIdSample])
async def debug_source_ids(
    graph_store: GraphStoreService = Depends(get_graph_store_service)
) -> List[SourceIdSample]:
    """
    Zeigt Sample source_ids für jeden Node Type.
    
    Hilft zu verstehen wie die IDs formatiert sind.
    """
    
    # Get all labels
    labels_query = """
    MATCH (n)
    WITH DISTINCT labels(n)[0] as label
    WHERE label IS NOT NULL
    RETURN label
    ORDER BY label
    """
    
    labels_result = await graph_store.query(labels_query)
    
    samples = []
    
    for row in labels_result:
        label = row["label"]
        
        # Get sample source_ids for this label
        sample_query = f"""
        MATCH (n:{label})
        WHERE n.source_id IS NOT NULL
        RETURN n.source_id as source_id
        LIMIT 10
        """
        
        sample_result = await graph_store.query(sample_query)
        sample_ids = [r["source_id"] for r in sample_result if r.get("source_id")]
        
        # Get total count
        count_query = f"""
        MATCH (n:{label})
        WHERE n.source_id IS NOT NULL
        RETURN count(n) as total
        """
        
        count_result = await graph_store.query(count_query)
        total_count = count_result[0]["total"] if count_result else 0
        
        samples.append(SourceIdSample(
            label=label,
            sample_ids=sample_ids,
            total_count=total_count
        ))
    
    return samples


@router.get("/debug/orphan-analysis")
async def debug_orphan_analysis(
    graph_store: GraphStoreService = Depends(get_graph_store_service)
) -> Dict[str, Any]:
    """
    Analysiert Orphan Nodes im Detail.
    
    Zeigt warum bestimmte Nodes keine Relationships haben.
    """
    
    # Get orphans with their properties
    orphan_query = """
    MATCH (n:CRMEntity)
    WHERE NOT (n)--()
    WITH n, labels(n) as all_labels
    RETURN 
        all_labels[1] as specific_label,
        n.source_id as source_id,
        n.name as name,
        count(*) as count
    ORDER BY count DESC
    LIMIT 100
    """
    
    orphans = await graph_store.query(orphan_query)
    
    # Analyze patterns
    orphan_by_type = {}
    for orphan in orphans:
        label = orphan.get("specific_label", "Unknown")
        if label not in orphan_by_type:
            orphan_by_type[label] = []
        
        orphan_by_type[label].append({
            "source_id": orphan.get("source_id"),
            "name": orphan.get("name"),
            "count": orphan.get("count")
        })
    
    return {
        "total_orphans": sum(len(v) for v in orphan_by_type.values()),
        "orphans_by_type": orphan_by_type
    }


@router.get("/debug/relationship-targets")
async def debug_relationship_targets(
    graph_store: GraphStoreService = Depends(get_graph_store_service)
) -> Dict[str, Any]:
    """
    Analysiert welche target_ids in Relations verwendet werden
    und ob die entsprechenden Nodes existieren.
    """
    
    # Sample relations that SHOULD exist but DON'T
    # Example: Notes should link to Accounts/Leads
    
    analysis = {}
    
    # Check Notes → Account links
    notes_query = """
    MATCH (n:Note)
    WHERE n.source_id IS NOT NULL
    WITH n.source_id as note_id, 
         n.What_Id as target_id,
         n.name as note_name
    LIMIT 20
    RETURN note_id, target_id, note_name
    """
    
    notes = await graph_store.query(notes_query)
    
    analysis["notes_sample"] = []
    for note in notes:
        note_id = note.get("note_id")
        target_id = note.get("target_id")
        
        # Check if target exists
        if target_id:
            exists_query = f"""
            MATCH (n)
            WHERE n.source_id = '{target_id}'
            RETURN labels(n) as labels, n.name as name
            LIMIT 1
            """
            
            exists = await graph_store.query(exists_query)
            
            analysis["notes_sample"].append({
                "note_id": note_id,
                "target_id": target_id,
                "note_name": note.get("note_name"),
                "target_exists": len(exists) > 0,
                "target_info": exists[0] if exists else None
            })
    
    # Check Deals → Account links
    deals_query = """
    MATCH (d:Deal)
    WHERE d.source_id IS NOT NULL
    WITH d.source_id as deal_id,
         d.Account_Name as account_id,
         d.name as deal_name
    LIMIT 20
    RETURN deal_id, account_id, deal_name
    """
    
    deals = await graph_store.query(deals_query)
    
    analysis["deals_sample"] = []
    for deal in deals:
        deal_id = deal.get("deal_id")
        account_id = deal.get("account_id")
        
        if account_id:
            exists_query = f"""
            MATCH (n)
            WHERE n.source_id = '{account_id}'
            RETURN labels(n) as labels, n.name as name
            LIMIT 1
            """
            
            exists = await graph_store.query(exists_query)
            
            analysis["deals_sample"].append({
                "deal_id": deal_id,
                "account_id": account_id,
                "deal_name": deal.get("deal_name"),
                "target_exists": len(exists) > 0,
                "target_info": exists[0] if exists else None
            })
    
    return analysis


@router.get("/debug/relationship-readiness")
async def debug_relationship_readiness(
    graph_store: GraphStoreService = Depends(get_graph_store_service)
) -> Dict[str, Any]:
    """
    Prüft ob Nodes die nötigen Properties für Relationships haben.
    """
    
    analysis = {}
    
    # Check 1: Do Deals have account_name_id?
    deals_query = """
    MATCH (d:Deal)
    RETURN 
        count(d) as total_deals,
        count(d.account_name_id) as deals_with_account_id,
        count(d.owner_id) as deals_with_owner_id
    """
    
    deals_result = await graph_store.query(deals_query)
    if deals_result:
        analysis["deals"] = deals_result[0]
    
    # Check 2: Do Notes have parent_id?
    notes_query = """
    MATCH (n:Note)
    RETURN 
        count(n) as total_notes,
        count(n.parent_id) as notes_with_parent_id,
        count(n.owner_id) as notes_with_owner_id
    """
    
    notes_result = await graph_store.query(notes_query)
    if notes_result:
        analysis["notes"] = notes_result[0]
    
    # Check 3: Do Tasks have what_id/who_id?
    tasks_query = """
    MATCH (t:Task)
    RETURN 
        count(t) as total_tasks,
        count(t.what_id) as tasks_with_what_id,
        count(t.who_id) as tasks_with_who_id,
        count(t.owner_id) as tasks_with_owner_id
    """
    
    tasks_result = await graph_store.query(tasks_query)
    if tasks_result:
        analysis["tasks"] = tasks_result[0]
    
    # Check 4: Sample Deal with properties
    sample_deal_query = """
    MATCH (d:Deal)
    RETURN d.source_id, d.name, d.account_name_id, d.owner_id, keys(d) as all_keys
    LIMIT 3
    """
    
    sample_deals = await graph_store.query(sample_deal_query)
    analysis["sample_deals"] = sample_deals
    
    return analysis


@router.get("/debug/multi-label-check")
async def debug_multi_label_check(
    graph_store: GraphStoreService = Depends(get_graph_store_service)
) -> Dict[str, Any]:
    """
    Prüft ob Nodes korrekt Multi-Label haben (CRMEntity + spezifisches Label).
    """
    
    query = """
    MATCH (n)
    WITH n, labels(n) as all_labels
    WHERE size(all_labels) > 0
    RETURN 
        all_labels,
        count(*) as count
    ORDER BY count DESC
    LIMIT 50
    """
    
    result = await graph_store.query(query)
    
    # Analyze patterns
    single_label = []
    multi_label = []
    
    for row in result:
        labels = row["all_labels"]
        count = row["count"]
        
        if len(labels) == 1:
            single_label.append({"labels": labels, "count": count})
        else:
            multi_label.append({"labels": labels, "count": count})
    
    return {
        "single_label_nodes": single_label,
        "multi_label_nodes": multi_label,
        "analysis": {
            "nodes_with_only_crmentity": sum(
                item["count"] for item in single_label 
                if item["labels"] == ["CRMEntity"]
            )
        }
    }

