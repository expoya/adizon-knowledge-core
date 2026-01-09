"""
LangGraph Chat Workflow für Agentic RAG.
Kombiniert Knowledge Base Search und SQL Query Execution.
"""

import json
import logging
import re
from typing import Any, Dict, List, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from app.core.llm import get_llm
from app.services.metadata_store import metadata_service
from app.services.graph_store import get_graph_store_service
from app.tools.knowledge import search_knowledge_base
from app.tools.sql import execute_sql_query, get_sql_schema
from app.tools.crm import get_crm_facts

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Functions
# =============================================================================

def _get_next_node_name(intent: str) -> str:
    """Helper: Get next node name for debug logging."""
    if intent == "sql":
        return "sql_node"
    elif intent == "knowledge":
        return "knowledge_node"
    elif intent == "crm":
        return "crm_node"
    else:
        return "knowledge_node (fallback)"


# =============================================================================
# State Definition
# =============================================================================

class AgentState(TypedDict):
    """State für den Chat Agenten."""
    messages: List[AnyMessage]
    intent: str  # "general", "sql", "knowledge", "hybrid", "crm"
    sql_context: Dict[str, Any]  # {"source_id": "...", "table_names": [...]}
    crm_target: str  # Entity ID für CRM-Abfrage (z.B. "zoho_123456")
    tool_outputs: Dict[str, str]  # {"sql_result": "...", "knowledge_result": "...", "crm_result": "..."}


# =============================================================================
# Node Implementations
# =============================================================================

