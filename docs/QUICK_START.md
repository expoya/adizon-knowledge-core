# Quick Start Guide - Adizon Enterprise-Intelligence-System

Get up and running with Agentic RAG in 10 minutes!

---

## 🚀 Prerequisites

- Python 3.12+
- Docker & Docker Compose
- Node.js 18+ (for frontend)
- Git

---

## Step 1: Clone & Setup Infrastructure

```bash
# Clone the repository
git clone <repository-url>
cd adizon-knowledge-core

# Start infrastructure services
docker-compose up -d
```

This starts:
- ✅ PostgreSQL with pgvector (port 5433)
- ✅ Neo4j (ports 7474, 7687)
- ✅ MinIO (ports 9000, 9001)

Wait ~30 seconds for services to initialize.

---

## Step 2: Configure Environment

```bash
# Copy environment template
cp backend/.env.example backend/.env

# Edit with your favorite editor
nano backend/.env
```

### Minimum Required Configuration

```bash
# === Internal Knowledge Base ===
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_DB=knowledge_core
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# === AI Services (REQUIRED) ===
EMBEDDING_API_URL=http://your-trooper-server:8001/v1
EMBEDDING_API_KEY=your-api-key
EMBEDDING_MODEL=jina/jina-embeddings-v2-base-de
LLM_MODEL_NAME=adizon-ministral

# === External Databases (Optional for Agentic RAG) ===
ERP_DATABASE_URL=postgresql://user:pass@host:5432/erp_db

# === Frontend ===
CORS_ORIGINS=http://localhost:5173
```

> **Note:** `EMBEDDING_API_URL` and `EMBEDDING_API_KEY` are required!

---

## Step 3: Configure External Sources (Optional)

If you want to use SQL integration:

```bash
# Edit external sources configuration
nano backend/app/config/external_sources.yaml
```

Example configuration:

```yaml
sources:
  - id: "erp_postgres"
    type: "sql"
    description: "ERP system with invoices, customers, and sales data"
    connection_env: "ERP_DATABASE_URL"
    tables:
      - name: "invoices"
        description: "Invoice records with amounts, dates, and customer IDs"
      - name: "customers"
        description: "Customer master data with names and regions"
```

---

## Step 4: Start Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r ../requirements.txt

# Run database migrations (if any)
# alembic upgrade head

# Start backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend runs at: http://localhost:8000

Check API docs: http://localhost:8000/docs

---

## Step 5: Start Frontend (Optional)

```bash
# In a new terminal
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend runs at: http://localhost:5173

---

## ✅ Verify Installation

### 1. Check Backend Health

```bash
curl http://localhost:8000/api/v1/knowledge/summary
```

Expected response:
```json
{
  "status": "ok",
  "message": "Agentic RAG workflow is active",
  "features": [...]
}
```

### 2. Test Chat Endpoint

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello, what can you do?",
    "history": []
  }'
```

### 3. Check Infrastructure

```bash
# PostgreSQL
docker exec -it adizon-postgres psql -U postgres -d knowledge_core -c "SELECT 1;"

# Neo4j (web interface)
open http://localhost:7474

# MinIO (web interface)
open http://localhost:9001
```

---

## 📚 First Steps

### Upload a Document

1. Open frontend: http://localhost:5173
2. Navigate to "Upload" page
3. Select a PDF or DOCX file
4. Click "Upload"
5. Wait for processing (status changes to "INDEXED")

### Chat with Your Knowledge

1. Navigate to "Chat" page
2. Ask a question about your document
3. See the hybrid RAG in action!

### Example Knowledge Questions

```
"Was steht in Dokument XYZ über Sicherheit?"
"Erkläre mir den Prozess für..."
"Welche Personen werden erwähnt?"
```

### Example SQL Questions (if configured)

```
"Welche Rechnungen haben wir im Dezember?"
"Zeige mir alle Kunden aus Deutschland"
"Was ist der Gesamtumsatz im letzten Quartal?"
```

