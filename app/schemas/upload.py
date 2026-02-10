from datetime import datetime
from typing import Optional
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field


class FileType(str, Enum):
    """File type enumeration."""
    PNG = "png"
    JPEG = "jpeg"
    PDF = "pdf"
    CSV = "csv"
    EXCEL = "excel"
    DOCX = "docx"


class UploadStatus(str, Enum):
    """Upload status enumeration."""
    FAILED = "failed"
    SUCCESS = "success"
    PENDING = "pending"


# Base schema with common fields
class FileUploadBase(BaseModel):
    """Base file upload schema with common fields."""
    file_name: str = Field(..., min_length=1, max_length=255)
    file_type: FileType


# Schema for creating a file upload
class FileUploadCreate(FileUploadBase):
    """Schema for creating a new file upload."""
    uploaded_by: UUID


# Schema for updating a file upload
class FileUploadUpdate(BaseModel):
    """Schema for updating a file upload."""
    status: Optional[UploadStatus] = None
    url: Optional[str] = None


# Schema for response
class FileUploadResponse(FileUploadBase):
    """Schema for file upload response."""
    id: UUID
    uploaded_by: UUID
    uploaded_at: datetime
    status: UploadStatus
    url: Optional[str] = None

    class Config:
        from_attributes = True
