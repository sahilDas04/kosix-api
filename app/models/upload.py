import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, Enum, Text, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class FileType(str, enum.Enum):
    """File type enumeration."""
    PNG = "png"
    JPEG = "jpeg"
    PDF = "pdf"
    CSV = "csv"
    EXCEL = "excel"
    DOCX = "docx"


class UploadStatus(str, enum.Enum):
    """Upload status enumeration."""
    FAILED = "failed"
    SUCCESS = "success"
    PENDING = "pending"


class FileUpload(Base):
    """
    FileUpload model for tracking uploaded files.
    """
    __tablename__ = "file_upload"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    file_name = Column(String(255), nullable=False)
    file_type = Column(
        Enum(FileType, name="file_type"),
        nullable=False
    )
    uploaded_by = Column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    uploaded_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    status = Column(
        Enum(UploadStatus, name="upload_status"),
        nullable=False,
        default=UploadStatus.PENDING
    )
    url = Column(Text, nullable=True)

    # Relationship to account
    uploader = relationship("Account", backref="uploads")