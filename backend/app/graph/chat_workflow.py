"""
LangGraph Chat Workflow für Agentic RAG (Phase 3 - Streamlined).

Simplified 3-Node Architecture:
  Router → Knowledge Orchestrator → Generator

The Knowledge Orchestrator is the central hub that:
- Uses LLM-based Source Discovery (Catalog-first!)
- Performs Entity Resolution via Graph (when requires_entity_id)
- Executes CRM/SQL tools directly (no separate CRM node needed)
"""

import logging
import time
from typing import Dict, List, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from app.core.config import get_settings
from app.core.llm import get_llm
from app.tools.knowledge import search_knowledge_base
from app.tools.crm import get_crm_facts
from app.prompts import get_prompt

logger = logging.getLogger(__name__)
settings = get_settings()

# =============================================================================
# Company Context Cache
# =============================================================================

_company_context_cache: dict = {
    "content": None,
    "loaded_at": 0,
    "ttl": 300,  # 5 minutes cache
}


async def get_company_context() -> str:
    """
    Load company context from MinIO with caching.

    The company context is a Markdown file that provides company-specific
    information for the LLM (company name, products, communication style, etc.).

    Returns:
        Company context string, or empty string if not found.
    """
    global _company_context_cache

    # Check cache validity
    now = time.time()
    if (
        _company_context_cache["content"] is not None
        and now - _company_context_cache["loaded_at"] < _company_context_cache["ttl"]
    ):
        return _company_context_cache["content"]

    # Load from MinIO
    from app.services.storage import get_minio_service

    try:
        minio_service = get_minio_service()
        context_path = settings.company_context_minio_path

        # Check if file exists
        if not await minio_service.file_exists(context_path):
            logger.info(f"Company context not found in MinIO: {context_path} (using default)")
            _company_context_cache["content"] = ""
            _company_context_cache["loaded_at"] = now
            return ""

        # Download and decode
        content_bytes = await minio_service.download_file(context_path)
        content = content_bytes.decode("utf-8")

        # Update cache
        _company_context_cache["content"] = content
        _company_context_cache["loaded_at"] = now

        logger.info(f"Company context loaded from MinIO: {context_path} ({len(content)} chars)")
        return content

    except Exception as e:
        logger.warning(f"Failed to load company context from MinIO: {e}")
        _company_context_cache["content"] = ""
        _company_context_cache["loaded_at"] = now
        return ""


# =============================================================================
# Helper Functions
# =============================================================================

# Helper function removed - no longer needed after simplification


# =============================================================================
# State Definition
# =============================================================================

class AgentState(TypedDict):
    """State für den Chat Agenten."""
    messages: List[AnyMessage]
    intent: str  # "question", "general"
    crm_target: str  # Entity ID für CRM-Abfrage (z.B. "zoho_123456")
    tool_outputs: Dict[str, str]  # {"knowledge_result": "...", "crm_result": "..."}


# =============================================================================
# Node Implementations
# =============================================================================

async def router_node(state: AgentState) -> AgentState:
    """
    Router Node: Pure Intent Classification.

    Entscheidet NUR zwischen:
    - "question": Fachliche Frage → Knowledge Orchestrator
    - "general": Small Talk → Direkt zum Generator

    Entity Resolution passiert im Knowledge Node basierend auf dem Katalog!
    Der Katalog entscheidet, ob Graph-Suche nötig ist (requires_entity_id).
    """
    logger.info("🔀 Router Node: Intent classification only")

    # Hole letzte User-Nachricht
    user_message = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            user_message = msg.content
            break

    if not user_message:
        logger.warning("⚠️ No user message found in state")
        state["intent"] = "general"
        return state

    logger.info(f"[ROUTER] User Query: {user_message[:100]}...")

    # Verwende LLM für Intent Classification (vereinfacht: nur 2 Intents)
    llm = get_llm(temperature=0.0, streaming=False)
    classification_prompt = get_prompt("intent_classification")

    try:
        classification_result = await llm.ainvoke([
            SystemMessage(content=classification_prompt.format(query=user_message))
        ])
        intent_raw = classification_result.content.strip().lower()

        # Normalisiere Intent
        if "question" in intent_raw or "frage" in intent_raw:
            state["intent"] = "question"
        else:
            state["intent"] = "general"

        logger.info(f"[ROUTER] Intent: '{state['intent']}' → {'Knowledge Node' if state['intent'] == 'question' else 'Generator'}")

    except Exception as e:
        logger.error(f"❌ Intent classification failed: {e}")
        state["intent"] = "question"  # Fallback zu question (besser als general)

    return state


