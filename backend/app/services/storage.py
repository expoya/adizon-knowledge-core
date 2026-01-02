"""
MinIO Storage Service for document management.

Handles file uploads, downloads, and management in MinIO object storage.
Uses boto3 with run_in_executor for async compatibility.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from io import BytesIO
from urllib.parse import quote

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from fastapi import UploadFile

from app.core.config import get_settings

settings = get_settings()

# Thread pool for running blocking boto3 operations
_executor = ThreadPoolExecutor(max_workers=4)


class MinioService:
    """
    Service for interacting with MinIO S3-compatible storage.
    
    Provides async methods for:
    - Ensuring bucket exists
    - Uploading documents
    - Downloading documents
    - Generating presigned URLs
    - Deleting documents
    """

    def __init__(self):
        """Initialize MinIO client."""
        self.client = boto3.client(
            "s3",
            endpoint_url=f"{'https' if settings.minio_secure else 'http'}://{settings.minio_endpoint}",
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",  # MinIO default
        )
        self.bucket = settings.minio_bucket_name

    async def _run_sync(self, func, *args, **kwargs):
        """Run a synchronous function in the thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor, partial(func, *args, **kwargs)
        )

    async def ensure_bucket_exists(self) -> None:
        """
        Ensure the bucket exists, create if it doesn't.
        Should be called during application startup.
        """
        try:
            await self._run_sync(self.client.head_bucket, Bucket=self.bucket)
            print(f"   ✓ MinIO bucket '{self.bucket}' exists")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchBucket"):
                await self._run_sync(self.client.create_bucket, Bucket=self.bucket)
                print(f"   ✓ MinIO bucket '{self.bucket}' created")
            else:
                raise

    async def upload_file(
        self,
        file: UploadFile,
        object_name: str,
    ) -> str:
        """
        Upload a file to MinIO storage.
        
        Args:
            file: FastAPI UploadFile object (cursor should be at position 0)
            object_name: Target path/key in the bucket
            
        Returns:
            The object_name (storage path) for reference
        """
        content = await file.read()
        content_type = file.content_type or "application/octet-stream"

        await self._run_sync(
            self.client.put_object,
            Bucket=self.bucket,
            Key=object_name,
            Body=BytesIO(content),
            ContentType=content_type,
            ContentLength=len(content),
            Metadata={"original_filename": quote(file.filename or "unknown")},
        )

        return object_name

    async def upload_bytes(
        self,
        content: bytes,
        object_name: str,
        content_type: str = "application/octet-stream",
        filename: str = "unknown",
    ) -> str:
        """
        Upload raw bytes to MinIO storage.
        
        Args:
            content: File content as bytes
            object_name: Target path/key in the bucket
            content_type: MIME type
            filename: Original filename for metadata
            
        Returns:
            The object_name (storage path) for reference
        """
        await self._run_sync(
            self.client.put_object,
            Bucket=self.bucket,
            Key=object_name,
            Body=BytesIO(content),
            ContentType=content_type,
            ContentLength=len(content),
            Metadata={"original_filename": quote(filename)},
        )

        return object_name

    async def download_file(self, object_name: str) -> bytes:
        """
        Download a file from MinIO storage.
        
        Args:
            object_name: Key/path in the bucket
            
        Returns:
            Raw bytes of the file
        """
        response = await self._run_sync(
            self.client.get_object,
            Bucket=self.bucket,
            Key=object_name,
        )
        return response["Body"].read()

    async def delete_file(self, object_name: str) -> None:
        """
        Delete a file from storage.
        
        Args:
            object_name: Key/path in the bucket
        """
        await self._run_sync(
            self.client.delete_object,
            Bucket=self.bucket,
            Key=object_name,
        )

    async def get_presigned_url(
        self, object_name: str, expires_in: int = 3600
    ) -> str:
        """
        Generate a presigned URL for temporary file access.
        
        Args:
            object_name: Key/path in the bucket
            expires_in: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Presigned URL string
        """
        url = await self._run_sync(
            self.client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self.bucket, "Key": object_name},
            ExpiresIn=expires_in,
        )
        return url

    async def file_exists(self, object_name: str) -> bool:
        """
        Check if a file exists in storage.
        
        Args:
            object_name: Key/path in the bucket
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            await self._run_sync(
                self.client.head_object,
                Bucket=self.bucket,
                Key=object_name,
            )
            return True
        except ClientError:
            return False


# Singleton instance
_minio_service: MinioService | None = None


def get_minio_service() -> MinioService:
    """Get or create MinIO service singleton."""
    global _minio_service
    if _minio_service is None:
        _minio_service = MinioService()
    return _minio_service
