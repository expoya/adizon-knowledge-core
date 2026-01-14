# Adizon Knowledge Core - Backend

FastAPI-based backend for the Adizon Knowledge Management System featuring:
- LangGraph-based agentic RAG workflow
- Neo4j knowledge graph integration
- PostgreSQL with pgvector for semantic search
- MinIO for document storage
- CRM synchronization (Zoho)

## Quick Start

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Set environment variables (copy from .env.example)
cp .env.example .env
# Edit .env with your configuration

# Run development server
uvicorn app.main:app --reload
```

## Project Structure

```
backend/
├── app/
│   ├── api/endpoints/     # FastAPI route handlers
│   ├── core/              # Configuration, settings
│   ├── db/                # Database session management
│   ├── graph/             # LangGraph workflows
│   ├── models/            # SQLAlchemy models
│   ├── services/          # Business logic services
│   │   ├── crm_sync/      # CRM synchronization
│   │   └── graph_operations/
│   └── tools/             # LangChain tools (SQL, Knowledge)
├── tests/                 # Test suites
├── docs/                  # Architecture documentation
└── requirements.txt
```

## Testing

The project includes comprehensive test suites for security and stability.

### Running All Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --cov=app --cov-report=html
```

### Security Tests

Tests for injection attacks and path traversal vulnerabilities.

```bash
# Run security tests only
pytest tests/test_security_critical.py -v
```

**Test Categories:**
- **Cypher Injection** (5 tests): DELETE, CALL dbms.*, LOAD CSV, CREATE/DROP/SET/MERGE
- **SQL Injection** (4 tests): Statement stacking, UNION, comments, always-true conditions
- **Path Traversal** (2 tests): Directory traversal, shell metacharacters

### Unhappy Path Tests

Tests for graceful error handling when receiving malformed or unexpected data.

```bash
# Run unhappy path tests only
pytest tests/test_unhappy_paths.py -v
```

**Test Categories:**
- **Null Safety** (6 tests): None inputs, empty strings
- **Empty States** (5 tests): Empty lists, no results
- **Type Errors** (5 tests): Wrong types from external systems
- **Boundary Conditions** (4 tests): Long strings, special characters
- **Service Failures** (3 tests): Missing configuration
- **JSON Parsing** (3 tests): Malformed LLM responses
- **Pydantic Validation** (4 tests): Invalid API requests
- **Relationship Processing** (2 tests): CRM sync edge cases
- **List Handling** (2 tests): None values in lists

### Test Philosophy

1. **Red Phase**: Write tests that FAIL when vulnerability/bug exists
2. **Green Phase**: Implement fix, tests PASS
3. **No Tautologies**: Test logic, not just code structure
4. **Edge Cases First**: Boundary values (0, -1, MaxInt, None)
5. **Unhappy Path Focus**: At least as many failure tests as success tests

## Security

See [docs/ARCHITECTURE_DECISIONS.md](docs/ARCHITECTURE_DECISIONS.md) for detailed security decisions.

### Key Security Measures

1. **SQL Injection Prevention**
   - `sqlparse`-based query validation
   - READ-ONLY database user (defense in depth)

2. **Cypher Injection Prevention**
   - Pattern blacklist + structure whitelist
   - Parameterized queries for user input

3. **Path Traversal Prevention**
   - `os.path.basename()` + character whitelist
   - Shell metacharacter sanitization

## API Documentation

When running the server, API docs are available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Configuration

Key environment variables (see `.env.example`):

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Storage
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# LLM
OPENAI_API_KEY=sk-...

# CRM (optional)
ACTIVE_CRM_PROVIDER=zoho
ZOHO_CLIENT_ID=...
ZOHO_CLIENT_SECRET=...
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and changes.
