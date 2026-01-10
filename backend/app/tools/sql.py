"""
SQL Tools für LangGraph Agents.
Ermöglicht Zugriff auf externe SQL-Datenbanken.
"""

import json
import logging
from typing import List

from langchain_core.tools import tool
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.prompts import get_prompt
from app.services.sql_connector import get_sql_connector_service

logger = logging.getLogger(__name__)

# Load tool descriptions from prompts folder
_EXECUTE_SQL_QUERY_DESCRIPTION = get_prompt("tool_execute_sql_query")
_GET_SQL_SCHEMA_DESCRIPTION = get_prompt("tool_get_sql_schema")


@tool
def execute_sql_query(query: str, source_id: str = "erp_postgres") -> str:
    __doc__ = _EXECUTE_SQL_QUERY_DESCRIPTION
    logger.info(f"🔧 SQL Tool: Executing query on source '{source_id}'")
    logger.debug(f"Query: {query[:200]}...")
    
    # Sicherheitscheck: Nur SELECT Queries erlauben
    query_upper = query.strip().upper()
    if not query_upper.startswith("SELECT"):
        error_msg = "Error: Nur SELECT Queries sind erlaubt. Keine INSERT, UPDATE oder DELETE."
        logger.warning(f"❌ {error_msg}")
        return error_msg
    
    try:
        # Hole SQL Connector Service
        connector = get_sql_connector_service()
        engine = connector.get_engine(source_id)
        
        # Führe Query aus
        with engine.connect() as connection:
            result = connection.execute(text(query))
            
            # Konvertiere Ergebnisse zu Liste von Dicts
            rows = []
            for row in result:
                row_dict = dict(row._mapping)
                rows.append(row_dict)
            
            # Begrenze die Anzahl der Zeilen für die Rückgabe
            max_rows = 100
            if len(rows) > max_rows:
                logger.warning(f"⚠️ Query returned {len(rows)} rows, limiting to {max_rows}")
                rows = rows[:max_rows]
                truncated_msg = f"\n\n(Hinweis: Ergebnisse auf {max_rows} Zeilen begrenzt)"
            else:
                truncated_msg = ""
            
            # Formatiere als JSON
            if not rows:
                result_str = "Query erfolgreich ausgeführt, aber keine Zeilen gefunden."
            else:
                result_str = json.dumps(rows, indent=2, default=str, ensure_ascii=False)
                result_str += truncated_msg
            
            logger.info(f"✅ Query executed successfully: {len(rows)} rows returned")
            return result_str
    
    except RuntimeError as e:
        # ERP Database URL fehlt - Graceful Failure
        error_msg = (
            "⚠️ ERP-Datenbank ist nicht konfiguriert (fehlende Environment Variable). "
            "Für Kundendaten (Accounts, Leads, Deals, Einwände) verwende bitte das "
            "Knowledge Graph Tool (search_knowledge_base). "
            "Das SQL Tool ist nur für finanzielle Transaktionsdaten gedacht."
        )
        logger.warning(f"❌ ERP Database not configured: {e}")
        return error_msg
            
    except ValueError as e:
        # Source nicht gefunden oder Config-Fehler
        error_msg = f"Error: {str(e)}"
        logger.error(f"❌ Configuration error: {e}")
        return error_msg
        
    except Exception as e:
        # SQL Fehler oder andere Exceptions
        error_msg = f"Error executing query: {str(e)}"
        logger.error(f"❌ Query execution failed: {e}", exc_info=True)
        return error_msg


@tool
def get_sql_schema(source_id: str = "erp_postgres", table_names: List[str] = None) -> str:
    __doc__ = _GET_SQL_SCHEMA_DESCRIPTION
    logger.info(f"🔧 SQL Schema Tool: Getting schema for source '{source_id}'")
    if table_names:
        logger.debug(f"Tables requested: {table_names}")
    
    try:
        # Hole SQL Connector Service
        connector = get_sql_connector_service()
        engine = connector.get_engine(source_id)
        
        # Verwende SQLAlchemy Inspector
        inspector = inspect(engine)
        
        # Hole verfügbare Tabellen
        available_tables = inspector.get_table_names()
        
        # Bestimme, welche Tabellen wir inspizieren
        if table_names:
            tables_to_inspect = [t for t in table_names if t in available_tables]
            missing_tables = [t for t in table_names if t not in available_tables]
            if missing_tables:
                logger.warning(f"⚠️ Tables not found: {missing_tables}")
        else:
            tables_to_inspect = available_tables
        
        if not tables_to_inspect:
            return f"Error: Keine Tabellen gefunden für Source '{source_id}'"
        
        # Sammle Schema-Informationen
        schema_parts = [f"=== SQL Schema für Source: {source_id} ===\n"]
        
        for table_name in tables_to_inspect:
            schema_parts.append(f"\n--- Tabelle: {table_name} ---")
            
            # Hole Spalten
            columns = inspector.get_columns(table_name)
            schema_parts.append("Spalten:")
            
            for col in columns:
                col_name = col['name']
                col_type = str(col['type'])
                nullable = "NULL" if col.get('nullable', True) else "NOT NULL"
                default = f", Default: {col.get('default')}" if col.get('default') else ""
                
                schema_parts.append(f"  - {col_name}: {col_type} {nullable}{default}")
            
            # Hole Primary Keys
            pk = inspector.get_pk_constraint(table_name)
            if pk and pk.get('constrained_columns'):
                pk_cols = ", ".join(pk['constrained_columns'])
                schema_parts.append(f"Primary Key: {pk_cols}")
            
            # Hole Foreign Keys
            fks = inspector.get_foreign_keys(table_name)
            if fks:
                schema_parts.append("Foreign Keys:")
                for fk in fks:
                    fk_cols = ", ".join(fk['constrained_columns'])
                    ref_table = fk['referred_table']
                    ref_cols = ", ".join(fk['referred_columns'])
                    schema_parts.append(f"  - {fk_cols} -> {ref_table}({ref_cols})")
        
        result_str = "\n".join(schema_parts)
        
        logger.info(f"✅ Schema retrieved for {len(tables_to_inspect)} table(s)")
        return result_str
    
    except RuntimeError as e:
        # ERP Database URL fehlt - Graceful Failure
        error_msg = (
            "⚠️ ERP-Datenbank ist nicht konfiguriert (fehlende Environment Variable). "
            "Dieses Tool ist nicht verfügbar. Verwende das Knowledge Graph Tool "
            "(search_knowledge_base) für CRM-Daten."
        )
        logger.warning(f"❌ ERP Database not configured: {e}")
        return error_msg
        
    except ValueError as e:
        # Source nicht gefunden oder Config-Fehler
        error_msg = f"Error: {str(e)}"
        logger.error(f"❌ Configuration error: {e}")
        return error_msg
        
    except Exception as e:
        # Andere Exceptions
        error_msg = f"Error retrieving schema: {str(e)}"
        logger.error(f"❌ Schema retrieval failed: {e}", exc_info=True)
        return error_msg