# =============================================================================
# SQL Node - REMOVED (Phase 1 Cleanup)
# SQL functionality will be integrated into Knowledge Orchestrator in Phase 3
# =============================================================================


async def knowledge_node(state: AgentState) -> AgentState:
    """
    Smart Knowledge Orchestrator (Phase 3).
    
    Flow:
    1. LLM Source Discovery (welche Quellen sind relevant?)
    2. Check requires_entity_id (brauchen wir Entity IDs?)
    3. IF needed: Graph Query (Entity Resolution)
    4. Execute Tools parallel für alle relevanten Sources
    5. Combine Results
    
    Der Catalog entscheidet was abgefragt wird - nicht mehr der Graph!
    """
    logger.info("🧠 [SMART ORCHESTRATOR] Phase 3 - Intelligent Source Discovery")
    
    # Hole User Query
    user_message = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            user_message = msg.content
            break
    
    if not user_message:
        state["tool_outputs"]["knowledge_result"] = "Error: Keine User-Query gefunden."
        return state
    
    logger.info(f"  Query: {user_message[:100]}...")
    
    # =========================================================================
    # STEP 1: LLM Source Discovery (Catalog-first!)
    # =========================================================================
    logger.info("📋 Step 1: LLM-based Source Discovery")
    
    from app.services.metadata_store import metadata_service
    metadata_svc = metadata_service()
    
    try:
        # LLM wählt relevante Sources
        # max_sources=4 to allow: knowledge_base + CRM + Finance + IoT
        relevant_sources = await metadata_svc.get_relevant_sources_llm(
            query=user_message,
            max_sources=4
        )
        
        logger.info(f"  ✅ Selected {len(relevant_sources)} sources: {[s.id for s in relevant_sources]}")
        
    except Exception as e:
        logger.error(f"  ❌ LLM Source Discovery failed: {e}")
        # Fallback: Nur knowledge_base
        relevant_sources = [metadata_svc.get_source_by_id("knowledge_base")]
        logger.warning(f"  ⚠️ Using fallback: knowledge_base only")
    
    # =========================================================================
    # STEP 2: Check if we need Entity IDs from Graph
    # =========================================================================
    needs_entity_ids = any(
        source.requires_entity_id 
        for source in relevant_sources 
        if source
    )
    
    entity_ids = {}
    graph_context = ""
    
    if needs_entity_ids:
        logger.info("🕸️ Step 2: Graph Query needed (Entity Resolution)")
        
        try:
            from app.services.graph_store import get_graph_store_service
            graph_store = get_graph_store_service()
            
            # STEP 2a: LLM extrahiert Entity-Namen
            logger.info("  🔍 Step 2a: Extracting entity names from query using LLM...")
            
            llm = get_llm(temperature=0.0, streaming=False)
            entity_extraction_prompt = get_prompt("entity_extraction")
            
            try:
                extraction_result = await llm.ainvoke([
                    SystemMessage(content=entity_extraction_prompt.format(query=user_message))
                ])
                
                # Parse JSON response
                import json
                import re
                extracted_text = extraction_result.content.strip()
                # Remove markdown code blocks if present
                if extracted_text.startswith("```"):
                    extracted_text = extracted_text.split("```")[1]
                    if extracted_text.startswith("json"):
                        extracted_text = extracted_text[4:]
                extracted_text = extracted_text.strip()
                
                # Clean control characters that break JSON parsing
                extracted_text = re.sub(r'[\x00-\x1F\x7F]', ' ', extracted_text)
                
                entity_names = json.loads(extracted_text)
                
                if entity_names:
                    logger.info(f"    ✅ LLM extracted {len(entity_names)} entity names: {entity_names}")
                else:
                    logger.debug("    ℹ️ No entity names extracted from query")
                    # Continue without entities
                    entity_names = []
                    
            except Exception as e:
                logger.warning(f"    ⚠️ Entity extraction failed: {e} - continuing without entity resolution")
                entity_names = []
            
            # STEP 2b: Graph-Suche mit extrahierten Namen
            if entity_names:
                logger.info("  🔍 Step 2b: Searching graph for extracted entities...")
                
                all_matches = []
                
                for entity_name in entity_names:
                    # Einfache, präzise Query mit exaktem Namen
                    cypher_query = """
                    MATCH (n)
                    WHERE (n.source_id STARTS WITH 'zoho_' OR n.source_id STARTS WITH 'twenty_' OR n.source_id STARTS WITH 'iot_')
                      AND (
                        toLower(n.name) = toLower($name)
                        OR toLower(n.company) = toLower($name)
                        OR toLower(n.account_name) = toLower($name)
                        OR (toLower(n.first_name) + ' ' + toLower(n.last_name)) = toLower($name)
                      )
                    RETURN
                      n.source_id as source_id,
                      coalesce(n.name, n.account_name, n.company, n.first_name + ' ' + n.last_name) as name,
                      labels(n)[0] as type,
                      100 as score

                    UNION

                    // Fallback: Partial match if exact not found
                    MATCH (n)
                    WHERE (n.source_id STARTS WITH 'zoho_' OR n.source_id STARTS WITH 'twenty_' OR n.source_id STARTS WITH 'iot_')
                      AND (
                        toLower(n.name) CONTAINS toLower($name)
                        OR toLower(n.company) CONTAINS toLower($name)
                        OR toLower(n.account_name) CONTAINS toLower($name)
                      )
                    RETURN
                      n.source_id as source_id,
                      coalesce(n.name, n.account_name, n.company) as name,
                      labels(n)[0] as type,
                      50 as score

                    ORDER BY score DESC
                    LIMIT 3
                    """
                    
                    result = await graph_store.query(
                        cypher_query,
                        parameters={"name": entity_name}
                    )
                    
                    if result:
                        logger.info(f"    ✅ Found {len(result)} matches for '{entity_name}'")
                        
                        # Apply fuzzy matching to re-rank results
                        from app.utils.fuzzy_matching import fuzzy_match_entities
                        
                        # Convert to format expected by fuzzy matcher
                        candidates = [
                            (match["source_id"], match["name"], match["type"], match["score"])
                            for match in result
                        ]
                        
                        # Apply fuzzy matching with 70% threshold
                        fuzzy_results = fuzzy_match_entities(entity_name, candidates, threshold=0.7)
                        
                        # Convert back and add to all_matches
                        for source_id, name, entity_type, score in fuzzy_results:
                            all_matches.append({
                                "source_id": source_id,
                                "name": name,
                                "type": entity_type,
                                "score": score,
                                "searched_name": entity_name
                            })
                        
                        if not fuzzy_results and result:
                            # If fuzzy matching filtered everything, keep original results
                            logger.warning(f"    ⚠️ Fuzzy matching too strict, keeping {len(result)} original results")
                            for match in result:
                                match["searched_name"] = entity_name
                                all_matches.append(match)
                    else:
                        logger.warning(f"    ⚠️ No matches found for '{entity_name}'")
                
                entities = all_matches
            else:
                entities = []
            
            if entities:
                logger.info(f"  ✅ Found {len(entities)} entity candidates in graph")
                
                # Bester Match (höchster Score)
                best_match = entities[0]
                best_score = best_match.get("score", 0)  # FIXED: score statt total_score
                best_name = best_match.get("name", "")
                best_type = best_match.get("type", "")
                best_id = best_match.get("source_id", "")
                
                # Log alle Kandidaten für Transparenz
                for i, entity in enumerate(entities):
                    score = entity.get("score", 0)  # FIXED: score statt total_score
                    name = entity.get("name", "")
                    entity_type = entity.get("type", "")
                    source_id = entity.get("source_id", "")
                    marker = "✅ BEST" if i == 0 else f"  Alt #{i}"
                    logger.info(f"    {marker}: {entity_type} '{name}' (Score: {score}) - {source_id}")
                
                # Check Confidence
                if best_score >= 60:
                    logger.info(f"  🎯 Confident match: {best_type} '{best_name}' (Score: {best_score})")
                    
                    # Kategorisiere beste Entity
                    if best_id.startswith("zoho_"):
                        entity_ids["crm"] = best_id
                        state["crm_target"] = best_id
                    elif best_id.startswith("iot_"):
                        entity_ids["iot"] = best_id
                else:
                    logger.warning(f"  ⚠️ Low confidence match (Score: {best_score}): {best_type} '{best_name}'")
                    logger.warning(f"  ℹ️ Consider asking user to clarify which entity they mean")
                    
                    # Verwende trotzdem beste Match aber markiere als unsicher
                    if best_id.startswith("zoho_"):
                        entity_ids["crm"] = best_id
                        state["crm_target"] = best_id
                        state["entity_uncertain"] = True
                    elif best_id.startswith("iot_"):
                        entity_ids["iot"] = best_id
                        state["entity_uncertain"] = True
                
                if entity_ids:
                    logger.info(f"  🎯 Entity IDs extracted: {entity_ids}")
                else:
                    logger.warning("  ⚠️ No usable entity IDs found")
            else:
                logger.info("  ℹ️ No entities with source_id found in query")
            
        except Exception as e:
            logger.error(f"  ❌ Graph query failed: {e}", exc_info=True)
            # Continue without entity IDs
    else:
        logger.info("⏭️ Step 2: Skipping Graph Query (no entity IDs needed)")
    
    # =========================================================================
    # STEP 3: Execute Tools based on Sources
    # =========================================================================
    logger.info("🔧 Step 3: Executing tools for relevant sources")
    
    tool_results = {}
    
    for source in relevant_sources:
        if not source:
            continue
        
        source_id = source.id
        tool_name = source.tool
        
        logger.info(f"  📞 {source_id}: Calling tool '{tool_name}'")
        
        try:
            # ---- Knowledge Base (Vector + Graph) ----
            if tool_name == "search_knowledge_base":
                result = await search_knowledge_base.ainvoke({"query": user_message})
                tool_results["knowledge_result"] = result
                
                if "Keine relevanten" in result or "nicht verfügbar" in result:
                    logger.info(f"    ⚠️ No relevant knowledge found")
                else:
                    logger.info(f"    ✅ Knowledge retrieved: {len(result)} chars")
            
            # ---- CRM (Live Data via Graph-ID) ----
            elif tool_name == "get_crm_facts":
                if "crm" in entity_ids:
                    result = await get_crm_facts.ainvoke({
                        "entity_id": entity_ids["crm"],
                        "query_context": user_message
                    })
                    tool_results["crm_result"] = result
                    
                    if "Error" in result or "Fehler" in result:
                        logger.warning(f"    ⚠️ CRM query had errors")
                    else:
                        logger.info(f"    ✅ CRM facts retrieved: {len(result)} chars")
                else:
                    logger.warning(f"    ⚠️ CRM source selected but no entity ID found")
                    tool_results["crm_result"] = "CRM-Daten: Keine Entity-ID gefunden."
            
            # ---- SQL (für IoT/Sensoren via Graph-ID) ----
            elif tool_name == "execute_sql_query":
                if "iot" in entity_ids:
                    from app.tools.sql import execute_sql_query as sql_tool
                    
                    # Einfaches SQL für Equipment (kann erweitert werden)
                    equipment_id = entity_ids["iot"]
                    
                    # Prüfe welche Tabellen relevant sind
                    relevant_tables = source.get_relevant_tables(user_message)
                    
                    if relevant_tables:
                        table_name = relevant_tables[0].get("name", "machine_sensors")
                        
                        # Simple SQL Query
                        sql_query = f"""
                        SELECT * FROM {table_name}
                        WHERE machine_id = '{equipment_id}'
                        ORDER BY timestamp DESC
                        LIMIT 10
                        """
                        
                        result = sql_tool.invoke({
                            "query": sql_query,
                            "source_id": source_id
                        })
                        
                        tool_results["sql_result"] = result
                        logger.info(f"    ✅ SQL query executed: {len(result)} chars")
                    else:
                        logger.warning(f"    ⚠️ No relevant tables found for SQL query")
                else:
                    logger.warning(f"    ⚠️ SQL source selected but no equipment ID found")
                    tool_results["sql_result"] = "SQL-Daten: Keine Equipment-ID gefunden."
            
            else:
                logger.warning(f"    ⚠️ Unknown tool: {tool_name}")
        
        except Exception as e:
            logger.error(f"    ❌ Tool {tool_name} failed: {e}", exc_info=True)
            tool_results[f"{source_id}_error"] = str(e)
    
    # =========================================================================
    # STEP 4: Store Results in State
    # =========================================================================
    logger.info("💾 Step 4: Storing results in state")
    
    state["tool_outputs"] = tool_results
    
    result_summary = ", ".join([
        f"{key}({len(str(val))} chars)" 
        for key, val in tool_results.items()
    ])
    logger.info(f"  ✅ Results: {result_summary}")
    
    logger.info("🎉 Smart Orchestrator completed successfully")
    
    return state


