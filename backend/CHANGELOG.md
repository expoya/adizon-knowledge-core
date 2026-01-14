# Changelog

All notable changes to the adizon-knowledge-core backend are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

#### Security Hardening (Phase 1)

- **SQL Injection Prevention** (`app/tools/sql.py`)
  - Added `validate_sql_query()` using `sqlparse` library for proper SQL parsing
  - Blocks statement stacking attacks (`SELECT ...; DROP TABLE ...`)
  - Blocks UNION-based data exfiltration
  - Blocks information_schema access
  - Blocks SQL comments (`--`, `/*`, `#`) commonly used in injection
  - Blocks always-true conditions (`1=1`, `'1'='1'`)
  - Blocks time-based blind injection functions (`SLEEP`, `PG_SLEEP`, etc.)

- **Cypher Injection Prevention** (`app/api/endpoints/graph.py`)
  - Added `validate_cypher_query()` with pattern blacklist + structure whitelist
  - Blocks data modification operations (DELETE, CREATE, MERGE, SET, REMOVE)
  - Blocks schema operations (DROP, CREATE INDEX/CONSTRAINT)
  - Blocks admin procedures (CALL dbms.*, CALL db.*, CALL apoc.*)
  - Blocks file access (LOAD CSV) preventing SSRF/LFI attacks
  - Requires queries to start with MATCH/OPTIONAL MATCH/WITH/RETURN/UNWIND
  - Requires queries to contain RETURN clause (read-only enforcement)

- **Path Traversal Prevention** (`app/api/endpoints/ingestion.py`)
  - Added `sanitize_filename()` function with whitelist approach
  - Uses `os.path.basename()` to strip directory components
  - Only allows alphanumeric characters, dots, underscores, hyphens
  - Replaces shell metacharacters (`$`, `` ` ``, `;`, `|`, etc.) with underscores
  - Enforces maximum filename length (255 chars)
  - Provides safe fallback for invalid filenames

- **File Extension Validation** (`app/api/endpoints/ingestion.py`)
  - Added `validate_file_extension()` function with blacklist approach
  - Blocks dangerous extensions: .exe, .dll, .sh, .bat, .cmd, .ps1, .jar, .pyc, etc.
  - Returns clear error message for rejected files

- **Prototype Pollution Prevention** (`app/services/crm_sync/property_sanitizer.py`)
  - Added `DANGEROUS_KEYS` blacklist: __proto__, constructor, prototype, etc.
  - Keys are filtered at top level and in nested JSON serialization
  - Logs warning when dangerous keys are blocked

#### Stability & Unhappy Path Handling (Phase 2)

- **Input Validation** (`app/api/endpoints/chat.py`)
  - Added `min_length=1` constraint to ChatRequest.message field
  - Empty messages now return 422 Validation Error instead of processing

- **Null Safety** (`app/services/crm_sync/property_sanitizer.py`)
  - `sanitize()` now handles `None` input gracefully (returns empty dict)
  - `_handle_list_field()` filters out `None` values before type checking
  - Fixes bug where `[None, {"id": "123"}]` was incorrectly treated as primitive list

#### Test Suites

- **Security Tests** (`tests/test_security_critical.py`)
  - 11 tests covering Cypher injection, SQL injection, path traversal
  - Tests verify both blocking of attacks AND passing of legitimate queries

- **Unhappy Path Tests** (`tests/test_unhappy_paths.py`)
  - 34 tests covering null safety, empty states, type errors, boundaries
  - Tests for JSON parsing robustness, Pydantic validation, relationship processing

- **Business Logic Tests** (`tests/test_business_logic.py`)
  - 23 tests covering upload rules, content security, workflow resilience
  - Extension blacklist validation (blocks .exe, .sh, .bat, .dll, etc.)
  - Prototype pollution prevention (__proto__, constructor keys blocked)
  - Partial success handling when services fail
  - Content deduplication via SHA256 hash

### Changed

- **Pydantic v2 Migration** (`app/api/endpoints/ingestion.py`)
  - Replaced deprecated `class Config` with `model_config = ConfigDict(...)`
  - Eliminates PydanticDeprecatedSince20 warning

### Dependencies

- Added `sqlparse` for SQL query parsing and validation

## [0.1.0] - Initial Release

- LangGraph-based agentic RAG workflow
- Neo4j knowledge graph integration
- PostgreSQL with pgvector for semantic search
- MinIO for document storage
- CRM synchronization (Zoho)
- FastAPI REST API
