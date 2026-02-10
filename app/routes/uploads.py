from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, UploadFile, File, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.controllers.auth_controller import AuthController
from app.controllers.upload_controller import UploadController
from app.schemas.upload import FileUploadResponse, FileType

router = APIRouter(prefix="/uploads", tags=["Uploads"])


def get_current_user_from_token(
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """Dependency to get current authenticated user."""
    if not authorization.startswith("Bearer "):
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )
    
    token = authorization.replace("Bearer ", "")
    return AuthController.get_current_user(db, token)


@router.post("", response_model=FileUploadResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Upload a document file.
    
    Supported file types:
    - Images: PNG, JPEG
    - Documents: PDF, DOCX
    - Data files: CSV, EXCEL (xls, xlsx)
    
    Maximum file size: 10MB
    
    - **file**: The file to upload
    
    Returns the upload metadata including the secure URL.
    """
    current_user = get_current_user_from_token(authorization, db)
    return await UploadController.upload_file(db, file, current_user.id)


@router.get("", response_model=List[FileUploadResponse])
def get_my_uploads(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum number of records to return"),
    file_type: Optional[FileType] = Query(None, description="Filter by file type"),
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Get all uploads for the authenticated user.
    
    - **skip**: Number of records to skip (for pagination)
    - **limit**: Maximum number of records to return (1-100)
    - **file_type**: Optional filter by file type (png, jpeg, pdf, csv, excel, docx)
    
    Returns a list of uploads ordered by upload date (newest first).
    """
    current_user = get_current_user_from_token(authorization, db)
    return UploadController.get_user_uploads(
        db, 
        current_user.id, 
        skip=skip, 
        limit=limit,
        file_type=file_type
    )


@router.get("/{upload_id}", response_model=FileUploadResponse)
def get_upload_by_id(
    upload_id: UUID,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Get details of a specific upload by ID.
    
    - **upload_id**: The UUID of the upload
    
    Returns the upload metadata including the secure URL.
    Only the user who uploaded the file can access it.
    """
    current_user = get_current_user_from_token(authorization, db)
    return UploadController.get_upload_by_id(db, upload_id, current_user.id)


@router.delete("/{upload_id}")
def delete_upload(
    upload_id: UUID,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Delete an upload.
    
    This will delete the file from cloud storage and remove the database record.
    
    - **upload_id**: The UUID of the upload to delete
    
    Only the user who uploaded the file can delete it.
    """
    current_user = get_current_user_from_token(authorization, db)
    return UploadController.delete_upload(db, upload_id, current_user.id)
