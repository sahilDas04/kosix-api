from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.controllers.auth_controller import AuthController
from app.controllers.team_controller import TeamController
from app.schemas.team import (
    TeamCreate,
    TeamUpdate,
    TeamResponse,
    TeamDetailResponse,
    TeamListItem,
    TeamMemberAction,
)

router = APIRouter(prefix="/teams", tags=["Teams"])


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


@router.post("", response_model=TeamResponse, status_code=201)
def create_team(
    request: TeamCreate,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Create a new team.
    
    The authenticated user becomes the team owner.
    
    - **name**: Team name (1-255 characters)
    - **avatar_url**: Optional team avatar URL
    """
    current_user = get_current_user_from_token(authorization, db)
    return TeamController.create_team(db, request, current_user.id)


@router.get("", response_model=List[TeamListItem])
def list_teams(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    owner_id: Optional[UUID] = None,
    db: Session = Depends(get_db)
):
    """
    List all teams with optional filtering.
    
    - **skip**: Number of teams to skip (pagination)
    - **limit**: Maximum number of teams to return
    - **owner_id**: Filter by owner ID
    """
    return TeamController.list_teams(db, skip=skip, limit=limit, owner_id=owner_id)


@router.get("/my", response_model=List[TeamListItem])
def get_my_teams(
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Get teams where current user is owner, member, or manager.
    """
    current_user = get_current_user_from_token(authorization, db)
    return TeamController.get_my_teams(db, current_user.id)


@router.get("/{team_id}", response_model=TeamDetailResponse)
def get_team(
    team_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get team details by ID.
    
    Returns team with owner, members, and managers.
    """
    return TeamController.get_team(db, team_id)


@router.patch("/{team_id}", response_model=TeamResponse)
def update_team(
    team_id: UUID,
    request: TeamUpdate,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Update team details.
    
    Requires owner or manager permissions.
    
    - **name**: New team name (optional)
    - **avatar_url**: New avatar URL (optional)
    """
    current_user = get_current_user_from_token(authorization, db)
    return TeamController.update_team(db, team_id, request, current_user.id)


@router.delete("/{team_id}")
def delete_team(
    team_id: UUID,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Delete a team.
    
    Only the team owner can delete the team.
    """
    current_user = get_current_user_from_token(authorization, db)
    return TeamController.delete_team(db, team_id, current_user.id)


@router.post("/{team_id}/members")
def add_members(
    team_id: UUID,
    request: TeamMemberAction,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Add members to a team.
    
    Requires owner or manager permissions.
    
    - **account_ids**: List of account IDs to add as members
    """
    current_user = get_current_user_from_token(authorization, db)
    return TeamController.add_members(db, team_id, request, current_user.id)


@router.delete("/{team_id}/members")
def remove_members(
    team_id: UUID,
    request: TeamMemberAction,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Remove members from a team.
    
    Requires owner or manager permissions.
    
    - **account_ids**: List of account IDs to remove
    """
    current_user = get_current_user_from_token(authorization, db)
    return TeamController.remove_members(db, team_id, request, current_user.id)


@router.post("/{team_id}/managers")
def add_managers(
    team_id: UUID,
    request: TeamMemberAction,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Add managers to a team.
    
    Only the team owner can add managers.
    
    - **account_ids**: List of account IDs to add as managers
    """
    current_user = get_current_user_from_token(authorization, db)
    return TeamController.add_managers(db, team_id, request, current_user.id)


@router.delete("/{team_id}/managers")
def remove_managers(
    team_id: UUID,
    request: TeamMemberAction,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Remove managers from a team.
    
    Only the team owner can remove managers.
    
    - **account_ids**: List of account IDs to remove
    """
    current_user = get_current_user_from_token(authorization, db)
    return TeamController.remove_managers(db, team_id, request, current_user.id)


@router.post("/{team_id}/transfer-ownership", response_model=TeamResponse)
def transfer_ownership(
    team_id: UUID,
    new_owner_id: UUID = Query(..., description="ID of the new owner"),
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Transfer team ownership to another account.
    
    Only the current owner can transfer ownership.
    
    - **new_owner_id**: ID of the account to transfer ownership to
    """
    current_user = get_current_user_from_token(authorization, db)
    return TeamController.transfer_ownership(db, team_id, new_owner_id, current_user.id)


@router.post("/{team_id}/leave")
def leave_team(
    team_id: UUID,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Leave a team.
    
    Removes the current user from members and managers.
    Team owners cannot leave - they must transfer ownership first.
    """
    current_user = get_current_user_from_token(authorization, db)
    return TeamController.leave_team(db, team_id, current_user.id)
