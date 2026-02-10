import cloudinary
import cloudinary.uploader
from uuid import UUID
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status, UploadFile
import os

from app.core.config import settings
from app.core.logger import get_logger
from app.models.upload import FileUpload, FileType, UploadStatus
from app.schemas.upload import FileUploadResponse

logger = get_logger(__name__)

# Configure Cloudinary
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)


class UploadController:
    """Controller for file upload operations."""

    # Allowed file extensions mapped to FileType
    ALLOWED_EXTENSIONS = {
        'png': FileType.PNG,
        'jpg': FileType.JPEG,
        'jpeg': FileType.JPEG,
        'pdf': FileType.PDF,
        'csv': FileType.CSV,
        'xls': FileType.EXCEL,
        'xlsx': FileType.EXCEL,
        'doc': FileType.DOCX,
        'docx': FileType.DOCX,
    }

    # Max file size: 10MB
    MAX_FILE_SIZE = 10 * 1024 * 1024

    @staticmethod
    def validate_file(file: UploadFile) -> FileType:
        """
        Validate file type and extension.
        
        Args:
            file: The uploaded file
            
        Returns:
            FileType enum value
            
        Raises:
            HTTPException: If file type is not allowed
        """
        # Get file extension
        filename = file.filename.lower()
        extension = filename.split('.')[-1] if '.' in filename else ''
        
        if extension not in UploadController.ALLOWED_EXTENSIONS:
            allowed = ', '.join(UploadController.ALLOWED_EXTENSIONS.keys())
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not allowed. Allowed types: {allowed}"
            )
        
        return UploadController.ALLOWED_EXTENSIONS[extension]

    @staticmethod
    async def upload_file(
        db: Session,
        file: UploadFile,
        user_id: UUID
    ) -> FileUploadResponse:
        """
        Upload a file to Cloudinary and save metadata to database.
        
        Args:
            db: Database session
            file: The file to upload
            user_id: ID of the user uploading the file
            
        Returns:
            FileUploadResponse with upload details
            
        Raises:
            HTTPException: If upload fails or validation fails
        """
        try:
            # Log upload start
            logger.info(f"[UPLOAD] : Started uploading {file.filename}")
            
            # Validate file type
            file_type = UploadController.validate_file(file)
            
            # Read file content
            file_content = await file.read()
            file_size = len(file_content)
            
            # Check file size
            if file_size > UploadController.MAX_FILE_SIZE:
                logger.error(f"[UPLOAD] : Failed uploading {file.filename} - File size exceeds limit")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File size exceeds maximum allowed size of {UploadController.MAX_FILE_SIZE / (1024 * 1024)}MB"
                )
            
            # Reset file pointer for upload
            await file.seek(0)
            
            # Create database record with PENDING status
            upload_record = FileUpload(
                file_name=file.filename,
                file_type=file_type,
                uploaded_by=user_id,
                status=UploadStatus.PENDING
            )
            db.add(upload_record)
            db.commit()
            db.refresh(upload_record)
            logger.info(f"[UPLOAD] : Database record created with PENDING status for {file.filename}")
            
            # Upload to Cloudinary
            try:
                # Determine resource type based on file type
                resource_type = "raw" if file_type in [FileType.PDF, FileType.CSV, FileType.EXCEL, FileType.DOCX] else "image"
                
                # Create a unique public_id using user_id and upload_id
                public_id = f"uploads/{user_id}/{upload_record.id}_{file.filename.rsplit('.', 1)[0]}"
                
                # Upload file
                upload_result = cloudinary.uploader.upload(
                    file.file,
                    public_id=public_id,
                    resource_type=resource_type,
                    overwrite=True
                )
                
                # Update database record with SUCCESS status and URL
                upload_record.status = UploadStatus.SUCCESS
                upload_record.url = upload_result.get("secure_url")
                db.commit()
                db.refresh(upload_record)
                
                logger.info(f"[UPLOAD] : Completed uploading {file.filename} successfully")
                
                return FileUploadResponse(
                    id=upload_record.id,
                    file_name=upload_record.file_name,
                    file_type=upload_record.file_type,
                    uploaded_by=upload_record.uploaded_by,
                    uploaded_at=upload_record.uploaded_at,
                    status=upload_record.status,
                    url=upload_record.url
                )
                
            except Exception as e:
                # Update database record with FAILED status
                upload_record.status = UploadStatus.FAILED
                db.commit()
                logger.error(f"[UPLOAD] : Failed uploading {file.filename} - Cloudinary error: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to upload file to cloud storage: {str(e)}"
                )
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[UPLOAD] : Failed uploading {file.filename} - Error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred during file upload: {str(e)}"
            )

    @staticmethod
    def get_user_uploads(
        db: Session,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100,
        file_type: Optional[FileType] = None
    ) -> List[FileUploadResponse]:
        """
        Get all uploads for a specific user.
        
        Args:
            db: Database session
            user_id: ID of the user
            skip: Number of records to skip
            limit: Maximum number of records to return
            file_type: Optional filter by file type
            
        Returns:
            List of FileUploadResponse
        """
        query = db.query(FileUpload).filter(FileUpload.uploaded_by == user_id)
        
        if file_type:
            query = query.filter(FileUpload.file_type == file_type)
        
        uploads = query.order_by(FileUpload.uploaded_at.desc()).offset(skip).limit(limit).all()
        
        return [
            FileUploadResponse(
                id=upload.id,
                file_name=upload.file_name,
                file_type=upload.file_type,
                uploaded_by=upload.uploaded_by,
                uploaded_at=upload.uploaded_at,
                status=upload.status,
                url=upload.url
            )
            for upload in uploads
        ]

    @staticmethod
    def get_upload_by_id(
        db: Session,
        upload_id: UUID,
        user_id: UUID
    ) -> FileUploadResponse:
        """
        Get a specific upload by ID.
        
        Args:
            db: Database session
            upload_id: ID of the upload
            user_id: ID of the user (for authorization)
            
        Returns:
            FileUploadResponse
            
        Raises:
            HTTPException: If upload not found or unauthorized
        """
        upload = db.query(FileUpload).filter(FileUpload.id == upload_id).first()
        
        if not upload:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Upload not found"
            )
        
        # Check if user is authorized to access this upload
        if upload.uploaded_by != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this upload"
            )
        
        return FileUploadResponse(
            id=upload.id,
            file_name=upload.file_name,
            file_type=upload.file_type,
            uploaded_by=upload.uploaded_by,
            uploaded_at=upload.uploaded_at,
            status=upload.status,
            url=upload.url
        )

    @staticmethod
    def delete_upload(
        db: Session,
        upload_id: UUID,
        user_id: UUID
    ) -> dict:
        """
        Delete an upload from both Cloudinary and database.
        
        Args:
            db: Database session
            upload_id: ID of the upload to delete
            user_id: ID of the user (for authorization)
            
        Returns:
            Success message
            
        Raises:
            HTTPException: If upload not found or unauthorized
        """
        upload = db.query(FileUpload).filter(FileUpload.id == upload_id).first()
        
        if not upload:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Upload not found"
            )
        
        # Check if user is authorized to delete this upload
        if upload.uploaded_by != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this upload"
            )
        
        try:
            logger.info(f"[UPLOAD] : Started deleting {upload.file_name}")
            
            # Delete from Cloudinary if URL exists
            if upload.url:
                # Extract public_id from URL
                public_id = f"uploads/{user_id}/{upload.id}_{upload.file_name.rsplit('.', 1)[0]}"
                
                # Determine resource type
                resource_type = "raw" if upload.file_type in [FileType.PDF, FileType.CSV, FileType.EXCEL, FileType.DOCX] else "image"
                
                cloudinary.uploader.destroy(public_id, resource_type=resource_type)
            
            # Delete from database
            db.delete(upload)
            db.commit()
            
            logger.info(f"[UPLOAD] : Completed deleting {upload.file_name} successfully")
            
            return {"message": "Upload deleted successfully"}
            
        except Exception as e:
            logger.error(f"[UPLOAD] : Failed deleting {upload.file_name} - Error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete upload: {str(e)}"
            )