---

## 🎨 Architecture Quick View

```
User Question
    ↓
Chat API
    ↓
LangGraph Router
    ↓
   / \
  /   \
SQL    Knowledge
Node    Node
 |       |
 |       ├─ Vector Search (pgvector)
 |       └─ Graph Search (Neo4j)
 |
 └─ External DB Query
    ↓
Generator Node
    ↓
Natural Language Answer
```

---

## 🔧 Troubleshooting

### Backend won't start

**Error:** "No module named 'app'"

**Solution:** Make sure you're in the `backend/` directory and virtual environment is activated.

---

### "Connection refused" errors

**Error:** Cannot connect to PostgreSQL/Neo4j/MinIO

**Solution:** 
```bash
# Check if containers are running
docker-compose ps

# Restart if needed
docker-compose restart
```

---

### SQL queries not working

**Error:** "Source 'erp_postgres' not found"

**Solution:**
1. Check `external_sources.yaml` configuration
2. Verify `ERP_DATABASE_URL` environment variable is set
3. Test connection manually:
   ```bash
   psql $ERP_DATABASE_URL -c "SELECT 1;"
   ```

---

### LLM errors

**Error:** "LLM call failed"

**Solution:**
1. Verify `EMBEDDING_API_URL` is correct and reachable
2. Check `EMBEDDING_API_KEY` is valid
3. Test endpoint manually:
   ```bash
   curl $EMBEDDING_API_URL/models \
     -H "Authorization: Bearer $EMBEDDING_API_KEY"
   ```

---

## 📖 Next Steps

1. **Read the Architecture Guide**
   - [AGENTIC_RAG.md](./AGENTIC_RAG.md) - Comprehensive documentation
   - [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture

2. **Explore the Knowledge Graph**
   - Navigate to "Garden" page in frontend
   - Approve/reject extracted entities
   - See relationship visualization

3. **Configure More External Sources**
   - Add more databases to `external_sources.yaml`
   - Set environment variables
   - Restart backend

4. **Customize the Ontology**
   - Edit `backend/app/config/ontology_voltage.yaml`
   - Define your domain-specific entities
   - Reprocess documents

---

## 🎓 Learning Resources

### Understanding the System

1. Start with: [README.md](../README.md)
2. Deep dive: [AGENTIC_RAG.md](./AGENTIC_RAG.md)
3. Architecture: [ARCHITECTURE.md](./ARCHITECTURE.md)

### API Documentation

- Interactive docs: http://localhost:8000/docs
- OpenAPI spec: http://localhost:8000/openapi.json

### Code Examples

Check the `tests/` directory for usage examples:
```bash
cd backend
pytest tests/ -v
```

---

## 💡 Tips & Tricks

### Faster Development

```bash
# Use auto-reload for backend
uvicorn app.main:app --reload

# Use hot-reload for frontend  
npm run dev
```

### Debugging

```bash
# Enable debug logging
export APP_DEBUG=true
export LOG_LEVEL=DEBUG

# Check logs
docker-compose logs -f postgres
docker-compose logs -f neo4j
```

### Performance

- Vector search is cached in pgvector
- SQL connections are pooled
- LLM responses can be streamed for better UX

---

## 🆘 Get Help

- **Documentation**: See `docs/` folder
- **Issues**: Check known limitations in [AGENTIC_RAG.md](./AGENTIC_RAG.md#troubleshooting)
- **Examples**: Review test files in `backend/tests/`

---

## ✅ Checklist

Before going to production:

- [ ] All environment variables configured
- [ ] External databases accessible
- [ ] LLM API endpoint working
- [ ] Document upload tested
- [ ] Chat functionality verified
- [ ] SQL queries tested (if using)
- [ ] Frontend connected to backend
- [ ] Neo4j graph populated
- [ ] Backups configured
- [ ] Monitoring setup

---

**Happy Building! 🚀**

Need more details? See the [Complete Documentation](./AGENTIC_RAG.md)

