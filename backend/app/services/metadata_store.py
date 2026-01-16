"""
MetadataService: Intelligenter Source Catalog Management (Phase 2.5)

Verwaltet alle verfügbaren Datenquellen und findet die relevanten Sources
für eine gegebene User-Query.

Phase 2.5: LLM-basierte Source Discovery mit semantischem Verständnis.

Der Knowledge Graph ist die zentrale "Glue"-Schicht!
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional
from pathlib import Path
import yaml

from langchain_core.messages import SystemMessage, HumanMessage
from app.core.llm import get_llm
from app.prompts import get_prompt

logger = logging.getLogger(__name__)


class SourceDefinition:
    """
    Repräsentiert eine Datenquelle aus dem Source Catalog.
    
    Eine Source kann sein:
    - knowledge_base: Vector Store + Knowledge Graph
    - CRM (Zoho CRM, Zoho Books)
    - SQL (IoT Datenbank, etc.)
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.id = config.get("id")
        self.type = config.get("type")  # vector_graph | crm | sql
        self.description = config.get("description", "")
        self.status = config.get("status", "active")
        self.tool = config.get("tool")  # Welches Tool wird aufgerufen?
        self.priority = config.get("priority", 99)
        self.requires_entity_id = config.get("requires_entity_id", False)
        self.capabilities = config.get("capabilities", [])
        self.keywords = config.get("keywords", [])
        self.modules = config.get("modules", [])
        self.tables = config.get("tables", [])
        self.connection_env = config.get("connection_env")
        self.note = config.get("note", "")
    
    def matches_query(self, query: str) -> float:
        """
        Berechnet Relevanz-Score für diese Source basierend auf Query.
        
        Args:
            query: User query (lowercase)
            
        Returns:
            float: 0.0 - 1.0 (Relevanz-Score)
        """
        query_lower = query.lower()
        score = 0.0
        max_score = 0.0
        
        # Check top-level keywords (0.3 pro Match)
        if self.keywords:
            max_score += 0.3
            for keyword in self.keywords:
                if keyword.lower() in query_lower:
                    score += 0.3
                    break  # Nur einmal zählen
        
        # Check module keywords (0.4 pro Match)
        if self.modules:
            max_score += 0.4
            for module in self.modules:
                module_keywords = module.get("keywords", [])
                for keyword in module_keywords:
                    if keyword.lower() in query_lower:
                        score += 0.4
                        logger.debug(f"  Module '{module.get('name')}' matched: '{keyword}'")
                        break  # Nur ein Modul pro Source
                if score > max_score - 0.4:  # Modul gefunden
                    break
        
        # Check table keywords (0.4 pro Match, für SQL Sources)
        if self.tables:
            max_score += 0.4
            for table in self.tables:
                table_keywords = table.get("keywords", [])
                for keyword in table_keywords:
                    if keyword.lower() in query_lower:
                        score += 0.4
                        logger.debug(f"  Table '{table.get('name')}' matched: '{keyword}'")
                        break
                if score > max_score - 0.4:  # Tabelle gefunden
                    break
        
        # Normalize score to 0.0 - 1.0
        normalized_score = min(score / max(max_score, 0.01), 1.0) if max_score > 0 else 0.0
        
        return normalized_score
    
    def is_available(self) -> bool:
        """
        Prüft ob die Source verfügbar ist.
        
        Returns:
            bool: True wenn Source genutzt werden kann
        """
        if self.status == "active":
            return True
        elif self.status == "optional":
            # Check if connection is configured
            if self.connection_env:
                env_value = os.getenv(self.connection_env)
                is_configured = bool(env_value)
                if not is_configured:
                    logger.warning(f"Source {self.id} not available: env var '{self.connection_env}' not set")
                else:
                    logger.info(f"Source {self.id} available: env var '{self.connection_env}' is configured")
                return is_configured
            return False
        else:
            logger.debug(f"Source {self.id} has status '{self.status}'")
            return False
    
    def get_relevant_modules(self, query: str) -> List[Dict[str, Any]]:
        """
        Findet relevante Module innerhalb dieser Source.
        
        Args:
            query: User query
            
        Returns:
            Liste von relevanten Modulen
        """
        query_lower = query.lower()
        relevant = []
        
        for module in self.modules:
            module_keywords = module.get("keywords", [])
            for keyword in module_keywords:
                if keyword.lower() in query_lower:
                    relevant.append(module)
                    break
        
        return relevant
    
    def get_relevant_tables(self, query: str) -> List[Dict[str, Any]]:
        """
        Findet relevante Tabellen innerhalb dieser Source (für SQL).
        
        Args:
            query: User query
            
        Returns:
            Liste von relevanten Tabellen
        """
        query_lower = query.lower()
        relevant = []
        
        for table in self.tables:
            table_keywords = table.get("keywords", [])
            for keyword in table_keywords:
                if keyword.lower() in query_lower:
                    relevant.append(table)
                    break
        
        return relevant
    
    def __repr__(self) -> str:
        return f"<SourceDefinition id={self.id} type={self.type} status={self.status}>"


