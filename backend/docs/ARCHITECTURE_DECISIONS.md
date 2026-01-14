# Architecture Decision Records (ADR)

This document records significant architectural and security decisions made in the adizon-knowledge-core backend.

---

## ADR-001: SQL Query Validation with sqlparse

**Status:** Accepted
**Date:** 2025-01-13
**Context:** The SQL Tool allows LangGraph agents to query external databases (ERP, IoT). User queries could contain SQL injection attacks.

### Decision

Use the `sqlparse` library for SQL query validation instead of regex-based pattern matching.

### Rationale

1. **Proper Parsing**: `sqlparse` builds an AST, correctly handling edge cases like:
   - Semicolons inside string literals (`SELECT 'a;b'`)
   - Comments with misleading content
   - Complex nested queries

2. **Statement Type Detection**: `statement.get_type()` reliably identifies SELECT vs INSERT/UPDATE/DELETE

3. **Statement Stacking Prevention**: Parsing reveals multiple statements that regex might miss

### Implementation

```python
# app/tools/sql.py
def validate_sql_query(query: str) -> Tuple[bool, str]:
    statements = sqlparse.parse(query)
    non_empty = [s for s in statements if s.get_type() != 'UNKNOWN' or str(s).strip()]

    if len(non_empty) > 1:
        return False, "Multiple SQL statements detected (statement stacking)"

    if non_empty[0].get_type() != 'SELECT':
        return False, f"Statement type '{stmt_type}' is not allowed"
```

### Defense in Depth

Application-level validation is **not sufficient alone**. The database user MUST have READ-ONLY permissions:

```sql
CREATE USER sql_tool_reader WITH PASSWORD 'xxx';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO sql_tool_reader;
```

---

## ADR-002: Cypher Query Validation with Pattern Blacklist + Structure Whitelist

**Status:** Accepted
**Date:** 2025-01-13
**Context:** The Graph Query endpoint accepts Cypher queries for admin/review purposes. Malicious queries could delete data or access admin functions.

### Decision

Implement a hybrid validation approach:
1. **Blacklist**: Block dangerous keywords (DELETE, CREATE, CALL dbms.*, LOAD CSV)
2. **Whitelist**: Require queries to start with read operations and contain RETURN

### Rationale

1. **Neo4j lacks a read-only query mode** that can be enforced at driver level
2. **Regex patterns with word boundaries** (`\bDELETE\b`) prevent bypass via concatenation
3. **Case-insensitive matching** prevents bypass via `DeLeTe`
4. **Structure validation** ensures queries are read-only (must have RETURN)

### Implementation

```python
# app/api/endpoints/graph.py
DANGEROUS_CYPHER_PATTERNS = [
    (r'\bDELETE\b', "DELETE operations are not allowed"),
    (r'\bCALL\s+dbms\.', "CALL dbms.* procedures are not allowed"),
    (r'\bLOAD\s+CSV\b', "LOAD CSV is not allowed (file access)"),
    # ...
]

valid_starts = [r'^\s*MATCH\b', r'^\s*OPTIONAL\s+MATCH\b', ...]
```

### Parameterized Queries

For user-provided values (node IDs, search terms), ALWAYS use Neo4j parameters:

```python
# GOOD
query = "MATCH (n) WHERE n.name = $name RETURN n"
parameters = {"name": user_input}

# BAD - NEVER DO THIS
query = f"MATCH (n) WHERE n.name = '{user_input}' RETURN n"
```

---

## ADR-003: Filename Sanitization with os.path.basename + Whitelist

**Status:** Accepted
**Date:** 2025-01-13
**Context:** Document upload accepts user-provided filenames. Malicious filenames could enable path traversal or command injection.

### Decision

Use `os.path.basename()` combined with character whitelist sanitization.

### Rationale

1. **os.path.basename()**: Strips directory components, handles both Unix and Windows paths
2. **Whitelist approach**: Only allow `[a-zA-Z0-9._-]`, replace everything else
3. **Multiple layers**: Even after basename, remove remaining `..`, `/`, `\`

### Implementation

```python
# app/api/endpoints/ingestion.py
def sanitize_filename(filename: str | None) -> str:
    if not filename:
        return "unnamed_document"

    # Strip directories
    safe_name = os.path.basename(filename)

    # Remove traversal attempts
    safe_name = safe_name.replace('..', '').replace('/', '').replace('\\', '')

    # Whitelist characters
    sanitized = []
    for char in safe_name:
        if re.match(r'[a-zA-Z0-9._-]', char):
            sanitized.append(char)
        else:
            sanitized.append('_')

    return ''.join(sanitized) or "document"
```

### Why Not Just basename()?

```python
# Attack: filename = "....//....//etc/passwd"
# os.path.basename() returns: "passwd"  # Looks safe but...

# Attack: filename = "file$(whoami).pdf"
# os.path.basename() returns: "file$(whoami).pdf"  # Shell injection!
```

The whitelist ensures even after basename, no dangerous characters remain.

---

## ADR-004: Defensive Coding in CRM Sync (Null-Safety)

**Status:** Accepted
**Date:** 2025-01-13
**Context:** CRM providers (Zoho) return data with unpredictable structure. Missing fields or None values could crash the sync.

### Decision

Implement defensive null-handling at data boundaries:
1. Early returns for None inputs
2. Filter None values before processing lists
3. Use `.get()` with defaults for dict access

### Rationale

1. **External Data is Untrusted**: CRM APIs may return null for any field
2. **Fail Gracefully**: Skip invalid records, don't crash entire sync
3. **Log Warnings**: Make issues visible without stopping processing

### Implementation

```python
# app/services/crm_sync/property_sanitizer.py
def sanitize(self, props: Dict[str, Any] | None) -> Dict[str, Any]:
    if not props:
        return {}  # Early return for None
    # ...

