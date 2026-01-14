"""
Critical Security Tests for adizon-knowledge-core.

Tests for injection vulnerabilities that must FAIL (Red) if the security hole exists.
These tests verify that malicious inputs are properly blocked or sanitized.

Priority: CRITICAL
Categories: Cypher Injection, SQL Injection, Path Traversal

Author: Security Audit
"""

import hashlib
import pytest
import re
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import UploadFile
from io import BytesIO


# =============================================================================
# TEST CATEGORY 1: CYPHER INJECTION (3.2 - 3.4)
# =============================================================================

class TestCypherInjection:
    """
    Tests for Cypher Injection vulnerabilities in the Graph Query endpoint.

    Tests verify that the validate_cypher_query function properly blocks
    dangerous Cypher operations.
    """

    def test_cypher_injection_detach_delete_blocked(self):
        """
        Test 3.2: DETACH DELETE should be blocked.

        Attack: MATCH (n) DETACH DELETE n
        Impact: Deletes entire database

        This test verifies that DELETE queries are rejected by validation.
        """
        from app.api.endpoints.graph import validate_cypher_query

        dangerous_queries = [
            "MATCH (n) DETACH DELETE n",
            "MATCH (n) DELETE n",
            "MATCH (n)-[r]-() DELETE r",
            "MATCH (n:User) DETACH DELETE n",
            # Case variations
            "match (n) detach delete n",
            "MATCH (n) detach DELETE n",
            # With WHERE clause (targeted deletion)
            "MATCH (n) WHERE n.name = 'test' DETACH DELETE n",
            # Hidden in subquery
            "MATCH (n) WITH n LIMIT 1 DETACH DELETE n",
        ]

        for query in dangerous_queries:
            is_valid, error_message = validate_cypher_query(query)

            if is_valid:
                pytest.fail(
                    f"SECURITY VULNERABILITY: DELETE query not blocked!\n"
                    f"Query: {query}\n"
                    f"Expected: Query should be rejected.\n"
                    f"Impact: Attacker could delete entire database."
                )

            assert error_message, f"Error message should not be empty for: {query}"
            assert 'delete' in error_message.lower(), f"Error should mention DELETE for: {query}"

    def test_cypher_injection_dbms_procedures_blocked(self):
        """
        Test 3.3: CALL dbms.* procedures should be blocked.

        Attack: CALL dbms.listConfig(), CALL dbms.security.*
        Impact: Access to admin functions, security settings, server config
        """
        from app.api.endpoints.graph import validate_cypher_query

        dangerous_queries = [
            # Config access
            "CALL dbms.listConfig()",
            "CALL dbms.showCurrentUser()",
            # Security procedures
            "CALL dbms.security.listUsers()",
            "CALL dbms.security.createUser('hacker', 'password', false)",
            # System procedures
            "CALL dbms.procedures()",
            # Combined with MATCH (needs RETURN to pass structure check)
            "MATCH (n) CALL dbms.listConfig() YIELD name RETURN name",
        ]

        for query in dangerous_queries:
            is_valid, error_message = validate_cypher_query(query)

            if is_valid:
                pytest.fail(
                    f"SECURITY VULNERABILITY: DBMS procedure not blocked!\n"
                    f"Query: {query}\n"
                    f"Expected: CALL dbms.* should be rejected.\n"
                    f"Impact: Attacker could access admin functions."
                )

            assert error_message, f"Error message should not be empty for: {query}"

    def test_cypher_injection_load_csv_blocked(self):
        """
        Test 3.4: LOAD CSV should be blocked.

        Attack: LOAD CSV FROM 'file:///etc/passwd' AS row RETURN row
        Impact: Read arbitrary files from server filesystem
        """
        from app.api.endpoints.graph import validate_cypher_query

        dangerous_queries = [
            # Local file access
            "LOAD CSV FROM 'file:///etc/passwd' AS row RETURN row",
            "LOAD CSV FROM 'file:///app/.env' AS row RETURN row",
            # Remote file access (SSRF)
            "LOAD CSV FROM 'http://internal-server/secrets' AS row RETURN row",
            # With headers
            "LOAD CSV WITH HEADERS FROM 'file:///etc/passwd' AS row RETURN row",
            # Case variations
            "load csv from 'file:///etc/passwd' as row return row",
        ]

        for query in dangerous_queries:
            is_valid, error_message = validate_cypher_query(query)

            if is_valid:
                pytest.fail(
                    f"SECURITY VULNERABILITY: LOAD CSV not blocked!\n"
                    f"Query: {query}\n"
                    f"Expected: LOAD CSV should be rejected.\n"
                    f"Impact: File access, SSRF attacks."
                )

            assert error_message, f"Error message should not be empty for: {query}"

    def test_cypher_injection_create_drop_blocked(self):
        """
        Additional test: CREATE/DROP/SET/MERGE operations should be blocked.

        These are write operations that should not be allowed via the query endpoint.
        """
        from app.api.endpoints.graph import validate_cypher_query

        dangerous_queries = [
            # Schema modifications
            "CREATE INDEX ON :User(email)",
            "DROP INDEX ON :User(email)",
            # Node creation (data pollution)
            "CREATE (n:Malware {payload: 'evil'}) RETURN n",
            "CREATE (n:Admin {name: 'hacker'}) RETURN n",
            # Merge can create
            "MERGE (n:Backdoor {id: 'persistent'}) RETURN n",
            # Set can modify
            "MATCH (n:User) SET n.role = 'admin' RETURN n",
            # Remove properties
            "MATCH (n:User) REMOVE n.permissions RETURN n",
        ]

        for query in dangerous_queries:
            is_valid, error_message = validate_cypher_query(query)

            if is_valid:
                pytest.fail(
                    f"SECURITY VULNERABILITY: Write operation not blocked!\n"
                    f"Query: {query}\n"
                    f"Expected: CREATE/DROP/SET/MERGE should be rejected.\n"
                    f"Impact: Data modification, privilege escalation."
                )

            assert error_message, f"Error message should not be empty for: {query}"

    def test_cypher_valid_queries_pass(self):
        """
        Verify that legitimate READ queries still work.
        """
        from app.api.endpoints.graph import validate_cypher_query

        valid_queries = [
            "MATCH (n) RETURN n",
            "MATCH (n:User) WHERE n.name = 'test' RETURN n",
            "MATCH (a)-[r]->(b) RETURN a, r, b LIMIT 10",
            "MATCH (n) RETURN n.name, n.email ORDER BY n.name",
            "OPTIONAL MATCH (n:Document) RETURN count(n)",
            "MATCH (n) WHERE n.status = $status RETURN n",
        ]

        for query in valid_queries:
            is_valid, error_message = validate_cypher_query(query)

            if not is_valid:
                pytest.fail(
                    f"Valid query incorrectly blocked!\n"
                    f"Query: {query}\n"
                    f"Error: {error_message}\n"
                    f"Expected: Legitimate READ queries should pass."
                )


