"""
Graph Store Service for Neo4j knowledge graph.

Stores extracted entities and relationships in Neo4j.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import partial
from typing import Any, List

from neo4j import GraphDatabase

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Thread pool for running blocking operations
_executor = ThreadPoolExecutor(max_workers=2)


class GraphStoreService:
    """
    Service for storing entities and relationships in Neo4j.
    
    Provides methods for:
    - Adding nodes (Person, Organization, etc.)
    - Adding relationships between nodes
    - Querying the knowledge graph
    """

    def __init__(self):
        """Initialize Neo4j driver."""
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        # Verify connectivity
        self.driver.verify_connectivity()
        
        # Create indexes for performance
        self._ensure_indexes()

    def close(self):
        """Close the Neo4j driver."""
        self.driver.close()

    def _ensure_indexes(self):
        """
        Create indexes for performance-critical properties.
        
        CRITICAL: Without these indexes, relation creation takes HOURS for large datasets!
        With indexes: Milliseconds per relation
        """
        logger.info("🔧 Creating database indexes...")
        
        try:
            with self.driver.session(database="neo4j") as session:
                # Index 1: CRMEntity.source_id (CRITICAL for relations!)
                try:
                    result = session.run(
                        "CREATE INDEX crm_source_id IF NOT EXISTS FOR (n:CRMEntity) ON (n.source_id)"
                    )
                    result.consume()  # Force execution
                    logger.info("✅ Index created: CRMEntity.source_id")
                except Exception as e:
                    logger.error(f"❌ Failed to create index CRMEntity.source_id: {e}")
                
                # Index 2: User.source_id (for HAS_OWNER relations)
                try:
                    result = session.run(
                        "CREATE INDEX user_source_id IF NOT EXISTS FOR (n:User) ON (n.source_id)"
                    )
                    result.consume()  # Force execution
                    logger.info("✅ Index created: User.source_id")
                except Exception as e:
                    logger.error(f"❌ Failed to create index User.source_id: {e}")
                
                # Index 3: source_document_id (for document graph)
                try:
                    result = session.run(
                        "CREATE INDEX doc_source_id IF NOT EXISTS FOR (n) ON (n.source_document_id)"
                    )
                    result.consume()  # Force execution
                    logger.info("✅ Index created: source_document_id")
                except Exception as e:
                    logger.error(f"❌ Failed to create index source_document_id: {e}")
                    
        except Exception as e:
            logger.error(f"❌ CRITICAL: Failed to create indexes: {e}", exc_info=True)
            # Don't raise - let app continue but log the error

    async def _run_sync(self, func, *args, **kwargs):
        """Run a synchronous function in the thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor, partial(func, *args, **kwargs)
        )

    def _create_node(self, tx, label: str, properties: dict) -> str:
        """Create a node with given label and properties."""
        # Merge to avoid duplicates based on 'name' property
        query = f"""
        MERGE (n:{label} {{name: $name}})
        SET n += $properties
        SET n.updated_at = datetime()
        RETURN elementId(n) as node_id
        """
        result = tx.run(
            query,
            name=properties.get("name", "Unknown"),
            properties=properties,
        )
        record = result.single()
        return record["node_id"] if record else ""

    def _create_relationship(
        self,
        tx,
        from_label: str,
        from_name: str,
        to_label: str,
        to_name: str,
        rel_type: str,
        properties: dict | None = None,
    ) -> None:
        """Create a relationship between two nodes."""
        query = f"""
        MATCH (a:{from_label} {{name: $from_name}})
        MATCH (b:{to_label} {{name: $to_name}})
        MERGE (a)-[r:{rel_type}]->(b)
        SET r += $properties
        SET r.updated_at = datetime()
        """
        tx.run(
            query,
            from_name=from_name,
            to_name=to_name,
            properties=properties or {},
        )

    async def add_entity(
        self,
        label: str,
        name: str,
        properties: dict | None = None,
        document_id: str | None = None,
    ) -> str:
        """
        Add an entity (node) to the graph.
        
        Args:
            label: Node label (e.g., 'Person', 'Organization')
            name: Entity name (used as unique identifier)
            properties: Additional properties for the node
            document_id: Source document ID for provenance
            
        Returns:
            Node ID
        """
        props = properties or {}
        props["name"] = name
        if document_id:
            props["source_document_id"] = document_id

        def _execute(tx):
            return self._create_node(tx, label, props)

        return await self._run_sync(
            self.driver.execute_query,
            f"""
            MERGE (n:{label} {{name: $name}})
            SET n += $properties
            SET n.updated_at = datetime()
            RETURN elementId(n) as node_id
            """,
            name=name,
            properties=props,
            database_="neo4j",
        )

    async def add_relationship(
        self,
        from_entity: tuple[str, str],  # (label, name)
        to_entity: tuple[str, str],     # (label, name)
        relationship_type: str,
        properties: dict | None = None,
    ) -> None:
        """
        Add a relationship between two entities.
        
        Args:
            from_entity: Tuple of (label, name) for source node
            to_entity: Tuple of (label, name) for target node
            relationship_type: Type of relationship (e.g., 'WORKS_FOR')
            properties: Additional properties for the relationship
        """
        from_label, from_name = from_entity
        to_label, to_name = to_entity

        await self._run_sync(
            self.driver.execute_query,
            f"""
            MATCH (a:{from_label} {{name: $from_name}})
            MATCH (b:{to_label} {{name: $to_name}})
            MERGE (a)-[r:{relationship_type}]->(b)
            SET r += $properties
            SET r.updated_at = datetime()
            """,
            from_name=from_name,
            to_name=to_name,
            properties=properties or {},
            database_="neo4j",
        )

    async def add_graph_documents(
        self,
        entities: List[dict],
        relationships: List[dict],
        document_id: str,
        source_file: str | None = None,
    ) -> dict:
        """
        Add extracted graph data to Neo4j with PENDING status for review.

        Args:
            entities: List of dicts with 'label', 'name', and optional 'properties'
            relationships: List of dicts with 'from_label', 'from_name',
                          'to_label', 'to_name', 'type', and optional 'properties'
            document_id: Source document ID
            source_file: Optional source filename for provenance

        Returns:
            Summary of created nodes and relationships
        """
        nodes_created = 0
        rels_created = 0
        created_at = datetime.now(timezone.utc).isoformat()

        # Create entities with PENDING status
        for entity in entities:
            props = entity.get("properties", {})
            props["source_document_id"] = document_id
            props["status"] = "PENDING"  # Review-Status
            props["created_at"] = created_at
            if source_file:
                props["source_file"] = source_file

            await self._run_sync(
                self.driver.execute_query,
                f"""
                MERGE (n:{entity['label']} {{name: $name}})
                SET n += $properties
                SET n.updated_at = datetime()
                """,
                name=entity["name"],
                properties=props,
                database_="neo4j",
            )
            nodes_created += 1

        # Create relationships with PENDING status
        for rel in relationships:
            rel_props = rel.get("properties", {})
            rel_props["status"] = "PENDING"  # Review-Status
            rel_props["created_at"] = created_at
            rel_props["source_document_id"] = document_id
            if source_file:
                rel_props["source_file"] = source_file

            await self._run_sync(
                self.driver.execute_query,
                f"""
                MATCH (a:{rel['from_label']} {{name: $from_name}})
                MATCH (b:{rel['to_label']} {{name: $to_name}})
                MERGE (a)-[r:{rel['type']}]->(b)
                SET r += $properties
                SET r.updated_at = datetime()
                """,
                from_name=rel["from_name"],
                to_name=rel["to_name"],
                properties=rel_props,
                database_="neo4j",
            )
            rels_created += 1

        return {
            "nodes_created": nodes_created,
            "relationships_created": rels_created,
        }

    async def query(self, cypher: str, parameters: dict | None = None) -> List[dict]:
        """
        Execute a custom Cypher query.
        
        Args:
            cypher: Cypher query string
            parameters: Query parameters
            
        Returns:
            List of result records as dicts
        """
        result = await self._run_sync(
            self.driver.execute_query,
            cypher,
            **(parameters or {}),
            database_="neo4j",
        )
        return [dict(record) for record in result.records]

    async def query_graph(self, question: str) -> str:
        """
        Query the knowledge graph for information relevant to a question.

        IMPORTANT: Returns APPROVED nodes and CRM nodes.
        - Document-extracted nodes: Only APPROVED (not PENDING)
        - CRM-synced nodes: Always visible (no status field)
        
        Logic: (status = 'APPROVED' OR status IS NULL)

        Uses SIMPLE Cypher queries to avoid syntax errors with local LLMs.
        No UNION, no complex subqueries - just straightforward MATCH patterns.

        Args:
            question: Natural language question

        Returns:
            Formatted string with graph context, or empty string if no results
        """
        try:
            import re

            # Extract potential keywords from the question
            # Look for capitalized words (proper nouns) and important lowercase words
            words = re.findall(r'\b[A-Z][a-zäöüß]+(?:\s+[A-Z][a-zäöüß]+)*\b', question)

            # Also get some lowercase keywords (filter common words)
            lowercase_words = re.findall(r'\b[a-zäöüß]{4,}\b', question.lower())
            stopwords = {"what", "when", "where", "which", "wer", "wie", "was", "wann", "welche",
                        "sind", "ist", "haben", "hat", "werden", "wird", "kann", "können",
                        "about", "from", "with", "this", "that", "there", "here", "alle", "über"}
            keywords = [w for w in lowercase_words if w not in stopwords]

            all_keywords = list(set(words + keywords))

            logger.info(f"Graph query keywords: {all_keywords}")

            if not all_keywords:
                # Fallback: get some entities from the graph
                # Include APPROVED nodes AND nodes without status (CRM entities)
                logger.info("No keywords found, fetching recent entities")
                result = await self._run_sync(
                    self.driver.execute_query,
                    """
                    MATCH (n)
                    WHERE n.name IS NOT NULL 
                      AND (n.status = 'APPROVED' OR n.status IS NULL)
                    WITH n ORDER BY n.updated_at DESC LIMIT 10
                    OPTIONAL MATCH (n)-[r]->(m)
                    WHERE (m.status = 'APPROVED' OR m.status IS NULL)
                      AND (r.status = 'APPROVED' OR r.status IS NULL)
                    RETURN labels(n)[0] as type, n.name as name,
                           type(r) as relationship, m.name as related_to
                    LIMIT 20
                    """,
                    database_="neo4j",
                )
            else:
                # SIMPLE Cypher: Search for entities matching ANY keyword
                # Include APPROVED nodes AND nodes without status (CRM entities)
                # Use toLower for case-insensitive matching
                # NO UNION - just one simple query with outgoing relationships
                result = await self._run_sync(
                    self.driver.execute_query,
                    """
                    MATCH (n)
                    WHERE n.name IS NOT NULL
                      AND (n.status = 'APPROVED' OR n.status IS NULL)
                      AND ANY(keyword IN $keywords WHERE toLower(n.name) CONTAINS toLower(keyword))
                    WITH n LIMIT 10
                    OPTIONAL MATCH (n)-[r]->(m)
                    WHERE (m.status = 'APPROVED' OR m.status IS NULL)
                      AND (r.status = 'APPROVED' OR r.status IS NULL)
                    RETURN labels(n)[0] as type, n.name as name,
                           type(r) as relationship, m.name as related_to
                    LIMIT 20
                    """,
                    keywords=all_keywords,
                    database_="neo4j",
                )

                # If no results, try incoming relationships in a separate query
                if not result.records:
                    logger.info("No outgoing relationships found, trying incoming")
                    result = await self._run_sync(
                        self.driver.execute_query,
                        """
                        MATCH (n)<-[r]-(m)
                        WHERE n.name IS NOT NULL
                          AND (n.status = 'APPROVED' OR n.status IS NULL)
                          AND (m.status = 'APPROVED' OR m.status IS NULL)
                          AND (r.status = 'APPROVED' OR r.status IS NULL)
                          AND ANY(keyword IN $keywords WHERE toLower(n.name) CONTAINS toLower(keyword))
                        RETURN labels(n)[0] as type, n.name as name,
                               type(r) as relationship, m.name as related_from
                        LIMIT 20
                        """,
                        keywords=all_keywords,
                        database_="neo4j",
                    )

            if not result.records:
                logger.info("No graph results found")
                return ""

            # Format results as readable text
            lines = []
            seen = set()  # Avoid duplicate lines
            
            for record in result.records:
                data = dict(record)
                entity_type = data.get("type", "Entity")
                name = data.get("name", "Unknown")
                rel = data.get("relationship")
                related = data.get("related_to") or data.get("related_from")
                
                if rel and related:
                    line = f"- {entity_type} '{name}' {rel} '{related}'"
                else:
                    line = f"- {entity_type}: {name}"
                
                if line not in seen:
                    seen.add(line)
                    lines.append(line)

            logger.info(f"Graph query returned {len(lines)} unique results")
            return "\n".join(lines) if lines else ""

        except Exception as e:
            logger.error(f"Graph query failed: {e}", exc_info=True)
            return ""

    async def get_graph_summary(self) -> str:
        """
        Get a summary of the knowledge graph contents.

        Shows both APPROVED and PENDING counts for transparency.

        Returns:
            Summary string with entity counts
        """
        try:
            # Get APPROVED counts (document-extracted entities)
            approved_result = await self._run_sync(
                self.driver.execute_query,
                """
                MATCH (n)
                WHERE n.status = 'APPROVED'
                RETURN labels(n)[0] as label, count(*) as count
                ORDER BY count DESC
                LIMIT 10
                """,
                database_="neo4j",
            )
            
            # Get CRM counts (no status field)
            crm_result = await self._run_sync(
                self.driver.execute_query,
                """
                MATCH (n)
                WHERE n.status IS NULL
                RETURN labels(n)[0] as label, count(*) as count
                ORDER BY count DESC
                LIMIT 10
                """,
                database_="neo4j",
            )

            # Get PENDING counts
            pending_result = await self._run_sync(
                self.driver.execute_query,
                """
                MATCH (n)
                WHERE n.status = 'PENDING'
                RETURN count(*) as pending_count
                """,
                database_="neo4j",
            )

            pending_count = 0
            if pending_result.records:
                pending_count = pending_result.records[0]["pending_count"]

            if not approved_result.records and not crm_result.records and pending_count == 0:
                return "Graph is empty."

            lines = []
            
            # Show CRM entities (always visible)
            if crm_result.records:
                lines.append("Knowledge Graph (CRM - Always Visible):")
                for record in crm_result.records:
                    data = dict(record)
                    lines.append(f"  - {data['count']} {data['label']}")
            
            # Show APPROVED entities (document-extracted)
            if approved_result.records:
                lines.append("\nKnowledge Graph (Documents - APPROVED):")
                for record in approved_result.records:
                    data = dict(record)
                    lines.append(f"  - {data['count']} {data['label']}")
            
            if pending_count > 0:
                lines.append(f"\n⏳ {pending_count} Entitäten warten auf Review (PENDING)")

            return "\n".join(lines)

        except Exception as e:
            print(f"Graph summary failed: {e}")
            return ""

    async def delete_by_filename(self, filename: str) -> int:
        """
        Delete all nodes and relationships associated with a specific filename.

        Args:
            filename: The source filename to delete

        Returns:
            Number of deleted nodes
        """
        logger.info(f"Deleting graph nodes for filename: {filename}")

        try:
            # First count how many we'll delete
            count_result = await self._run_sync(
                self.driver.execute_query,
                """
                MATCH (n)
                WHERE n.source_file CONTAINS $filename
                RETURN count(n) as count
                """,
                filename=filename,
                database_="neo4j",
            )

            delete_count = count_result.records[0]["count"] if count_result.records else 0

            # Then delete nodes (DETACH DELETE also removes relationships)
            await self._run_sync(
                self.driver.execute_query,
                """
                MATCH (n)
                WHERE n.source_file CONTAINS $filename
                DETACH DELETE n
                """,
                filename=filename,
                database_="neo4j",
            )

            logger.info(f"Deleted {delete_count} graph nodes for filename: {filename}")
            return delete_count

        except Exception as e:
            logger.error(f"Failed to delete graph nodes for {filename}: {e}")
            raise

    async def delete_by_document_id(self, document_id: str) -> int:
        """
        Delete all nodes and relationships associated with a specific document ID.

        Args:
            document_id: The source document ID to delete

        Returns:
            Number of deleted nodes
        """
        logger.info(f"Deleting graph nodes for document_id: {document_id}")

        try:
            # First count how many we'll delete
            count_result = await self._run_sync(
                self.driver.execute_query,
                """
                MATCH (n)
                WHERE n.source_document_id = $document_id
                RETURN count(n) as count
                """,
                document_id=document_id,
                database_="neo4j",
            )

            delete_count = count_result.records[0]["count"] if count_result.records else 0

            # Then delete nodes (DETACH DELETE also removes relationships)
            await self._run_sync(
                self.driver.execute_query,
                """
                MATCH (n)
                WHERE n.source_document_id = $document_id
                DETACH DELETE n
                """,
                document_id=document_id,
                database_="neo4j",
            )

            logger.info(f"Deleted {delete_count} graph nodes for document_id: {document_id}")
            return delete_count

        except Exception as e:
            logger.error(f"Failed to delete graph nodes for document {document_id}: {e}")
            raise

    async def get_last_sync_time(self, sync_key: str = "crm_sync") -> str | None:
        """
        Get the last sync timestamp for a given sync key.
        
        Args:
            sync_key: Unique key for this sync type (default: "crm_sync")
            
        Returns:
            ISO 8601 timestamp string or None if never synced
        """
        try:
            result = await self._run_sync(
                self.driver.execute_query,
                """
                MATCH (sys:System {key: $sync_key})
                RETURN sys.last_sync_time as last_sync_time
                """,
                sync_key=sync_key,
                database_="neo4j",
            )
            
            if result and result.records and len(result.records) > 0:
                last_sync = result.records[0].get("last_sync_time")
                if last_sync:
                    # Convert Neo4j DateTime to ISO string
                    return last_sync.isoformat() if hasattr(last_sync, 'isoformat') else str(last_sync)
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to get last sync time: {e}")
            return None

    async def set_last_sync_time(self, timestamp: str | None = None, sync_key: str = "crm_sync") -> None:
        """
        Set the last sync timestamp for a given sync key.
        
        Args:
            timestamp: ISO 8601 timestamp string or None for current time
            sync_key: Unique key for this sync type (default: "crm_sync")
        """
        try:
            # Use provided timestamp or current time
            if timestamp is None:
                timestamp = datetime.now(timezone.utc).isoformat()
            
            await self._run_sync(
                self.driver.execute_query,
                """
                MERGE (sys:System {key: $sync_key})
                SET sys.last_sync_time = datetime($timestamp),
                    sys.updated_at = datetime()
                """,
                sync_key=sync_key,
                timestamp=timestamp,
                database_="neo4j",
            )
            
            logger.info(f"✅ Updated last sync time: {timestamp}")
            
        except Exception as e:
            logger.error(f"Failed to set last sync time: {e}")
            raise


# Singleton instance
_graph_store_service: GraphStoreService | None = None


def get_graph_store_service() -> GraphStoreService:
    """Get or create graph store service singleton."""
    global _graph_store_service
    if _graph_store_service is None:
        _graph_store_service = GraphStoreService()
    return _graph_store_service

