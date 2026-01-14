"""
SQL Tools für LangGraph Agents.
Ermöglicht Zugriff auf externe SQL-Datenbanken.

SECURITY ARCHITECTURE NOTE:
==========================
The database user configured for this service MUST have READ-ONLY permissions
at the database level. This is a critical defense-in-depth measure:

1. Create a dedicated read-only database user:
   CREATE USER sql_tool_reader WITH PASSWORD 'xxx';
   GRANT CONNECT ON DATABASE yourdb TO sql_tool_reader;
   GRANT USAGE ON SCHEMA public TO sql_tool_reader;
   GRANT SELECT ON ALL TABLES IN SCHEMA public TO sql_tool_reader;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO sql_tool_reader;

2. Use this user in the connection string (ERP_DATABASE_URL env var).

This ensures that even if SQL injection bypasses application-level validation,
the attacker cannot modify data due to database-level permissions.
"""

import json
import logging
import re
from typing import List, Tuple

import sqlparse
from langchain_core.tools import tool
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.prompts import get_prompt
from app.services.sql_connector import get_sql_connector_service

logger = logging.getLogger(__name__)

# Load tool descriptions from prompts folder
_EXECUTE_SQL_QUERY_DESCRIPTION = get_prompt("tool_execute_sql_query")
_GET_SQL_SCHEMA_DESCRIPTION = get_prompt("tool_get_sql_schema")


# =============================================================================
# Security: SQL Query Validation using sqlparse
# =============================================================================

class SQLSecurityError(Exception):
    """Raised when a SQL query fails security validation."""
    pass


def validate_sql_query(query: str) -> Tuple[bool, str]:
    """
    Validate a SQL query for security using sqlparse.

    This implements a whitelist approach:
    1. Parse the query using sqlparse
    2. Verify exactly ONE statement (no statement stacking)
    3. Verify the statement type is SELECT (whitelist)
    4. Check for suspicious patterns that indicate injection attempts

    Args:
        query: The SQL query string to validate

    Returns:
        Tuple of (is_valid, error_message)
        If is_valid is True, error_message is empty.
        If is_valid is False, error_message explains why.
    """
    if not query or not query.strip():
        return False, "Query cannot be empty"

    # Step 1: Parse with sqlparse
    try:
        statements = sqlparse.parse(query)
    except Exception as e:
        logger.warning(f"SQL parsing failed: {e}")
        return False, f"Failed to parse SQL query: {e}"

    # Step 2: Verify exactly ONE statement (prevents statement stacking)
    # Filter out empty statements (sqlparse may return empty ones for trailing semicolons)
    non_empty_statements = [s for s in statements if s.get_type() != 'UNKNOWN' or str(s).strip()]

    if len(non_empty_statements) == 0:
        return False, "No valid SQL statement found"

    if len(non_empty_statements) > 1:
        return False, (
            "Multiple SQL statements detected (statement stacking). "
            "Only single SELECT queries are allowed."
        )

    statement = non_empty_statements[0]

    # Step 3: Verify statement type is SELECT (whitelist approach)
    stmt_type = statement.get_type()

    # sqlparse returns the type as uppercase string
    if stmt_type != 'SELECT':
        return False, (
            f"Statement type '{stmt_type}' is not allowed. "
            f"Only SELECT queries are permitted."
        )

    # Step 4: Check for dangerous patterns that might bypass sqlparse detection
    query_upper = query.upper()

    # 4a: Check for UNION (data exfiltration from other tables)
    if 'UNION' in query_upper:
        return False, (
            "UNION queries are not allowed. "
            "This prevents unauthorized access to other tables."
        )

    # 4b: Check for information_schema access (schema enumeration)
    if 'INFORMATION_SCHEMA' in query_upper:
        return False, (
            "Access to INFORMATION_SCHEMA is not allowed. "
            "Use the get_sql_schema tool to inspect table structures."
        )

    # 4c: Check for SQL comments (often used to hide injection)
    if '--' in query or '/*' in query or '#' in query:
        return False, (
            "SQL comments (-- or /* or #) are not allowed. "
            "Please provide a clean query without comments."
        )

    # 4d: Check for suspicious always-true conditions (common injection pattern)
    # This is a heuristic - legitimate queries rarely use these patterns
    always_true_patterns = [
        r"'\s*'\s*=\s*'",       # '' = ''
        r"1\s*=\s*1",           # 1=1
        r"'1'\s*=\s*'1'",       # '1'='1'
        r"OR\s+1\s*=\s*1",      # OR 1=1
        r"OR\s+'1'\s*=\s*'1'",  # OR '1'='1'
    ]

    for pattern in always_true_patterns:
        if re.search(pattern, query_upper):
            return False, (
                "Suspicious pattern detected (always-true condition). "
                "This pattern is commonly used in SQL injection attacks."
            )

    # 4e: Check for time-based blind injection attempts
    time_functions = ['SLEEP', 'WAITFOR', 'BENCHMARK', 'PG_SLEEP']
    for func in time_functions:
        if func in query_upper:
            return False, (
                f"Time-based function '{func}' is not allowed. "
                "This pattern is commonly used in blind SQL injection."
            )

    # 4f: Check for subqueries that could access other tables
    # This is optional - you might want to allow subqueries in some cases
    # Uncomment if you want strict single-table access:
    # if re.search(r'\(\s*SELECT', query_upper):
    #     return False, "Subqueries are not allowed for security reasons."

    logger.debug(f"SQL query passed security validation: {query[:50]}...")
    return True, ""


@tool
def execute_sql_query(query: str, source_id: str = "erp_postgres") -> str:
    """Führt eine SQL SELECT Query auf einer externen Datenbank aus (z.B. IoT, ERP).

    Nur SELECT Queries sind erlaubt (keine INSERT, UPDATE, DELETE).
    Security validation using sqlparse ensures single-statement SELECT only.

    Args:
        query: Die SQL SELECT Query
        source_id: Die ID der Datenquelle (z.B. "iot_database", "erp_postgres")

    Returns:
        Query-Ergebnisse als JSON
    """
    logger.info(f"🔧 SQL Tool: Executing query on source '{source_id}'")
    logger.debug(f"Query: {query[:200]}...")

    # SECURITY: Comprehensive query validation using sqlparse
    # This is the first line of defense - validates query structure and patterns
    is_valid, error_message = validate_sql_query(query)
    if not is_valid:
        logger.warning(f"❌ SQL security validation failed: {error_message}")
        return f"Security Error: {error_message}"

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
    """Holt das Datenbank-Schema (Tabellen, Spalten, Keys) einer SQL-Datenquelle.
    
    Hilfreich um zu verstehen welche Daten verfügbar sind bevor eine Query geschrieben wird.
    
    Args:
        source_id: Die ID der Datenquelle (z.B. "iot_database", "erp_postgres")
        table_names: Optional - Liste von Tabellen-Namen (wenn leer, werden alle Tabellen zurückgegeben)
        
    Returns:
        Datenbank-Schema als formatierter Text
    """
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
