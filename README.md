# Adizon Knowledge Core

A Sovereign AI RAG (Retrieval-Augmented Generation) System with Knowledge Graph integration.

## Architecture

- **Backend**: FastAPI with async endpoints
- **Vector Store**: PostgreSQL with pgvector extension
- **Knowledge Graph**: Neo4j for entity relationships
- **File Storage**: MinIO (S3-compatible)
- **Frontend**: React + TypeScript + Tailwind CSS

## Features

- Document upload with automatic processing
- Hybrid retrieval: Vector search + Knowledge Graph
- Entity extraction with review workflow (PENDING/APPROVED states)
- German language optimized (Jina embeddings)
- Real-time chat interface with source attribution

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

| Variable | Description |
|----------|-------------|
| `POSTGRES_*` | PostgreSQL connection settings |
| `NEO4J_*` | Neo4j connection settings |
| `MINIO_*` | MinIO storage settings |
| `EMBEDDING_API_URL` | OpenAI-compatible embedding API URL |
| `EMBEDDING_API_KEY` | API key for embeddings |
| `EMBEDDING_MODEL` | Model name for embeddings |
| `LLM_MODEL_NAME` | Model name for graph extraction |
| `CORS_ORIGINS` | Allowed frontend origins |

## API Endpoints

### Chat
- `POST /api/v1/chat` - Send chat message with RAG retrieval

### Documents
- `POST /api/v1/upload` - Upload document for processing
- `GET /api/v1/documents` - List all documents
- `GET /api/v1/documents/{id}` - Get document details
- `DELETE /api/v1/documents/{id}` - Delete document and all associated data
- `POST /api/v1/documents/{id}/reprocess` - Reprocess document

### Knowledge Graph
- `GET /api/v1/graph/pending` - Get pending nodes for review
- `POST /api/v1/graph/approve` - Approve selected nodes
- `POST /api/v1/graph/reject` - Reject (delete) selected nodes
- `POST /api/v1/graph/query` - Execute Cypher query

### System
- `GET /api/v1/knowledge/summary` - Get knowledge base statistics

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