# CRM Node REMOVED (Phase 3 Cleanup)
# -------------------------------------------------
# The CRM Node was redundant - Knowledge Node already calls get_crm_facts
# directly via the Source Catalog (tool_name == "get_crm_facts").
# Workflow simplified: Router → Knowledge → Generator
# -------------------------------------------------


def _format_chat_history(messages: List[AnyMessage]) -> str:
    """
    Formatiert die Chat-History für den Prompt.

    Nimmt die letzten Nachrichten (außer der aktuellen Frage) und
    formatiert sie als lesbaren Gesprächsverlauf.

    Args:
        messages: Liste aller Nachrichten im State

    Returns:
        Formatierter String der Chat-History
    """
    if len(messages) <= 1:
        return "(Keine vorherige Konversation)"

    # Alle Nachrichten außer der letzten (aktuelle Frage)
    history_messages = messages[:-1]

    # Nur die letzten 6 Nachrichten für Kontext (3 Runden)
    history_messages = history_messages[-6:]

    if not history_messages:
        return "(Keine vorherige Konversation)"

    formatted = []
    for msg in history_messages:
        if isinstance(msg, HumanMessage):
            formatted.append(f"Benutzer: {msg.content}")
        elif isinstance(msg, AIMessage):
            # Kürze lange Antworten
            content = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
            formatted.append(f"Assistent: {content}")

    return "\n".join(formatted)