# =============================================================================
# TEST CATEGORY 2: SQL INJECTION (4.2 - 4.3)
# =============================================================================

class TestSQLInjection:
    """
    Tests for SQL Injection vulnerabilities in the SQL Tool.

    Tests verify that the validate_sql_query function properly blocks
    injection attempts using sqlparse-based validation.
    """

    def test_sql_injection_statement_stacking_validation(self):
        """
        Test 4.2: Statement stacking should be detected by validation.

        Attack: SELECT * FROM users; DROP TABLE users;--
        Impact: Data deletion, schema destruction

        This test verifies that the validate_sql_query function blocks
        multi-statement queries (statement stacking attacks).
        """
        from app.tools.sql import validate_sql_query

        injection_queries = [
            # Classic statement stacking
            "SELECT * FROM users; DROP TABLE users;--",
            "SELECT * FROM users; DELETE FROM users;--",
            "SELECT * FROM users; UPDATE users SET role='admin';--",
            "SELECT * FROM users; INSERT INTO admins VALUES('hacker');--",
            # With newlines
            "SELECT * FROM users;\nDROP TABLE users;--",
            # With comments hiding the dangerous part
            "SELECT * FROM users; /* comment */ DROP TABLE users;",
        ]

        for query in injection_queries:
            is_valid, error_message = validate_sql_query(query)

            if is_valid:
                pytest.fail(
                    f"SECURITY VULNERABILITY: SQL statement stacking not blocked!\n"
                    f"Query: {query}\n"
                    f"Expected: Validation should reject multi-statement queries.\n"
                    f"Impact: Attacker could DROP tables, DELETE data, or escalate privileges."
                )

            # Verify the error message is informative
            assert error_message, f"Error message should not be empty for blocked query: {query}"

    def test_sql_injection_union_validation(self):
        """
        Test 4.3: UNION-based injection should be detected by validation.

        Attack: SELECT * FROM users UNION SELECT password FROM admin
        Impact: Extract sensitive data from other tables

        This test verifies that UNION queries are blocked.
        """
        from app.tools.sql import validate_sql_query

        injection_queries = [
            # Classic UNION injection
            "SELECT id, name FROM users UNION SELECT id, password FROM admin_users",
            "SELECT * FROM products UNION SELECT username, password, null FROM credentials",
            # UNION ALL (avoids DISTINCT)
            "SELECT name FROM users UNION ALL SELECT secret FROM secrets",
            # Information schema access
            "SELECT * FROM users UNION SELECT table_name, column_name FROM information_schema.columns",
            "SELECT 1 UNION SELECT table_name FROM information_schema.tables",
        ]

        for query in injection_queries:
            is_valid, error_message = validate_sql_query(query)

            if is_valid:
                pytest.fail(
                    f"SECURITY VULNERABILITY: SQL UNION injection not blocked!\n"
                    f"Query: {query}\n"
                    f"Expected: UNION queries should be blocked.\n"
                    f"Impact: Attacker could extract passwords, secrets, or schema info."
                )

            assert error_message, f"Error message should not be empty for blocked query: {query}"

    def test_sql_injection_comment_bypass_validation(self):
        """
        Additional test: Comment-based bypasses should be detected.

        Attack variations using SQL comments to hide malicious code.
        """
        from app.tools.sql import validate_sql_query

        injection_queries = [
            # Comment markers that could hide injected code
            ("SELECT * FROM users WHERE id = 1 OR 1=1--", "comment marker '--'"),
            ("SELECT * FROM users WHERE id = 1 OR 1=1#", "comment marker '#'"),
            ("SELECT * FROM users WHERE id = 1 OR 1=1/*", "comment marker '/*'"),
            # Always-true conditions (data exfiltration)
            ("SELECT * FROM users WHERE '1'='1'", "always-true condition '1'='1'"),
            ("SELECT * FROM users WHERE 1=1", "always-true condition 1=1"),
        ]

        for query, attack_type in injection_queries:
            is_valid, error_message = validate_sql_query(query)

            if is_valid:
                pytest.fail(
                    f"SECURITY VULNERABILITY: SQL validation doesn't detect {attack_type}!\n"
                    f"Query: {query}\n"
                    f"Expected: Suspicious patterns should be blocked.\n"
                    f"Impact: Data exfiltration, injection attacks."
                )

            assert error_message, f"Error message should not be empty for blocked query: {query}"

    def test_sql_valid_queries_pass(self):
        """
        Verify that legitimate SELECT queries still work.
        """
        from app.tools.sql import validate_sql_query

        valid_queries = [
            "SELECT * FROM users",
            "SELECT id, name FROM customers WHERE status = 'active'",
            "SELECT COUNT(*) FROM orders WHERE date > '2024-01-01'",
            "SELECT a.name, b.total FROM accounts a JOIN balances b ON a.id = b.account_id",
        ]

        for query in valid_queries:
            is_valid, error_message = validate_sql_query(query)

            if not is_valid:
                pytest.fail(
                    f"Valid query incorrectly blocked!\n"
                    f"Query: {query}\n"
                    f"Error: {error_message}\n"
                    f"Expected: Legitimate SELECT queries should pass validation."
                )