async def router_node(state: AgentState) -> AgentState:
    """
    Router Node: Klassifiziert die User-Query und entscheidet über den Workflow.
    
    Prüft:
    1. Ob die Query nach strukturierten Daten (SQL) klingt
    2. Ob relevante Tabellen im MetadataService gefunden werden
    3. Setzt intent entsprechend: "sql", "knowledge", oder "hybrid"
    """
    logger.info("🔀 Router Node: Analyzing user intent")
    
    # Hole letzte User-Nachricht
    user_message = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            user_message = msg.content
            break
    
    if not user_message:
        logger.warning("⚠️ No user message found in state")
        state["intent"] = "knowledge"
        return state
    
    # STRICT DEBUG LOGGING
    logger.info(f"[ROUTER] User Query: {user_message}")
    logger.debug(f"Analyzing query: {user_message[:100]}...")
    
    # Verwende LLM für Intent Classification
    llm = get_llm(temperature=0.0, streaming=False)
    
    classification_prompt = """Du bist ein Intent Classifier für einen RAG Agenten.

Analysiere die folgende Benutzeranfrage und klassifiziere sie:

INTENT TYPES:
- "sql": Frage nach finanziellen Daten aus dem ERP-System (Rechnungen, Zahlungen, Buchhaltung, Finanztransaktionen)
- "knowledge": Frage nach CRM-Daten (Kunden, Accounts, Leads, Deals, Kontakte, Einwände, Meetings) ODER Frage nach Dokumenten, Konzepten, Erklärungen, Prozessen aus der Wissensdatenbank
- "general": Allgemeine Konversation oder Small Talk

WICHTIG:
- Kunden, Accounts, Leads, Deals, Kontakte, Einwände → "knowledge" (CRM-Daten im Graph)
- Rechnungen, Zahlungen, Buchhaltung → "sql" (ERP-Daten in PostgreSQL)

BENUTZERANFRAGE:
{query}

Antworte NUR mit einem der drei Wörter: sql, knowledge, oder general
Keine Erklärung, nur das Klassifikations-Wort!"""
    
    try:
        classification_result = await llm.ainvoke([
            SystemMessage(content=classification_prompt.format(query=user_message))
        ])
        intent_raw = classification_result.content.strip().lower()
        
        # Extrahiere Intent
        if "sql" in intent_raw:
            initial_intent = "sql"
        elif "knowledge" in intent_raw:
            initial_intent = "knowledge"
        else:
            initial_intent = "general"
        
        # STRICT DEBUG LOGGING
        logger.info(f"[ROUTER] LLM Classification Result: '{intent_raw}' → Intent: '{initial_intent}'")
        
    except Exception as e:
        logger.error(f"❌ Intent classification failed: {e}")
        initial_intent = "knowledge"  # Fallback
    
    # Wenn SQL Intent: Prüfe ob relevante Tabellen existieren
    if initial_intent == "sql":
        try:
            metadata_svc = metadata_service()
            relevant_tables_info = metadata_svc.get_relevant_tables(user_message)
            
            logger.debug(f"Metadata search result: {relevant_tables_info[:200]}...")
            
            # Prüfe ob Tabellen gefunden wurden
            if "Keine relevanten Tabellen" not in relevant_tables_info:
                # Parse die Tabellen-Info (primitive Extraktion)
                # Format: "1. Quelle: erp_postgres ... Tabelle: invoices ..."
                source_ids = re.findall(r'Quelle: (\w+)', relevant_tables_info)
                table_names = re.findall(r'Tabelle: (\w+)', relevant_tables_info)
                
                if source_ids and table_names:
                    state["sql_context"] = {
                        "source_id": source_ids[0],  # Nehme erste Source
                        "table_names": table_names,
                        "metadata_info": relevant_tables_info
                    }
                    state["intent"] = "sql"
                    logger.info(f"✅ SQL intent confirmed. Tables: {table_names}, Source: {source_ids[0]}")
                else:
                    # Keine konkreten Tabellen gefunden, falle zurück
                    state["intent"] = "knowledge"
                    logger.info("⚠️ No specific tables found, falling back to knowledge")
            else:
                # Keine relevanten Tabellen
                state["intent"] = "knowledge"
                logger.info("⚠️ No relevant tables found, falling back to knowledge")
                
        except Exception as e:
            logger.error(f"❌ Metadata search failed: {e}")
            state["intent"] = "knowledge"
    else:
        # Knowledge oder General Intent
        state["intent"] = initial_intent
    
    # STRICT DEBUG LOGGING - Final Intent
    logger.info(f"[ROUTER] ✅ Final Intent Decision: '{state['intent']}'")
    logger.info(f"[ROUTER] Next Node: {_get_next_node_name(state['intent'])}")
    
    # CRM-Check: Suche nach Entities mit CRM-ID im Graph
    # Wenn eine spezifische Person/Firma erwähnt wird, holen wir Live-Facts
    if state["intent"] in ["knowledge", "general"]:
        try:
            logger.info("🔍 Checking for CRM entities in query...")
            
            # Suche im Graph nach Entities mit source_id
            graph_store = get_graph_store_service()
            
            # Cypher Query: Suche nach Nodes mit source_id die mit "zoho_" beginnen
            # und deren Name in der Query erwähnt wird
            cypher_query = """
            MATCH (n)
            WHERE n.source_id STARTS WITH 'zoho_'
            AND toLower($query) CONTAINS toLower(n.name)
            RETURN n.source_id as source_id, n.name as name, labels(n)[0] as type
            LIMIT 1
            """
            
            # Führe Query aus mit der query() Methode
            result = await graph_store.query(
                cypher_query,
                parameters={"query": user_message}
            )
            
            if result and len(result) > 0:
                record = result[0]
                source_id = record.get("source_id")
                entity_name = record.get("name")
                entity_type = record.get("type")
                
                if source_id:
                    logger.info(f"✅ Found CRM entity: {entity_name} ({entity_type}) with ID: {source_id}")
                    state["crm_target"] = source_id
                    state["intent"] = "crm"  # Override intent für CRM-Pfad
                else:
                    logger.debug("  ℹ️ No CRM entities found in query")
            else:
                logger.debug("  ℹ️ No CRM entities found in query")
                
        except Exception as e:
            logger.warning(f"⚠️ CRM entity search failed: {e}")
            # Continue without CRM - non-fatal error
    
    return state


