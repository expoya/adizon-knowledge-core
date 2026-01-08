# Adizon Knowledge Core

**Enterprise-Intelligence-System** powered by Agentic RAG Architecture

A Sovereign AI RAG (Retrieval-Augmented Generation) System with Knowledge Graph integration and external database connectivity.

## 🚀 Version 2.1 - Agentic RAG with CRM

> Intelligentes Multi-Source RAG mit autonomem Routing, SQL-Integration und CRM-Plugin-System

## Architecture

- **Backend**: FastAPI with async endpoints + LangGraph workflow
- **Agent System**: LangGraph-based autonomous routing
- **Vector Store**: PostgreSQL with pgvector extension
- **Knowledge Graph**: Neo4j for entity relationships
- **SQL Integration**: External database connectivity with query generation
- **File Storage**: MinIO (S3-compatible)
- **Frontend**: React + TypeScript + Tailwind CSS

## ✨ Key Features

### Core RAG Features
- 📄 Document upload with automatic processing
- 🔍 Hybrid retrieval: Vector search + Knowledge Graph
- 🧠 Entity extraction with review workflow (PENDING/APPROVED states)
- 🇩🇪 German language optimized (Jina embeddings)
- 💬 Real-time chat interface with source attribution

### 🆕 Agentic Features (v2.0+)
- 🤖 **LangGraph-based Agent**: Autonomous decision-making workflow
- 🔀 **Intent Routing**: LLM-powered query classification (SQL vs Knowledge vs CRM)
- 🗄️ **SQL Query Generation**: Natural language to SQL conversion
- 📞 **CRM Integration**: Modular plugin system for CRM connectivity (v2.1)
- 🎯 **Entity Detection**: Automatic recognition of CRM entities in queries (v2.1)
- 💼 **Live Facts**: Real-time CRM data (Deals, Meetings, Objections) (v2.1)
- 🔗 **Multi-Source Intelligence**: Combines documents, graphs, databases, and CRM
- 📊 **Schema Discovery**: Automatic database schema inspection
- 🌊 **Smart Streaming**: Token-by-token responses without internal leaks
- 🛡️ **Enterprise Security**: Query validation, connection pooling, error handling

## Prerequisites

- Python 3.12+
- Node.js 18+
- Docker & Docker Compose (for local services)

## Local Development Setup

### 1. Start Infrastructure Services

```bash
docker-compose up -d
```

This starts:
- PostgreSQL with pgvector (port 5433)
- Neo4j (ports 7474, 7687)
- MinIO (ports 9000, 9001)

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r ../requirements.txt

# Copy environment variables
cp ../.env.example .env
# Edit .env with your API keys

# Run backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend runs on http://localhost:5173

## Environment Variables

Copy `.env.example` to `.env` and configure:

### Internal Knowledge Base
| Variable | Description |
|----------|-------------|
| `POSTGRES_*` | PostgreSQL connection settings (internal vector store) |
| `NEO4J_*` | Neo4j connection settings (knowledge graph) |
| `MINIO_*` | MinIO storage settings (document storage) |

### AI Services
| Variable | Description |
|----------|-------------|
| `EMBEDDING_API_URL` | OpenAI-compatible embedding API URL |
| `EMBEDDING_API_KEY` | API key for embeddings |
| `EMBEDDING_MODEL` | Model name for embeddings (e.g., jina-embeddings-v2-base-de) |
| `LLM_MODEL_NAME` | Model name for LLM (e.g., adizon-ministral) |

### External Databases (Agentic RAG)
| Variable | Description |
|----------|-------------|
| `ERP_DATABASE_URL` | 🆕 External database connection (e.g., PostgreSQL, MySQL) |

### CRM Integration (v2.1)
| Variable | Description |
|----------|-------------|
| `ACTIVE_CRM_PROVIDER` | 🆕 Active CRM provider: 'zoho', 'salesforce', or 'none' (default: zoho) |
| `ZOHO_CLIENT_ID` | 🆕 Zoho OAuth2 Client ID |
| `ZOHO_CLIENT_SECRET` | 🆕 Zoho OAuth2 Client Secret |
| `ZOHO_REFRESH_TOKEN` | 🆕 Zoho OAuth2 Refresh Token (long-lived) |
| `ZOHO_API_BASE_URL` | 🆕 Zoho API base URL (region-specific, default: .eu) |

### Other
| Variable | Description |
|----------|-------------|
| `CORS_ORIGINS` | Allowed frontend origins |
| `TROOPER_URL` | Trooper worker endpoint (if using external worker) |

## 📚 Documentation

- **[Agentic RAG Guide](docs/AGENTIC_RAG.md)** - Comprehensive guide to v2.0 features
- **[Architecture](docs/ARCHITECTURE.md)** - System architecture and data flows
- **[API Reference](docs/API.md)** - Complete API documentation
- **[Deployment](docs/DEPLOYMENT.md)** - Deployment instructions

## API Endpoints

### Chat (Agentic RAG)
- `POST /api/v1/chat` - 🆕 Agentic chat with multi-source retrieval
- `POST /api/v1/chat/stream` - 🆕 Streaming chat with smart token filtering
- `GET /api/v1/knowledge/summary` - Get knowledge base statistics

### Documents & Ingestion
- `POST /api/v1/upload` - Upload document for processing
- `GET /api/v1/documents` - List all documents
- `GET /api/v1/documents/{id}` - Get document details
- `DELETE /api/v1/documents/{id}` - Delete document and all associated data
- `POST /api/v1/documents/{id}/reprocess` - Reprocess document
- `POST /api/v1/ingestion/crm-sync` - 🆕 Sync CRM entities to graph (v2.1)

### Knowledge Graph
- `GET /api/v1/graph/pending` - Get pending nodes for review
- `POST /api/v1/graph/approve` - Approve selected nodes
- `POST /api/v1/graph/reject` - Reject (delete) selected nodes
- `POST /api/v1/graph/query` - Execute Cypher query

## Deployment

### Railway

The project includes `railway.toml` for Railway deployment.

1. Create a new Railway project
2. Add PostgreSQL, Neo4j (via plugin or template), and configure MinIO
3. Connect your GitHub repository
4. Set environment variables in Railway dashboard
5. Deploy

## Project Structure

```
adizon-knowledge-core/
├── backend/
│   └── app/
│       ├── api/endpoints/     # API routes
│       ├── core/              # Configuration
│       ├── db/                # Database session
│       ├── graph/             # Ingestion workflow
│       ├── models/            # SQLAlchemy models
│       └── services/          # Business logic
├── frontend/
│   └── src/
│       ├── api/               # API client
│       ├── components/        # React components
│       └── pages/             # Page components
├── docker-compose.yml         # Local services
├── requirements.txt           # Python dependencies
└── railway.toml              # Railway config
```

## License

Proprietary - Adizon GmbH