# =============================================================================
# TEST CATEGORY 3: PATH TRAVERSAL (2.5)
# =============================================================================

class TestPathTraversal:
    """
    Tests for Path Traversal vulnerabilities in document upload.

    The filename from user upload is used to construct storage paths.
    Without sanitization, an attacker could overwrite arbitrary files.

    SECURITY RISK: An attacker could:
    - Overwrite system files
    - Overwrite application config
    - Plant backdoors in executable directories
    """

    @pytest.mark.asyncio
    async def test_path_traversal_filename_blocked(self):
        """
        Test 2.5: Path traversal in filename should be blocked.

        Attack: Upload file with name '../../../etc/passwd' or '..\\..\\..\\windows\\system32\\config'
        Impact: File overwrite in arbitrary locations

        This test verifies that the sanitize_filename function properly blocks
        path traversal attempts and produces safe filenames.
        """
        from app.api.endpoints.ingestion import sanitize_filename

        malicious_filenames = [
            # Unix-style traversal
            "../../../etc/passwd",
            "../../../../etc/shadow",
            "../../../app/.env",
            # Multiple traversal patterns
            "....//....//etc/passwd",
            "..././..././etc/passwd",
            # URL encoded (should be decoded before use)
            "%2e%2e%2fetc/passwd",
            # Windows-style traversal
            "..\\..\\..\\windows\\system32\\config\\SAM",
            # Mixed style
            "..\\../etc/passwd",
            # Absolute paths (could bypass relative path handling)
            "/etc/passwd",
            # With valid extension to bypass type checks
            "../../../etc/cron.d/malicious.pdf",
        ]

        doc_id = "12345678-1234-5678-1234-567812345678"

        for filename in malicious_filenames:
            # Use the sanitize_filename function that should now exist
            safe_filename = sanitize_filename(filename)
            storage_path = f"documents/{doc_id}/{safe_filename}"

            # Check for path traversal patterns in the constructed path
            has_path_traversal = (
                '..' in storage_path or
                storage_path.count('/') > 3 or  # More slashes than expected
                '\\' in storage_path or
                storage_path.startswith('/') or
                ':' in storage_path  # Windows absolute path
            )

            # Check if the path escapes the intended directory
            import os
            try:
                base_path = f"/data/documents/{doc_id}"
                full_path = os.path.normpath(os.path.join(base_path, safe_filename))
                escapes_base = not full_path.startswith(base_path.rsplit('/', 1)[0])
            except Exception:
                escapes_base = True

            if has_path_traversal or escapes_base:
                pytest.fail(
                    f"SECURITY VULNERABILITY: Path traversal in storage path!\n"
                    f"Malicious filename: {filename}\n"
                    f"Sanitized filename: {safe_filename}\n"
                    f"Constructed storage path: {storage_path}\n"
                    f"Path escapes base directory: {escapes_base}\n"
                    f"Expected: Filename should be sanitized to remove '../', '..\\', etc."
                )

    def test_path_traversal_special_characters_blocked(self):
        """
        Test 2.6: Filenames with special characters should be sanitized.

        Attack: Use shell metacharacters or filesystem special chars
        Impact: Command injection via filename, filesystem corruption

        Tests that sanitize_filename removes dangerous characters.
        """
        from app.api.endpoints.ingestion import sanitize_filename

        dangerous_filenames = [
            # Shell metacharacters
            ("file$(whoami).pdf", "$"),
            ("file`id`.pdf", "`"),
            ("file;rm -rf /.pdf", ";"),
            ("file|cat /etc/passwd.pdf", "|"),
            # Newlines in filename (log injection, header injection)
            ("file\nname.pdf", "\n"),
            ("file\rname.pdf", "\r"),
        ]

        doc_id = "12345678-1234-5678-1234-567812345678"

        for filename, dangerous_char in dangerous_filenames:
            # Use the sanitize_filename function
            safe_filename = sanitize_filename(filename)
            storage_path = f"documents/{doc_id}/{safe_filename}"

            # Check for shell metacharacters
            dangerous_chars_in_path = ['$', '`', ';', '|', '&', '<', '>', '\n', '\r']

            for char in dangerous_chars_in_path:
                if char in storage_path:
                    pytest.fail(
                        f"SECURITY VULNERABILITY: Dangerous character in storage path!\n"
                        f"Original filename: {repr(filename)}\n"
                        f"Sanitized filename: {repr(safe_filename)}\n"
                        f"Constructed storage path: {repr(storage_path)}\n"
                        f"Dangerous character: {repr(char)}\n"
                        f"Expected: Special characters should be removed or replaced."
                    )