async def generation_node(state: AgentState) -> AgentState:
    """
    Generator Node: Synthesiert finale Antwort aus Multi-Source Contexts (Phase 3).

    Kombiniert:
    - Chat-History (für Kontext bei Folgefragen!)
    - Knowledge Base (Vector + Graph)
    - CRM Live Data
    - SQL/IoT Data

    Der LLM versteht die Zusammenhänge zwischen den Quellen UND den Chat-Verlauf.
    """
    logger.info("✍️ [GENERATOR] Synthesizing answer from multiple sources")

    # Hole User Query (letzte HumanMessage)
    user_message = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            user_message = msg.content
            break

    if not user_message:
        user_message = "Unbekannte Frage"

    # Formatiere Chat-History für Kontext
    chat_history = _format_chat_history(state["messages"])
    logger.info(f"  📜 Chat history: {len(state['messages'])-1} previous messages")

    # Sammle alle verfügbaren Informationen
    tool_outputs = state.get("tool_outputs", {})
    intent = state.get("intent", "general")
    entity_uncertain = state.get("entity_uncertain", False)
    
    # CHECK: Wenn Entity Match unsicher ist, User um Klarstellung bitten
    if entity_uncertain and state.get("crm_target"):
        logger.warning("⚠️ Entity match was uncertain - asking user for clarification")
        
        # Hole den Namen der gefundenen Entity aus dem Graph Context
        kb_result = tool_outputs.get("knowledge_result", "")
        
        clarification_message = """Ich habe mehrere mögliche Treffer gefunden und bin mir nicht ganz sicher, welche Person oder Firma Sie meinen. 

Können Sie bitte präzisieren:
- Meinen Sie einen Kontakt (Person) oder ein Unternehmen (Account)?
- Falls möglich, können Sie den vollständigen Namen nennen?

Das hilft mir, Ihnen die korrekten Informationen zu liefern."""
        
        state["messages"].append(AIMessage(content=clarification_message))
        return state
    
    # Baue strukturierten Kontext für die Antwort
    context_parts = []
    sources_used = []
    
    # Knowledge Base (Vector + Graph) - Der "Glue"!
    if "knowledge_result" in tool_outputs and tool_outputs["knowledge_result"]:
        kb_result = tool_outputs["knowledge_result"]
        # Only exclude if it's an actual error, not just "no vector results"
        # The result may have graph data even if vector search found nothing
        has_graph_data = "GRAPH WISSEN" in kb_result and "Graph-Daten verfügbar" not in kb_result
        has_vector_data = "TEXT WISSEN" in kb_result and "Keine relevanten Textabschnitte" not in kb_result
        is_error = "Error" in kb_result or "nicht verfügbar" in kb_result

        if (has_graph_data or has_vector_data) and not is_error:
            context_parts.append(f"=== WISSENSDATENBANK (Dokumente + Knowledge Graph) ===\n{kb_result}")
            sources_used.append("knowledge_base")
            logger.info("  ✓ Including knowledge_base context")
    
    # CRM Live Data
    if "crm_result" in tool_outputs and tool_outputs["crm_result"]:
        crm_result = tool_outputs["crm_result"]
        if "Error" not in crm_result and "Keine" not in crm_result:
            context_parts.append(f"\n=== LIVE CRM-DATEN (Aktuelle Informationen) ===\n{crm_result}")
            sources_used.append("crm")
            logger.info("  ✓ Including CRM context")
    
    # SQL/IoT Data
    if "sql_result" in tool_outputs and tool_outputs["sql_result"]:
        sql_result = tool_outputs["sql_result"]
        if "Error" not in sql_result and "Keine" not in sql_result:
            context_parts.append(f"\n=== ECHTZEIT-DATEN (Sensoren/Datenbank) ===\n{sql_result}")
            sources_used.append("sql")
            logger.info("  ✓ Including SQL context")
    
    # Kombiniere alle Kontexte
    if context_parts:
        context = "\n\n".join(context_parts)
        logger.info(f"  📊 Combined context from {len(sources_used)} sources: {sources_used}")
    else:
        context = "Keine relevanten Informationen gefunden."
        logger.warning("  ⚠️ No context available for answer generation")
    
    # Generiere finale Antwort
    llm = get_llm(temperature=0.7, streaming=False)

    # Lade Answer Generation Prompt aus File
    generation_prompt = get_prompt("answer_generation")

    # Lade Company Context aus MinIO (mit Cache)
    company_context = await get_company_context()

    try:
        response = await llm.ainvoke([
            SystemMessage(content=generation_prompt.format(
                company_context=company_context,
                chat_history=chat_history,
                context=context,
                query=user_message
            ))
        ])
        
        answer = response.content.strip()
        
        # Füge Antwort zu Messages hinzu
        state["messages"].append(AIMessage(content=answer))
        
        logger.info(f"✅ Generated answer: {len(answer)} chars")
        
    except Exception as e:
        error_msg = f"Entschuldigung, es gab einen Fehler bei der Antwortgenerierung: {str(e)}"
        logger.error(f"❌ Generation failed: {e}", exc_info=True)
        state["messages"].append(AIMessage(content=error_msg))
    
    return state


