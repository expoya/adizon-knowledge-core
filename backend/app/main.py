"""
Adizon Knowledge Core - FastAPI Application Entry Point

A Sovereign AI Knowledge Platform for document ingestion and hybrid GraphRAG search.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.endpoints import chat, graph, ingestion, health, debug, sync_status
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import async_engine
from app.services.storage import get_minio_service

settings = get_settings()


async def reset_vector_tables_if_dev():
    """
    In development mode, drop PGVector tables if they exist.
    This handles dimension mismatches when switching embedding models.
    
    WARNING: Only runs in development mode!
    """
    if settings.app_env != "development":
        return

    print("   ⚠️  DEV MODE: Checking for vector table reset...")
    
    async with async_engine.begin() as conn:
        # Check if langchain_pg_embedding table exists and drop it
        # This is the table created by langchain-postgres PGVector
        result = await conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'langchain_pg_embedding'
            );
        """))
        exists = result.scalar()
        
        if exists:
            print("   🗑️  Dropping existing vector tables (dimension mismatch prevention)...")
            await conn.execute(text("DROP TABLE IF EXISTS langchain_pg_embedding CASCADE;"))
            await conn.execute(text("DROP TABLE IF EXISTS langchain_pg_collection CASCADE;"))
            print("   ✓ Vector tables dropped. Will be recreated with new dimensions.")


async def init_database():
    """Initialize database tables."""
    # Import all models to ensure they're registered with Base
    from app.models import document  # noqa: F401
    
    # In dev mode, reset vector tables to handle dimension changes
    await reset_vector_tables_if_dev()
    
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("   ✓ Database tables initialized")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Runs startup and shutdown logic.
    """
    # Get logger
    logger = logging.getLogger(__name__)
    
    # Startup
    print("🚀 Starting Adizon Knowledge Core...")
    logger.info("🚀 Starting Adizon Knowledge Core...")
    print(f"   Environment: {settings.app_env}")
    logger.info(f"Environment: {settings.app_env}")
    print(f"   Debug: {settings.app_debug}")
    logger.info(f"Debug Mode: {settings.app_debug}")
    print(f"   Embedding Model: {settings.embedding_model}")
    logger.info(f"Embedding Model: {settings.embedding_model}")
    
    # Initialize database tables
    await init_database()
    logger.info("✅ Database tables initialized")
    
    # Ensure MinIO bucket exists
    minio = get_minio_service()
    await minio.ensure_bucket_exists()
    logger.info("✅ MinIO bucket ready")
    
    print("✅ Startup complete!")
    logger.info("✅ Startup complete! Ready to accept requests.")
    logger.info("="*60)
    
    yield
    
    # Shutdown
    print("👋 Shutting down Adizon Knowledge Core...")
    logger.info("👋 Shutting down Adizon Knowledge Core...")
    await async_engine.dispose()
    logger.info("✅ Shutdown complete")


app = FastAPI(
    title="Adizon Knowledge Core",
    description="Sovereign AI Knowledge Platform with Hybrid GraphRAG",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(sync_status.router, prefix="/api/v1", tags=["Monitoring"])
app.include_router(debug.router, prefix="/api/v1", tags=["Debug"])
app.include_router(ingestion.router, prefix="/api/v1", tags=["Ingestion"])
app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
app.include_router(graph.router, prefix="/api/v1", tags=["Graph"])


@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Adizon Knowledge Core",
        "version": "0.1.0",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check endpoint."""
    return {
        "status": "healthy",
        "environment": settings.app_env,
        "embedding_model": settings.embedding_model,
        "components": {
            "api": "ok",
            "database": "ok",
            "storage": "ok",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )
