"""
Graph Query Service.

Query and search operations for Neo4j graph.
"""

import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

# Thread pool for running blocking operations
_executor = ThreadPoolExecutor(max_workers=2)


class GraphQueryService:
    """
    Handles query and search operations in Neo4j.
    
    Features:
    - Raw Cypher queries
    - Natural language graph queries
    - Graph summarization
    - Keyword-based search
    """
    
    def __init__(self, driver: Any):
        """
        Initialize query service.
        
        Args:
            driver: Neo4j driver instance
        """
        self.driver = driver
    
    async def _run_sync(self, func, *args, **kwargs):
        """Run a synchronous function in the thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor, partial(func, *args, **kwargs)
        )
    
    async def query(self, cypher: str, parameters: Optional[dict] = None) -> List[dict]:
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
            # LLM-based keyword extraction (robust against special chars)
            keywords = await self._extract_keywords(question)
            
            logger.info(f"Graph query keywords: {keywords}")

            if not keywords:
                # Fallback: get some entities from the graph
                logger.info("No keywords found, fetching recent entities")
                result = await self._fetch_recent_entities()
            else:
                # Search for entities matching keywords
                result = await self._search_by_keywords(keywords)

            if not result.records:
                logger.info("No graph results found")
                return ""

            # Format results as readable text
            formatted_results = self._format_results(result.records)
            
            logger.info(f"Graph query returned {len(formatted_results)} unique results")
            return "\n".join(formatted_results) if formatted_results else ""

        except Exception as e:
            logger.error(f"Graph query failed: {e}", exc_info=True)
            return ""
    
    async def get_summary(self) -> str:
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
            logger.error(f"Graph summary failed: {e}")
            return ""
    
    async def _extract_keywords(self, question: str) -> List[str]:
        """
        LLM-basierte Keyword-Extraktion (robust gegen Sonderzeichen).
        
        Args:
            question: Natural language question
            
        Returns:
            List of keywords
        """
        try:
            from app.core.llm import get_llm
            from app.prompts import get_prompt
            from langchain_core.messages import SystemMessage
            import json
            
            llm = get_llm(temperature=0.0, streaming=False)
            query_prompt = get_prompt("query_generation")
            
            logger.debug("  🤖 LLM extracting search keywords...")
            
            result = await llm.ainvoke([
                SystemMessage(content=query_prompt.format(query=question))
            ])
            
            # Parse JSON response
            import re
            content = result.content.strip()
            
            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()
            
            # Clean control characters that break JSON parsing
            content = re.sub(r'[\x00-\x1F\x7F]', ' ', content)
            
            keywords = json.loads(content)
            
            if keywords:
                logger.debug(f"  ✅ LLM extracted keywords: {keywords}")
                return keywords
            else:
                logger.debug("  ℹ️ No keywords extracted, using fallback")
                return self._fallback_keywords(question)
                
        except Exception as e:
            logger.warning(f"  ⚠️ LLM keyword extraction failed: {e}")
            return self._fallback_keywords(question)
    
    def _fallback_keywords(self, question: str) -> List[str]:
        """
        Einfacher Fallback: Extrahiere kapitalisierte Wörter (Namen).
        
        Args:
            question: Natural language question
            
        Returns:
            List of keywords
        """
        import re
        # Nur kapitalisierte Wörter (Namen)
        words = re.findall(r'\b[A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)*\b', question)
        return list(set(words)) if words else [""]
    
    async def _fetch_recent_entities(self):
        """Fetch recent entities when no keywords found."""
        return await self._run_sync(
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
    
    async def _search_by_keywords(self, keywords: List[str]):
        """
        Search for entities matching keywords in ALL text properties.
        
        CRM entities use various name fields (deal_name, account_name_name, contact_name_name).
        We search across ALL string properties to find matches.
        
        IMPORTANT: Queries BOTH outgoing AND incoming relationships to capture:
        - Outgoing: Contact → Account (WORKS_AT)
        - Incoming: Note → Contact (HAS_NOTE), Task → Contact (HAS_TASK), etc.
        
        Args:
            keywords: List of keywords to search
            
        Returns:
            Query result with both relationship directions
        """
        # Search across ALL properties and get BOTH relationship directions
        result = await self._run_sync(
            self.driver.execute_query,
            """
            MATCH (n)
            WHERE (n.status = 'APPROVED' OR n.status IS NULL)
              AND ANY(keyword IN $keywords WHERE 
                  toLower(coalesce(n.name, '')) CONTAINS toLower(keyword)
                  OR toLower(coalesce(n.deal_name, '')) CONTAINS toLower(keyword)
                  OR toLower(coalesce(n.account_name_name, '')) CONTAINS toLower(keyword)
                  OR toLower(coalesce(n.contact_name_name, '')) CONTAINS toLower(keyword)
                  OR toLower(coalesce(n.company, '')) CONTAINS toLower(keyword)
                  OR toLower(coalesce(n.first_name, '')) CONTAINS toLower(keyword)
                  OR toLower(coalesce(n.last_name, '')) CONTAINS toLower(keyword)
              )
            WITH n LIMIT 10
            
            CALL {
                WITH n
                OPTIONAL MATCH (n)-[r_out]->(m_out)
                WHERE (m_out.status = 'APPROVED' OR m_out.status IS NULL)
                  AND (r_out.status = 'APPROVED' OR r_out.status IS NULL)
                RETURN 
                    type(r_out) as relationship,
                    coalesce(m_out.name, m_out.deal_name, m_out.account_name_name, m_out.contact_name_name, m_out.first_name + ' ' + m_out.last_name, m_out.note_title, m_out.subject) as related_entity,
                    coalesce(m_out.note_content, m_out.description, '') as entity_content
                
                UNION ALL
                
                WITH n
                OPTIONAL MATCH (m_in)-[r_in]->(n)
                WHERE (m_in.status = 'APPROVED' OR m_in.status IS NULL)
                  AND (r_in.status = 'APPROVED' OR r_in.status IS NULL)
                RETURN 
                    type(r_in) as relationship,
                    coalesce(m_in.name, m_in.deal_name, m_in.account_name_name, m_in.contact_name_name, m_in.first_name + ' ' + m_in.last_name, m_in.note_title, m_in.subject) as related_entity,
                    coalesce(m_in.note_content, m_in.description, '') as entity_content
            }
            
            RETURN 
                labels(n)[0] as type, 
                coalesce(n.name, n.deal_name, n.account_name_name, n.contact_name_name, n.first_name + ' ' + n.last_name, 'Unknown') as name,
                n.source_id as entity_id,
                relationship,
                related_entity,
                entity_content
            LIMIT 50
            """,
            keywords=keywords,
            database_="neo4j",
        )
        
        return result
    
    def _format_results(self, records) -> List[str]:
        """
        Format query results as readable text with entity IDs for CRM fact lookup.
        
        Includes relationship information and content snippets from Notes/Tasks.
        
        Args:
            records: Neo4j result records
            
        Returns:
            List of formatted strings
        """
        lines = []
        seen = set()  # Avoid duplicate lines
        
        for record in records:
            data = dict(record)
            entity_type = data.get("type", "Entity")
            name = data.get("name", "Unknown")
            entity_id = data.get("entity_id")  # CRM source_id
            rel = data.get("relationship")
            related = data.get("related_entity") or data.get("related_to") or data.get("related_from")
            content = data.get("entity_content", "")
            
            # Include entity_id for CRM entities so the tool can fetch live facts
            if rel and related:
                # Build base relationship line
                if entity_id:
                    line = f"- {entity_type} '{name}' (ID: {entity_id}) {rel} '{related}'"
                else:
                    line = f"- {entity_type} '{name}' {rel} '{related}'"
                
                # Add content preview for Notes/Tasks (first 100 chars)
                if content and len(content.strip()) > 0:
                    content_preview = content.strip()[:100]
                    if len(content) > 100:
                        content_preview += "..."
                    line += f" | Content: {content_preview}"
            else:
                if entity_id:
                    line = f"- {entity_type}: {name} (ID: {entity_id})"
                else:
                    line = f"- {entity_type}: {name}"
            
            if line not in seen:
                seen.add(line)
                lines.append(line)
        
        return lines