# =============================================================================
# HELPER: QUERY PATTERN DETECTION
# =============================================================================

class CypherQueryValidator:
    """
    Helper class to demonstrate what the validation SHOULD do.
    This is for documentation purposes - the actual implementation
    should be in the application code.
    """

    DANGEROUS_PATTERNS = [
        r'\bDELETE\b',
        r'\bDETACH\s+DELETE\b',
        r'\bDROP\b',
        r'\bCREATE\b',
        r'\bMERGE\b',
        r'\bSET\b',
        r'\bREMOVE\b',
        r'\bCALL\s+dbms\.',
        r'\bLOAD\s+CSV\b',
        r'\bFOREACH\b',
    ]

    @classmethod
    def is_safe_query(cls, cypher: str) -> tuple[bool, str]:
        """
        Check if a Cypher query is safe to execute.

        Returns:
            Tuple of (is_safe, reason)
        """
        cypher_upper = cypher.upper()

        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, cypher_upper, re.IGNORECASE):
                return False, f"Query contains forbidden pattern: {pattern}"

        return True, "Query appears safe"


class SQLQueryValidator:
    """
    Helper class to demonstrate what SQL validation SHOULD do.
    """

    @classmethod
    def is_safe_query(cls, query: str) -> tuple[bool, str]:
        """
        Check if a SQL query is safe to execute.

        Returns:
            Tuple of (is_safe, reason)
        """
        query_upper = query.upper().strip()

        # Must start with SELECT
        if not query_upper.startswith('SELECT'):
            return False, "Only SELECT queries allowed"

        # No multiple statements
        # Split by semicolon but ignore semicolons in strings
        if ';' in query:
            # Simple check - could be more sophisticated
            return False, "Multiple statements not allowed"

        # No UNION (or whitelist specific tables)
        if 'UNION' in query_upper:
            return False, "UNION queries not allowed"

        # No subqueries to sensitive tables
        if 'INFORMATION_SCHEMA' in query_upper:
            return False, "Access to information_schema not allowed"

        # No comments
        if '--' in query or '/*' in query or '#' in query:
            return False, "SQL comments not allowed"

        return True, "Query appears safe"


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