def _handle_list_field(self, key: str, value: list) -> Any:
    if not value:
        return None

    # Filter None before checking type
    non_none = [v for v in value if v is not None]
    if not non_none:
        return None

    if isinstance(non_none[0], dict):
        return json.dumps(non_none)
    return non_none
```

### Anti-Pattern Avoided

```python
# BAD: Silent failure hides bugs
try:
    result = process(data)
except:
    pass  # Swallows all errors

# GOOD: Explicit handling with logging
if not data:
    logger.warning("Received None, skipping")
    return default_value
```

---

## ADR-005: Pydantic Validation at API Boundaries

**Status:** Accepted
**Date:** 2025-01-13
**Context:** Invalid API requests should be rejected early with clear error messages.

### Decision

Use Pydantic Field constraints for input validation:
- `min_length` for required strings
- `Optional[]` for nullable fields
- `List[str]` with type enforcement

### Implementation

```python
# app/api/endpoints/chat.py
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Cannot be empty")
    history: Optional[List[ChatMessage]] = None
```

### Benefits

1. **422 Validation Error**: Clear error response with field details
2. **OpenAPI Documentation**: Constraints appear in generated API docs
3. **Type Safety**: Invalid types rejected before handler execution

---

## ADR-006: File Extension Blacklist for Upload Security

**Status:** Accepted
**Date:** 2025-01-13
**Context:** Document upload accepts user-provided files. Even with filename sanitization, executable files could be uploaded and stored.

### Decision

Implement file extension blacklist to reject dangerous file types at upload time.

### Rationale

1. **Defense in Depth**: Even if executables aren't run, storing them is a risk
2. **Early Rejection**: Reject at upload, not during processing
3. **Clear Error Messages**: Users understand why upload failed

### Implementation

```python
# app/api/endpoints/ingestion.py
DANGEROUS_EXTENSIONS = {
    'exe', 'dll', 'so', 'dylib',  # Executables
    'sh', 'bash', 'bat', 'cmd', 'ps1',  # Scripts
    'pyc', 'pyo', 'class', 'jar',  # Compiled code
    'bin', 'com', 'msi', 'app',  # Binary/system
}

def validate_file_extension(filename: str) -> tuple[bool, str]:
    ext = filename.rsplit('.', 1)[-1].lower()
    if ext in DANGEROUS_EXTENSIONS:
        return False, f"File extension '.{ext}' is not allowed"
    return True, ""
```

---

## ADR-007: Prototype Pollution Prevention in Property Sanitizer

**Status:** Accepted
**Date:** 2025-01-13
**Context:** CRM data is processed and stored. Malicious keys like `__proto__` could enable prototype pollution attacks.

### Decision

Block dangerous JavaScript/JSON keys at the property sanitization layer.

### Rationale

1. **Cross-Language Attack**: Even in Python, JSON with `__proto__` can be dangerous when consumed by JavaScript frontends
2. **Defense in Depth**: Block at data ingestion, not just at rendering
3. **Logging**: Log blocked keys for security monitoring

### Implementation

```python
# app/services/crm_sync/property_sanitizer.py
DANGEROUS_KEYS = {
    '__proto__',
    'constructor',
    'prototype',
    '__defineGetter__',
    '__defineSetter__',
}

def sanitize(self, props: Dict[str, Any] | None) -> Dict[str, Any]:
    for key, value in props.items():
        if key in DANGEROUS_KEYS:
            logger.warning(f"Blocked dangerous key: '{key}'")
            continue
        # ... process safely
```

---

## Testing Strategy

### Security Tests (test_security_critical.py)

- **Red Phase**: Write tests that FAIL when vulnerability exists
- **Green Phase**: Implement fix, tests PASS
- **Regression**: Tests prevent future reintroduction of vulnerability

### Unhappy Path Tests (test_unhappy_paths.py)

- **Null Safety**: Functions handle None without crashing
- **Empty States**: Empty lists return structured responses
- **Type Errors**: Wrong types from external sources handled gracefully
- **Boundaries**: Edge cases (very long strings, special characters)

### Business Logic Tests (test_business_logic.py)

- **Upload Rules**: Extension blacklist, corrupt files, deduplication
- **Content Security**: XSS patterns, prototype pollution prevention
- **Workflow Resilience**: Partial success when services fail
- **Edge Cases**: Unicode filenames, deeply nested JSON, large files

### Running Tests

```bash
# All tests (117 total)
PYTHONPATH=. pytest tests/ -v

# Security tests only (11 tests)
PYTHONPATH=. pytest tests/test_security_critical.py -v

# Unhappy path tests only (34 tests)
PYTHONPATH=. pytest tests/test_unhappy_paths.py -v

# Business logic tests only (23 tests)
PYTHONPATH=. pytest tests/test_business_logic.py -v
```
