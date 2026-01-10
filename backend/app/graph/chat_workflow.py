"""
LangGraph Chat Workflow für Agentic RAG (Phase 1 - Simplified).
Knowledge Orchestrator mit optionalem CRM Access.
"""

import logging
from typing import Dict, List, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from app.core.llm import get_llm
from app.services.graph_store import get_graph_store_service
from app.tools.knowledge import search_knowledge_base
from app.tools.crm import get_crm_facts
from app.prompts import get_prompt

logger = logging.getLogger(__name__)


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
    Router Node: Vereinfachte Intent Classification.
    
    Entscheidet nur noch zwischen:
    - "question": Fachliche Frage → Knowledge Orchestrator
    - "general": Small Talk → Direkt zum Generator
    
    Optional: Sucht nach CRM-Entities im Graph für Live-Daten.
    """
    logger.info("🔀 Router Node: Simple intent classification")
    
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
    
    logger.info(f"[ROUTER] User Query: {user_message}")
    
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
        
        logger.info(f"[ROUTER] Intent: '{state['intent']}'")
        
    except Exception as e:
        logger.error(f"❌ Intent classification failed: {e}")
        state["intent"] = "question"  # Fallback zu question (besser als general)
    
    # Bei Fragen: Suche optional nach CRM-Entities im Graph
    if state["intent"] == "question":
        try:
            logger.info("🔍 Checking for CRM entities in query...")
            
            graph_store = get_graph_store_service()
            
            # Smart Entity Resolution mit Relevanz-Scoring
            # Sucht in: name, company, account_name_name, contact_name_name, first_name + last_name
            cypher_query = """
            MATCH (n)
            WHERE n.source_id STARTS WITH 'zoho_'
            WITH n, $query as query
            // Calculate relevance score based on multiple fields
            WITH n, query,
              CASE 
                // Exact matches (highest score)
                WHEN toLower(coalesce(n.name, '')) = toLower(query) THEN 100
                WHEN toLower(coalesce(n.company, '')) = toLower(query) THEN 100
                WHEN toLower(coalesce(n.account_name, '')) = toLower(query) THEN 100
                // Full phrase matches
                WHEN toLower(coalesce(n.name, '')) CONTAINS toLower(query) THEN 50
                WHEN toLower(coalesce(n.company, '')) CONTAINS toLower(query) THEN 50
                WHEN toLower(coalesce(n.account_name_name, '')) CONTAINS toLower(query) THEN 50
                // Partial word matches
                WHEN ANY(word IN split(toLower(query), ' ') WHERE 
                    toLower(coalesce(n.name, '')) CONTAINS word OR
                    toLower(coalesce(n.company, '')) CONTAINS word OR
                    toLower(coalesce(n.first_name, '')) CONTAINS word OR
                    toLower(coalesce(n.last_name, '')) CONTAINS word
                ) THEN 25
                ELSE 0
              END as match_score,
              // Entity type priority (Contact/Account > Events/Tasks)
              CASE labels(n)[0]
                WHEN 'Contact' THEN 10
                WHEN 'Account' THEN 9
                WHEN 'Lead' THEN 8
                WHEN 'Deal' THEN 7
                WHEN 'User' THEN 6
                ELSE 1
              END as type_score
            WHERE match_score > 0
            RETURN 
              n.source_id as source_id, 
              coalesce(n.name, n.account_name, n.company, 'Unknown') as name,
              labels(n)[0] as type,
              (match_score + type_score) as total_score
            ORDER BY total_score DESC
            LIMIT 3
            """
            
            result = await graph_store.query(
                cypher_query,
                parameters={"query": user_message}
            )
            
            if result and len(result) > 0:
                # Bester Match
                best_match = result[0]
                source_id = best_match.get("source_id")
                entity_name = best_match.get("name")
                entity_type = best_match.get("type")
                best_score = best_match.get("total_score", 0)
                
                # Check if match is confident (score > 60)
                if best_score >= 60:
                    logger.info(f"✅ Confident match: {entity_name} ({entity_type}) with ID: {source_id} [Score: {best_score}]")
                    state["crm_target"] = source_id
                else:
                    # Multiple candidates with similar scores - log for transparency
                    logger.warning(f"⚠️ Uncertain match (Score: {best_score}): {entity_name} ({entity_type})")
                    logger.info(f"  Other candidates: {[r.get('name') for r in result[1:]]}")
                    
                    # Use best match but note uncertainty in state
                    state["crm_target"] = source_id
                    state["entity_uncertain"] = True
            else:
                logger.debug("  ℹ️ No entities found in query")
                
        except Exception as e:
            logger.warning(f"⚠️ Entity search failed: {e}")
            # Continue without CRM - non-fatal error
    
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
        relevant_sources = await metadata_svc.get_relevant_sources_llm(
            query=user_message,
            max_sources=3
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
            
            # Smart Entity Resolution mit Relevanz-Scoring
            cypher_query = """
            MATCH (n)
            WHERE n.source_id STARTS WITH 'zoho_' OR n.source_id STARTS WITH 'iot_'
            WITH n, $query as query
            // Calculate relevance score based on multiple fields
            WITH n, query,
              CASE 
                // Exact matches (highest score)
                WHEN toLower(coalesce(n.name, '')) = toLower(query) THEN 100
                WHEN toLower(coalesce(n.company, '')) = toLower(query) THEN 100
                WHEN toLower(coalesce(n.account_name, '')) = toLower(query) THEN 100
                // Full phrase matches
                WHEN toLower(coalesce(n.name, '')) CONTAINS toLower(query) THEN 50
                WHEN toLower(coalesce(n.company, '')) CONTAINS toLower(query) THEN 50
                WHEN toLower(coalesce(n.account_name_name, '')) CONTAINS toLower(query) THEN 50
                // Partial word matches
                WHEN ANY(word IN split(toLower(query), ' ') WHERE 
                    toLower(coalesce(n.name, '')) CONTAINS word OR
                    toLower(coalesce(n.company, '')) CONTAINS word OR
                    toLower(coalesce(n.first_name, '')) CONTAINS word OR
                    toLower(coalesce(n.last_name, '')) CONTAINS word
                ) THEN 25
                ELSE 0
              END as match_score,
              // Entity type priority
              CASE labels(n)[0]
                WHEN 'Contact' THEN 10
                WHEN 'Account' THEN 9
                WHEN 'Lead' THEN 8
                WHEN 'Deal' THEN 7
                WHEN 'User' THEN 6
                ELSE 1
              END as type_score
            WHERE match_score > 0
            RETURN 
              n.source_id as source_id,
              coalesce(n.name, n.account_name, n.company, 'Unknown') as name,
              labels(n)[0] as type,
              (match_score + type_score) as total_score
            ORDER BY total_score DESC
            LIMIT 5
            """
            
            entities = await graph_store.query(
                cypher_query,
                parameters={"query": user_message}
            )
            
            if entities:
                logger.info(f"  ✅ Found {len(entities)} entity candidates in graph")
                
                # Bester Match (höchster Score)
                best_match = entities[0]
                best_score = best_match.get("total_score", 0)
                best_name = best_match.get("name", "")
                best_type = best_match.get("type", "")
                best_id = best_match.get("source_id", "")
                
                # Log alle Kandidaten für Transparenz
                for i, entity in enumerate(entities):
                    score = entity.get("total_score", 0)
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


async def crm_node(state: AgentState) -> AgentState:
    """
    CRM Node: Holt Live-Fakten aus dem CRM-System.
    """
    logger.info("[CRM_NODE] 📞 Executing CRM Node")
    logger.info("[CRM_NODE] Tool: get_crm_facts")
    
    # Hole CRM Target
    crm_target = state.get("crm_target", "")
    
    if not crm_target:
        error_msg = "Error: Kein CRM-Target im State."
        logger.error(f"❌ {error_msg}")
        state["tool_outputs"]["crm_result"] = error_msg
        return state
    
    # Hole User Query für Context
    user_message = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            user_message = msg.content
            break
    
    query_context = user_message if user_message else "general information"
    
    try:
        # Rufe CRM Tool auf
        logger.info(f"📡 Calling CRM for entity: {crm_target}")
        crm_result = await get_crm_facts.ainvoke({
            "entity_id": crm_target,
            "query_context": query_context
        })
        
        # Speichere Ergebnis
        state["tool_outputs"]["crm_result"] = crm_result
        
        # Log Ergebnis
        if "Error" in crm_result or "Fehler" in crm_result:
            logger.warning(f"⚠️ CRM query had errors: {crm_result[:200]}")
        else:
            logger.info(f"✅ CRM facts retrieved: {len(crm_result)} chars")
        
    except Exception as e:
        error_msg = f"Error in CRM processing: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        state["tool_outputs"]["crm_result"] = error_msg
    
    return state


async def generation_node(state: AgentState) -> AgentState:
    """
    Generator Node: Synthesiert finale Antwort aus Multi-Source Contexts (Phase 3).
    
    Kombiniert:
    - Knowledge Base (Vector + Graph)
    - CRM Live Data
    - SQL/IoT Data
    
    Der LLM versteht die Zusammenhänge zwischen den Quellen.
    """
    logger.info("✍️ [GENERATOR] Synthesizing answer from multiple sources")
    
    # Hole User Query
    user_message = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            user_message = msg.content
            break
    
    if not user_message:
        user_message = "Unbekannte Frage"
    
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
        if "Error" not in kb_result and "Keine" not in kb_result:
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
    
    try:
        response = await llm.ainvoke([
            SystemMessage(content=generation_prompt.format(
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


def should_use_crm(state: AgentState) -> str:
    """
    Entscheidet ob CRM Node aufgerufen werden soll.
    Nur wenn crm_target im State vorhanden ist.
    """
    has_target = bool(state.get("crm_target"))
    return "crm" if has_target else "skip_crm"


# =============================================================================
# Workflow Construction
# =============================================================================

def create_chat_workflow() -> StateGraph:
    """
    Erstellt den vereinfachten LangGraph Chat Workflow (Phase 1).
    
    Flow:
        Router → Knowledge Orchestrator → [optional: CRM] → Generator
    
    Returns:
        Compiled StateGraph für den Chat Agenten
    """
    logger.info("🏗️ Building simplified chat workflow graph (Phase 1)")
    
    # Erstelle den State Graph
    workflow = StateGraph(AgentState)
    
    # Füge Nodes hinzu (SQL Node entfernt!)
    workflow.add_node("router", router_node)
    workflow.add_node("knowledge", knowledge_node)
    workflow.add_node("crm", crm_node)
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
    
    # Knowledge Node prüft ob CRM benötigt wird
    workflow.add_conditional_edges(
        "knowledge",
        should_use_crm,
        {
            "crm": "crm",  # Wenn CRM-Entity gefunden, hole Live-Facts
            "skip_crm": "generator"  # Sonst direkt zum Generator
        }
    )
    
    # CRM Node geht zu Generator
    workflow.add_edge("crm", "generator")
    
    # Generator ist das Ende
    workflow.add_edge("generator", END)
    
    # Compile den Workflow
    app = workflow.compile()
    
    logger.info("✅ Chat workflow compiled (4 nodes: router, knowledge, crm, generator)")
    
    return app


# =============================================================================
# Main Workflow Instance
# =============================================================================

# Erstelle den Workflow beim Import
chat_workflow = create_chat_workflow()