class MetadataService:
    """
    Intelligenter Source Catalog (Phase 2).
    
    Entscheidet welche Datenquellen für eine Query relevant sind.
    Der Knowledge Graph wird IMMER zuerst abgefragt (als "Glue"-Schicht).
    """
    
    def __init__(self):
        self.sources: List[SourceDefinition] = []
        self.strategy: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """Lädt external_sources.yaml mit Source Catalog."""
        config_path = Path(__file__).parent.parent / "config" / "external_sources.yaml"
        
        if not config_path.exists():
            logger.warning(f"Source catalog not found: {config_path}")
            logger.warning("MetadataService will operate with empty catalog")
            return
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                
                if not config:
                    logger.warning("Source catalog is empty")
                    return
                
                # Load sources
                for source_config in config.get("sources", []):
                    source = SourceDefinition(source_config)
                    self.sources.append(source)
                    logger.debug(f"Loaded source: {source.id} ({source.type})")
                
                # Load strategy
                self.strategy = config.get("selection_strategy", {})
            
            logger.info(f"✅ Loaded {len(self.sources)} sources from catalog")
            
        except Exception as e:
            logger.error(f"Failed to load source catalog: {e}", exc_info=True)
    
    def _parse_llm_json_response(self, content: str) -> Dict[str, Any]:
        """
        Robust JSON parsing for LLM responses.
        
        Handles:
        - Markdown code blocks
        - Control characters
        - Trailing commas
        - Escaped quotes
        - Malformed JSON
        
        Args:
            content: Raw LLM response
            
        Returns:
            Parsed JSON dictionary
            
        Raises:
            json.JSONDecodeError: If parsing fails after all repair attempts
        """
        import re
        
        # 1. Remove markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        # 2. Clean control characters (except newlines in strings)
        content = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', ' ', content)
        
        # 3. Remove trailing commas before ] or }
        # Example: {"key": "value",} → {"key": "value"}
        content = re.sub(r',(\s*[}\]])', r'\1', content)
        
        # 4. Fix common JSON formatting issues
        # Remove multiple consecutive commas
        content = re.sub(r',\s*,', ',', content)
        
        # 5. Try to parse
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            # Log original content for debugging
            logger.debug(f"JSON parse error at position {e.pos}: {e.msg}")
            logger.debug(f"Content around error: ...{content[max(0, e.pos-50):e.pos+50]}...")
            
            # 6. Attempt repair: Extract JSON object/array
            # Try to find first { or [ and last } or ]
            start_brace = content.find('{')
            start_bracket = content.find('[')
            
            # Determine which comes first
            if start_brace == -1 and start_bracket == -1:
                raise  # No JSON structure found
            
            if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
                # Object
                start = start_brace
                end = content.rfind('}')
                if end > start:
                    repaired = content[start:end+1]
            else:
                # Array
                start = start_bracket
                end = content.rfind(']')
                if end > start:
                    repaired = content[start:end+1]
            
            try:
                return json.loads(repaired)
            except Exception as repair_err:
                # Last resort: Try to extract source IDs from text
                logger.error(f"JSON repair failed ({repair_err}). Attempting text extraction...")
                logger.debug(f"  Repaired content was: {repaired[:300]}")

                # Try to find source IDs mentioned in the text
                found_sources = []
                known_sources = ["knowledge_base", "zoho_crm", "zoho_books", "iot_database"]
                for source_id in known_sources:
                    if source_id in content.lower():
                        found_sources.append(source_id)

                if found_sources:
                    logger.info(f"  📝 Extracted sources from text: {found_sources}")
                    return {
                        "reasoning": "Extracted from text (JSON parsing failed)",
                        "selected_sources": found_sources,
                        "confidence": 0.5,  # Lower confidence for text extraction
                        "alternative_terms": []
                    }

                # True last resort: Return default with knowledge_base
                logger.error("JSON repair failed. Returning default structure with knowledge_base.")
                return {
                    "reasoning": "JSON parsing failed - using default",
                    "selected_sources": ["knowledge_base"],  # At least return knowledge_base
                    "confidence": 0.3,
                    "alternative_terms": []
                }
    
    def get_relevant_sources(
        self, 
        query: str,
        min_score: float = None,
        max_sources: int = None
    ) -> List[SourceDefinition]:
        """
        Findet relevante Datenquellen für eine Query.
        
        Args:
            query: User query
            min_score: Minimum relevance score (default from strategy)
            max_sources: Maximum number of sources (default from strategy)
        
        Returns:
            List of relevant sources, sorted by priority and score
        """
        # Use defaults from strategy if not provided
        if min_score is None:
            min_score = self.strategy.get("min_relevance_score", 0.3)
        if max_sources is None:
            max_sources = self.strategy.get("max_parallel_sources", 3)
        
        scored_sources = []
        
        for source in self.sources:
            # Skip if not available
            if not source.is_available():
                logger.debug(f"  Source {source.id} not available, skipping")
                continue
            
            # Calculate relevance score
            score = source.matches_query(query)
            
            if score >= min_score:
                scored_sources.append((source, score))
                logger.debug(f"  ✓ Source {source.id} matched with score {score:.2f}")
            else:
                logger.debug(f"  ✗ Source {source.id} score {score:.2f} below threshold {min_score}")
        
        # Sort by priority (lower number = higher priority), then by score
        scored_sources.sort(key=lambda x: (x[0].priority, -x[1]))
        
        # Knowledge Graph immer dabei (wenn strategy sagt so) - VOR max_sources
        result = []
        if self.strategy.get("always_check_graph", True):
            kb_source = self.get_source_by_id("knowledge_base")
            if kb_source and kb_source.is_available():
                result.append(kb_source)
                logger.debug("  ℹ️ Added knowledge_base (always check graph)")
        
        # Add other sources up to max_sources limit
        for source, score in scored_sources:
            if len(result) >= max_sources:
                break
            if source not in result:  # Skip if kb is already in result
                result.append(source)
        
        if result:
            logger.info(f"✅ Selected {len(result)} sources: {[s.id for s in result]}")
        else:
            logger.warning("⚠️ No sources matched query, using default fallback")
            fallback = self.get_default_fallback()
            if fallback:
                result = [fallback]
        
        return result
    
    async def get_relevant_sources_llm(
        self, 
        query: str,
        max_sources: int = None,
        max_retries: int = 2
    ) -> List[SourceDefinition]:
        """
        LLM-basierte Source Discovery mit semantischem Verständnis (Phase 2.5).
        
        Der LLM analysiert die Query semantisch und wählt passende Sources:
        - Versteht Synonyme ("Zahlungsstatus" → Rechnungen)
        - Denkt in verwandten Begriffen
        - Gibt nicht auf bei fehlenden Matches
        - Zeigt Chain-of-Thought Reasoning
        
        Args:
            query: User query
            max_sources: Maximum number of sources (default from strategy)
            max_retries: Anzahl Retry-Versuche bei niedriger Confidence
        
        Returns:
            List of SourceDefinition (LLM-selected)
        """
        if max_sources is None:
            max_sources = self.strategy.get("max_parallel_sources", 3)
        
        logger.info("🤖 LLM-based Source Discovery (Phase 2.5)")
        
        for attempt in range(max_retries + 1):
            if attempt > 0:
                logger.info(f"  Retry attempt {attempt}/{max_retries}")
            
            try:
                # 1. Prepare Source Catalog für LLM
                catalog_description = self._format_catalog_for_llm()
                
                # 2. Load Prompt Template
                source_selection_prompt = get_prompt("source_selection")
                
                # 3. Format Prompt
                formatted_prompt = source_selection_prompt.format(
                    catalog=catalog_description,
                    query=query
                )
                
                # 4. Call LLM
                llm = get_llm(temperature=0.0, streaming=False)
                
                response = await llm.ainvoke([
                    SystemMessage(content="Du bist ein Source Selection Agent."),
                    HumanMessage(content=formatted_prompt)
                ])
                
                # 5. Parse Response (extract JSON from potential markdown)
                content = response.content.strip()

                # Debug: Log raw LLM response for troubleshooting
                logger.debug(f"  📝 Raw LLM response (first 500 chars): {content[:500]}")

                # Use robust JSON parsing
                result = self._parse_llm_json_response(content)
                
                reasoning = result.get("reasoning", "")
                source_ids = result.get("selected_sources", [])
                confidence = result.get("confidence", 0.0)
                alternative_terms = result.get("alternative_terms", [])
                
                # Log reasoning
                logger.info(f"  💭 LLM Reasoning: {reasoning[:200]}...")
                if alternative_terms:
                    logger.info(f"  🔍 Alternative terms: {', '.join(alternative_terms)}")
                logger.info(f"  ✅ Selected: {source_ids} (confidence: {confidence:.2f})")
                
                # 6. Get Source Objects
                selected_sources = []
                for source_id in source_ids:
                    source = self.get_source_by_id(source_id)
                    if source and source.is_available():
                        selected_sources.append(source)
                    else:
                        logger.warning(f"  ⚠️ Source '{source_id}' not found or not available")
                
                # 7. Ensure knowledge_base is included (always check graph strategy)
                if self.strategy.get("always_check_graph", True):
                    kb = self.get_source_by_id("knowledge_base")
                    if kb and kb.is_available():
                        if kb not in selected_sources:
                            selected_sources.insert(0, kb)
                            logger.debug("  ℹ️ Added knowledge_base (always check graph)")
                
                # 8. Check if we have sources
                if selected_sources:
                    # Check confidence for retry
                    if confidence >= 0.5 or attempt >= max_retries:
                        return selected_sources[:max_sources]
                    else:
                        logger.warning(f"  ⚠️ Low confidence ({confidence:.2f}), retrying...")
                        continue
                else:
                    # No sources from LLM - use keyword fallback immediately
                    logger.warning("  ⚠️ LLM returned no sources, trying keyword-based fallback...")
                    keyword_sources = self._fallback_keyword_based(query, max_sources)
                    if keyword_sources:
                        logger.info(f"  ✅ Keyword fallback found: {[s.id for s in keyword_sources]}")
                        return keyword_sources
                    continue
                    
            except json.JSONDecodeError as e:
                logger.error(f"  ❌ Failed to parse LLM response: {e}")
                logger.debug(f"  Response was: {content[:500]}")
                
                if attempt >= max_retries:
                    logger.error("  ❌ All retries exhausted, falling back to keyword-based")
                    return self._fallback_keyword_based(query, max_sources)
                    
            except Exception as e:
                logger.error(f"  ❌ LLM Source Selection failed: {e}", exc_info=True)
                
                if attempt >= max_retries:
                    logger.error("  ❌ All retries exhausted, falling back to keyword-based")
                    return self._fallback_keyword_based(query, max_sources)
        
        # Final fallback
        logger.warning("⚠️ All retries exhausted, using fallback")
        return self._fallback_keyword_based(query, max_sources)
    
    def _format_catalog_for_llm(self) -> str:
        """
        Formatiert Source Catalog für LLM Context.
        
        Returns:
            Formatierter Catalog-String
        """
        lines = []
        
        for source in self.sources:
            if not source.is_available():
                continue
            
            lines.append(f"\n{'='*50}")
            lines.append(f"SOURCE: {source.id}")
            lines.append(f"{'='*50}")
            lines.append(f"Type: {source.type}")
            lines.append(f"Description: {source.description}")
            lines.append(f"Tool: {source.tool}")
            lines.append(f"Priority: {source.priority}")
            lines.append(f"Requires Entity ID from Graph: {source.requires_entity_id}")
            
            if source.keywords:
                # Limit keywords für Token-Effizienz
                keywords_sample = source.keywords[:15]
                lines.append(f"Keywords: {', '.join(keywords_sample)}")
                if len(source.keywords) > 15:
                    lines.append(f"  (... und {len(source.keywords) - 15} weitere)")
            
            if source.modules:
                lines.append("\nModules:")
                for module in source.modules[:6]:  # Max 6 Module
                    name = module.get("name", "")
                    entity_type = module.get("entity_type", "")
                    keywords = module.get("keywords", [])[:8]  # Max 8 Keywords pro Module
                    lines.append(f"  - {name} ({entity_type})")
                    lines.append(f"    Keywords: {', '.join(keywords)}")
            
            if source.tables:
                lines.append("\nTables:")
                for table in source.tables[:4]:  # Max 4 Tables
                    name = table.get("name", "")
                    desc = table.get("description", "")
                    keywords = table.get("keywords", [])[:8]
                    lines.append(f"  - {name}: {desc}")
                    lines.append(f"    Keywords: {', '.join(keywords)}")
            
            if source.capabilities:
                lines.append(f"\nCapabilities: {', '.join(source.capabilities)}")
            
            if source.note:
                lines.append(f"\nNote: {source.note}")
        
        return "\n".join(lines)
    
    def _fallback_keyword_based(
        self, 
        query: str, 
        max_sources: int = None
    ) -> List[SourceDefinition]:
        """
        Fallback zu keyword-based Source Selection.
        
        Args:
            query: User query
            max_sources: Maximum sources
            
        Returns:
            List of SourceDefinition
        """
        logger.info("📋 Fallback: Keyword-based source selection")
        
        # Use old keyword-based method
        if max_sources is None:
            max_sources = self.strategy.get("max_parallel_sources", 3)
        
        return self.get_relevant_sources(query, max_sources=max_sources)
    
    def get_source_by_id(self, source_id: str) -> Optional[SourceDefinition]:
        """
        Findet eine Source anhand ihrer ID.
        
        Args:
            source_id: Source ID
            
        Returns:
            SourceDefinition or None
        """
        for source in self.sources:
            if source.id == source_id:
                return source
        return None
    
    def should_combine_sources(self) -> bool:
        """
        Prüft ob Quellen kombiniert werden sollen.
        
        Returns:
            bool: True wenn Multi-Source Queries erlaubt sind
        """
        return self.strategy.get("combine_sources", True)
    
    def get_default_fallback(self) -> Optional[SourceDefinition]:
        """
        Gibt die Default-Fallback-Source zurück.
        
        Returns:
            SourceDefinition or None
        """
        fallback_id = self.strategy.get("default_fallback", "knowledge_base")
        return self.get_source_by_id(fallback_id)
    
    def requires_graph_first(self) -> bool:
        """
        Prüft ob Graph immer zuerst abgefragt werden soll.
        
        Returns:
            bool: True wenn Graph immer zuerst kommt
        """
        return self.strategy.get("always_check_graph", True)
    
    def get_all_sources(self) -> List[SourceDefinition]:
        """
        Gibt alle konfigurierten Sources zurück.
        
        Returns:
            Liste aller Sources
        """
        return self.sources
    
    def get_source_summary(self) -> str:
        """
        Erstellt eine Summary aller Sources (für Debugging).
        
        Returns:
            Formatierter String mit Source-Info
        """
        lines = ["=== Source Catalog Summary ==="]
        lines.append(f"Total Sources: {len(self.sources)}")
        lines.append("")
        
        for source in self.sources:
            available = "✅" if source.is_available() else "❌"
            lines.append(f"{available} {source.id} ({source.type})")
            lines.append(f"   Priority: {source.priority}, Tool: {source.tool}")
            if source.requires_entity_id:
                lines.append(f"   Requires entity_id from Graph!")
            lines.append("")
        
        lines.append("Strategy:")
        lines.append(f"  - Always check graph: {self.strategy.get('always_check_graph')}")
        lines.append(f"  - Combine sources: {self.strategy.get('combine_sources')}")
        lines.append(f"  - Min score: {self.strategy.get('min_relevance_score')}")
        lines.append(f"  - Max sources: {self.strategy.get('max_parallel_sources')}")
        
        return "\n".join(lines)


# ==========================================
# Singleton Pattern
# ==========================================

_metadata_service_instance: Optional[MetadataService] = None

def metadata_service() -> MetadataService:
    """
    Returns singleton instance of MetadataService.
    
    Returns:
        MetadataService: The global metadata service instance
    """
    global _metadata_service_instance
    if _metadata_service_instance is None:
        _metadata_service_instance = MetadataService()
    return _metadata_service_instance


def reset_metadata_service() -> None:
    """
    Resets the singleton instance (für Tests).
    """
    global _metadata_service_instance
    _metadata_service_instance = None