# =============================================================================
# Routing Logic
# =============================================================================

def should_use_knowledge(state: AgentState) -> str:
    """
    Entscheidet ob Knowledge Orchestrator aufgerufen werden soll.
    Bei "question" → Knowledge Orchestrator
    Bei "general" (Small Talk) → Direkt zum Generator
    """
    intent = state.get("intent", "question")
    return "knowledge" if intent == "question" else "skip_knowledge"


# should_use_crm REMOVED (Phase 3 Cleanup) - CRM handled in Knowledge Node


# =============================================================================
# Workflow Construction
# =============================================================================

def create_chat_workflow() -> StateGraph:
    """
    Erstellt den vereinfachten LangGraph Chat Workflow (Phase 3).

    Flow:
        Router → Knowledge Orchestrator → Generator

    Der Knowledge Orchestrator ist der zentrale Hub:
    - LLM-basierte Source Discovery (Catalog-first!)
    - Entity Resolution via Graph (nur wenn requires_entity_id)
    - CRM/SQL Tool Calls direkt im Knowledge Node

    Returns:
        Compiled StateGraph für den Chat Agenten
    """
    logger.info("🏗️ Building simplified chat workflow graph (Phase 3)")

    # Erstelle den State Graph
    workflow = StateGraph(AgentState)

    # Füge Nodes hinzu (nur 3 Nodes: Router, Knowledge, Generator)
    workflow.add_node("router", router_node)
    workflow.add_node("knowledge", knowledge_node)
    workflow.add_node("generator", generation_node)

    # Setze Entry Point
    workflow.set_entry_point("router")

    # Router → Knowledge oder Generator
    # Bei "question" → Knowledge Orchestrator
    # Bei "general" (Small Talk) → Direkt Generator
    workflow.add_conditional_edges(
        "router",
        should_use_knowledge,
        {
            "knowledge": "knowledge",
            "skip_knowledge": "generator"  # Small Talk
        }
    )

    # Knowledge → Generator (direkt, keine CRM Node mehr!)
    workflow.add_edge("knowledge", "generator")

    # Generator ist das Ende
    workflow.add_edge("generator", END)

    # Compile den Workflow
    app = workflow.compile()

    logger.info("✅ Chat workflow compiled (3 nodes: router, knowledge, generator)")

    return app


# =============================================================================
# Main Workflow Instance
# =============================================================================

# Erstelle den Workflow beim Import
chat_workflow = create_chat_workflow()