async def sql_node(state: AgentState) -> AgentState:
    """
    SQL Node: Generiert und führt SQL Query basierend auf User-Frage aus.
    """
    logger.info("[SQL_NODE] 🗄️ Executing SQL Node")
    logger.info("[SQL_NODE] Tool: execute_sql_query & get_sql_schema")
    
    # Hole SQL Context
    sql_context = state.get("sql_context", {})
    source_id = sql_context.get("source_id")
    table_names = sql_context.get("table_names", [])
    
    if not source_id or not table_names:
        error_msg = "Error: Keine SQL-Kontext-Informationen verfügbar."
        logger.error(f"❌ {error_msg}")
        state["tool_outputs"]["sql_result"] = error_msg
        return state
    
    # Hole User Query
    user_message = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            user_message = msg.content
            break
    
    if not user_message:
        state["tool_outputs"]["sql_result"] = "Error: Keine User-Query gefunden."
        return state
    
    try:
        # Schritt 1: Hole detailliertes Schema
        logger.info(f"📋 Getting schema for tables: {table_names}")
        schema_info = get_sql_schema.invoke({
            "source_id": source_id,
            "table_names": table_names
        })
        
        logger.debug(f"Schema info: {schema_info[:500]}...")
        
        # Schritt 2: Generiere SQL Query mit LLM
        llm = get_llm(temperature=0.0, streaming=False)
        
        sql_generation_prompt = """Du bist ein PostgreSQL-Experte. Generiere eine sichere SELECT Query basierend auf der Benutzeranfrage und dem bereitgestellten Schema.

WICHTIGE REGELN:
- Verwende NUR SELECT Statements (kein INSERT, UPDATE, DELETE)
- Nutze die korrekten Tabellen- und Spaltennamen aus dem Schema
- Verwende PostgreSQL-Syntax
- Gib NUR die SQL Query zurück, keine Erklärung
- Die Query sollte in einer Zeile oder sauber formatiert sein

SCHEMA:
{schema}

BENUTZERANFRAGE:
{query}

SQL QUERY:"""
        
        sql_response = await llm.ainvoke([
            SystemMessage(content=sql_generation_prompt.format(
                schema=schema_info,
                query=user_message
            ))
        ])
        
        # Extrahiere SQL Query aus der Antwort
        sql_query_raw = sql_response.content.strip()
        
        # Säubere die Query (entferne Markdown Code Blocks etc.)
        sql_query = re.sub(r'```sql\s*', '', sql_query_raw)
        sql_query = re.sub(r'```\s*', '', sql_query)
        sql_query = sql_query.strip()
        
        logger.info(f"🔍 Generated SQL: {sql_query[:200]}...")
        
        # Schritt 3: Führe SQL Query aus
        logger.info("⚡ Executing SQL query...")
        sql_result = execute_sql_query.invoke({
            "query": sql_query,
            "source_id": source_id
        })
        
        # Speichere Ergebnis
        state["tool_outputs"]["sql_result"] = f"SQL Query:\n{sql_query}\n\nErgebnis:\n{sql_result}"
        
        if "Error" in sql_result:
            logger.warning(f"⚠️ SQL execution had errors: {sql_result[:200]}")
        else:
            logger.info("✅ SQL query executed successfully")
        
    except Exception as e:
        error_msg = f"Error in SQL processing: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        state["tool_outputs"]["sql_result"] = error_msg
    
    return state


async def knowledge_node(state: AgentState) -> AgentState:
    """
    Knowledge Node: Durchsucht die interne Wissensdatenbank.
    """
    logger.info("[KNOWLEDGE_NODE] 📚 Executing Knowledge Node")
    logger.info("[KNOWLEDGE_NODE] Tool: search_knowledge_base (Vector + Graph)")
    
    # Hole User Query
    user_message = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            user_message = msg.content
            break
    
    if not user_message:
        state["tool_outputs"]["knowledge_result"] = "Error: Keine User-Query gefunden."
        return state
    
    try:
        # Suche in Knowledge Base
        logger.info(f"🔍 Searching for: {user_message[:100]}...")
        knowledge_result = await search_knowledge_base.ainvoke({"query": user_message})
        
        # Speichere Ergebnis
        state["tool_outputs"]["knowledge_result"] = knowledge_result
        
        # Log Ergebnis
        if "Keine relevanten" in knowledge_result or "nicht verfügbar" in knowledge_result:
            logger.info("⚠️ No relevant knowledge found")
        else:
            logger.info(f"✅ Knowledge retrieved: {len(knowledge_result)} chars")
        
    except Exception as e:
        error_msg = f"Error in knowledge search: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        state["tool_outputs"]["knowledge_result"] = error_msg
    
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
    Generation Node: Generiert die finale Antwort basierend auf allen Tool-Outputs.
    """
    logger.info("✍️ Generation Node: Creating final answer")
    
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
    
    # Baue Kontext für die Antwort
    context_parts = []
    
    if "sql_result" in tool_outputs and tool_outputs["sql_result"]:
        context_parts.append(f"DATENBANK-ERGEBNISSE:\n{tool_outputs['sql_result']}")
    
    if "knowledge_result" in tool_outputs and tool_outputs["knowledge_result"]:
        context_parts.append(f"WISSENSDATENBANK:\n{tool_outputs['knowledge_result']}")
    
    if "crm_result" in tool_outputs and tool_outputs["crm_result"]:
        context_parts.append(f"CRM LIVE-DATEN:\n{tool_outputs['crm_result']}")
    
    context = "\n\n".join(context_parts) if context_parts else "Keine Informationen gefunden."
    
    # Generiere finale Antwort
    llm = get_llm(temperature=0.7, streaming=False)
    
    generation_prompt = """Du bist Adizon, ein hilfreicher Wissens-Assistent für ein Unternehmen.

