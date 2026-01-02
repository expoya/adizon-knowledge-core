"""
KnowledgeDocument model - The core entity for document management.

Represents documents uploaded to the Knowledge Core platform,
tracking their processing status and storage location.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DocumentStatus(str, enum.Enum):
    """Processing status of a knowledge document."""

    PENDING = "pending"
    INDEXED = "indexed"
    ERROR = "error"


class KnowledgeDocument(Base):
    """
    SQLAlchemy model for knowledge documents.
    
    This is the central entity that tracks:
    - Document metadata (filename, content hash, file size)
    - Storage location in MinIO
    - Processing status in the ingestion pipeline
    
    The content_hash ensures deduplication - documents with
    identical content won't be processed twice.
    """

    __tablename__ = "knowledge_documents"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    # Document metadata
    filename: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        index=True,
        comment="Original filename of the uploaded document",
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
        comment="SHA-256 hash of document content for deduplication",
    )

    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="File size in bytes",
    )

    # Storage reference
    storage_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        comment="Path to document in MinIO storage (bucket/key)",
    )

    # Processing status
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", create_constraint=True),
        nullable=False,
        default=DocumentStatus.PENDING,
        index=True,
        comment="Current processing status in the ingestion pipeline",
    )

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if processing failed",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when document was uploaded",
    )

    # Table-level configuration
    __table_args__ = (
        Index("ix_documents_status_created", "status", "created_at"),
        {"comment": "Core table for tracking knowledge documents in the platform"},
    )

    def __repr__(self) -> str:
        return f"<KnowledgeDocument(id={self.id}, filename='{self.filename}', status={self.status.value})>"