Deine Aufgabe ist es, die Benutzeranfrage basierend auf den bereitgestellten Informationen zu beantworten.

WICHTIGE REGELN:
- Antworte präzise und strukturiert auf Deutsch
- Verwende NUR die bereitgestellten Informationen
- Wenn keine relevanten Informationen vorhanden sind, sage das ehrlich
- Zitiere Fakten aus dem Kontext
- Verwende KEIN Markdown, nur reinen Text
- Erwähne NICHT "Datenbank-Ergebnisse" oder "Wissensdatenbank", sondern integriere die Informationen natürlich
- Bei Zahlen und Fakten aus Datenbanken: Sei präzise
- Bei Dokumenten-Wissen: Nenne die Quelle, falls angegeben

VERFÜGBARE INFORMATIONEN:
{context}

BENUTZERANFRAGE:
{query}

ANTWORT:"""
    
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

def should_use_sql(state: AgentState) -> str:
    """Entscheidet ob SQL Node aufgerufen werden soll."""
    intent = state.get("intent", "")
    return "sql" if intent in ["sql", "hybrid"] else "skip_sql"


def should_use_knowledge(state: AgentState) -> str:
    """Entscheidet ob Knowledge Node aufgerufen werden soll."""
    intent = state.get("intent", "")
    return "knowledge" if intent in ["knowledge", "hybrid", "general"] else "skip_knowledge"


def should_use_crm(state: AgentState) -> str:
    """Entscheidet ob CRM Node aufgerufen werden soll."""
    intent = state.get("intent", "")
    has_target = bool(state.get("crm_target"))
    return "crm" if intent == "crm" and has_target else "skip_crm"


# =============================================================================
# Workflow Construction
# =============================================================================

def create_chat_workflow() -> StateGraph:
    """
    Erstellt den LangGraph Chat Workflow.
    
    Returns:
        Compiled StateGraph für den Chat Agenten
    """
    logger.info("🏗️ Building chat workflow graph")
    
    # Erstelle den State Graph
    workflow = StateGraph(AgentState)
    
    # Füge Nodes hinzu
    workflow.add_node("router", router_node)
    workflow.add_node("sql", sql_node)
    workflow.add_node("knowledge", knowledge_node)
    workflow.add_node("crm", crm_node)
    workflow.add_node("generator", generation_node)
    
    # Setze Entry Point
    workflow.set_entry_point("router")
    
    # Conditional Edges vom Router
    # Router entscheidet: SQL, Knowledge, oder CRM
    workflow.add_conditional_edges(
        "router",
        should_use_sql,
        {
            "sql": "sql",
            "skip_sql": "knowledge"  # Wenn kein SQL, prüfe Knowledge/CRM
        }
    )
    
    # SQL Node geht zu Generator
    workflow.add_edge("sql", "generator")
    
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
    
    logger.info("✅ Chat workflow graph compiled successfully")
    
    return app


# =============================================================================
# Main Workflow Instance
# =============================================================================

# Erstelle den Workflow beim Import
chat_workflow = create_chat_workflow()

