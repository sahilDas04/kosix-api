from uuid import UUID
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from app.core.logger import get_logger
from app.models.team import Team, team_members, team_managers
from app.models.account import Account
from app.schemas.team import (
    TeamCreate,
    TeamUpdate,
    TeamResponse,
    TeamDetailResponse,
    TeamListItem,
    TeamMemberAction,
)
from app.schemas.account import AccountListItem

logger = get_logger(__name__)


class TeamController:
    """Controller for team operations."""

    @staticmethod
    def create_team(db: Session, request: TeamCreate, owner_id: UUID) -> TeamResponse:
        """Create a new team."""
        logger.info(f"Creating team '{request.name}' for owner {owner_id}")

        team = Team(
            name=request.name,
            avatar_url=request.avatar_url,
            owner_id=owner_id
        )

        db.add(team)
        db.commit()
        db.refresh(team)

        logger.info(f"Successfully created team: {team.id}")

        return TeamResponse(
            id=team.id,
            name=team.name,
            avatar_url=team.avatar_url,
            owner_id=team.owner_id,
            created_at=team.created_at,
            updated_at=team.updated_at
        )

    @staticmethod
    def get_team(db: Session, team_id: UUID) -> TeamDetailResponse:
        """Get team by ID with full details."""
        logger.info(f"Fetching team: {team_id}")

        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            logger.warning(f"Team not found: {team_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found"
            )

        # Get owner details
        owner = None
        if team.owner:
            owner = AccountListItem(
                id=team.owner.id,
                email=team.owner.email,
                name=team.owner.name,
                username=team.owner.username,
                role=team.owner.role,
                avatar_url=team.owner.avatar_url
            )

        # Get members
        members = [
            AccountListItem(
                id=member.id,
                email=member.email,
                name=member.name,
                username=member.username,
                role=member.role,
                avatar_url=member.avatar_url
            )
            for member in team.members.all()
        ]

        # Get managers
        managers = [
            AccountListItem(
                id=manager.id,
                email=manager.email,
                name=manager.name,
                username=manager.username,
                role=manager.role,
                avatar_url=manager.avatar_url
            )
            for manager in team.managers.all()
        ]

        return TeamDetailResponse(
            id=team.id,
            name=team.name,
            avatar_url=team.avatar_url,
            owner_id=team.owner_id,
            created_at=team.created_at,
            updated_at=team.updated_at,
            owner=owner,
            members=members,
            managers=managers
        )

    @staticmethod
    def list_teams(
        db: Session,
        skip: int = 0,
        limit: int = 20,
        owner_id: Optional[UUID] = None
    ) -> List[TeamListItem]:
        """List teams with optional filtering."""
        logger.info(f"Listing teams (skip={skip}, limit={limit}, owner_id={owner_id})")

        query = db.query(
            Team.id,
            Team.name,
            Team.avatar_url,
            Team.owner_id,
            func.count(team_members.c.account_id).label('member_count')
        ).outerjoin(
            team_members, Team.id == team_members.c.team_id
        ).group_by(
            Team.id
        )

        if owner_id:
            query = query.filter(Team.owner_id == owner_id)

        teams = query.offset(skip).limit(limit).all()

        return [
            TeamListItem(
                id=team.id,
                name=team.name,
                avatar_url=team.avatar_url,
                owner_id=team.owner_id,
                member_count=team.member_count
            )
            for team in teams
        ]

    @staticmethod
    def get_my_teams(db: Session, account_id: UUID) -> List[TeamListItem]:
        """Get teams where user is owner, member, or manager."""
        logger.info(f"Fetching teams for account: {account_id}")

        # Teams where user is owner
        owned_teams = db.query(Team).filter(Team.owner_id == account_id).all()

        # Teams where user is member
        member_team_ids = db.query(team_members.c.team_id).filter(
            team_members.c.account_id == account_id
        ).all()
        member_team_ids = [t[0] for t in member_team_ids]

        # Teams where user is manager
        manager_team_ids = db.query(team_managers.c.team_id).filter(
            team_managers.c.account_id == account_id
        ).all()
        manager_team_ids = [t[0] for t in manager_team_ids]

        # Get all unique team IDs
        all_team_ids = set([t.id for t in owned_teams] + member_team_ids + manager_team_ids)

        if not all_team_ids:
            return []

        # Query teams with member count
        teams = db.query(
            Team.id,
            Team.name,
            Team.avatar_url,
            Team.owner_id,
            func.count(team_members.c.account_id).label('member_count')
        ).outerjoin(
            team_members, Team.id == team_members.c.team_id
        ).filter(
            Team.id.in_(all_team_ids)
        ).group_by(
            Team.id
        ).all()

        return [
            TeamListItem(
                id=team.id,
                name=team.name,
                avatar_url=team.avatar_url,
                owner_id=team.owner_id,
                member_count=team.member_count
            )
            for team in teams
        ]

    @staticmethod
    def update_team(
        db: Session,
        team_id: UUID,
        request: TeamUpdate,
        current_user_id: UUID
    ) -> TeamResponse:
        """Update team details."""
        logger.info(f"Updating team: {team_id}")

        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found"
            )

        # Check if user is owner or manager
        is_manager = db.query(team_managers).filter(
            team_managers.c.team_id == team_id,
            team_managers.c.account_id == current_user_id
        ).first() is not None

        if team.owner_id != current_user_id and not is_manager:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to update this team"
            )

        # Update fields
        if request.name is not None:
            team.name = request.name
        if request.avatar_url is not None:
            team.avatar_url = request.avatar_url

        db.commit()
        db.refresh(team)

        logger.info(f"Successfully updated team: {team.id}")

        return TeamResponse(
            id=team.id,
            name=team.name,
            avatar_url=team.avatar_url,
            owner_id=team.owner_id,
            created_at=team.created_at,
            updated_at=team.updated_at
        )

    @staticmethod
    def delete_team(db: Session, team_id: UUID, current_user_id: UUID) -> dict:
        """Delete a team."""
        logger.info(f"Deleting team: {team_id}")

        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found"
            )

        # Only owner can delete team
        if team.owner_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the team owner can delete this team"
            )

        db.delete(team)
        db.commit()

        logger.info(f"Successfully deleted team: {team_id}")

        return {"message": "Team deleted successfully"}

    @staticmethod
    def add_members(
        db: Session,
        team_id: UUID,
        request: TeamMemberAction,
        current_user_id: UUID
    ) -> dict:
        """Add members to a team."""
        logger.info(f"Adding members to team: {team_id}")

        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found"
            )

        # Check permissions (owner or manager)
        is_manager = db.query(team_managers).filter(
            team_managers.c.team_id == team_id,
            team_managers.c.account_id == current_user_id
        ).first() is not None

        if team.owner_id != current_user_id and not is_manager:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to add members"
            )

        added_count = 0
        for account_id in request.account_ids:
            # Check if account exists
            account = db.query(Account).filter(Account.id == account_id).first()
            if not account:
                continue

            # Check if already a member
            existing = db.query(team_members).filter(
                team_members.c.team_id == team_id,
                team_members.c.account_id == account_id
            ).first()

            if not existing:
                db.execute(
                    team_members.insert().values(
                        team_id=team_id,
                        account_id=account_id
                    )
                )
                added_count += 1

        db.commit()

        logger.info(f"Added {added_count} members to team {team_id}")

        return {"message": f"Added {added_count} members to the team"}

    @staticmethod
    def remove_members(
        db: Session,
        team_id: UUID,
        request: TeamMemberAction,
        current_user_id: UUID
    ) -> dict:
        """Remove members from a team."""
        logger.info(f"Removing members from team: {team_id}")

        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found"
            )

        # Check permissions (owner or manager)
        is_manager = db.query(team_managers).filter(
            team_managers.c.team_id == team_id,
            team_managers.c.account_id == current_user_id
        ).first() is not None

        if team.owner_id != current_user_id and not is_manager:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to remove members"
            )

        # Remove members
        result = db.execute(
            team_members.delete().where(
                team_members.c.team_id == team_id,
                team_members.c.account_id.in_(request.account_ids)
            )
        )
        db.commit()

        logger.info(f"Removed {result.rowcount} members from team {team_id}")

        return {"message": f"Removed {result.rowcount} members from the team"}

    @staticmethod
    def add_managers(
        db: Session,
        team_id: UUID,
        request: TeamMemberAction,
        current_user_id: UUID
    ) -> dict:
        """Add managers to a team."""
        logger.info(f"Adding managers to team: {team_id}")

        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found"
            )

        # Only owner can add managers
        if team.owner_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the team owner can add managers"
            )

        added_count = 0
        for account_id in request.account_ids:
            # Check if account exists
            account = db.query(Account).filter(Account.id == account_id).first()
            if not account:
                continue

            # Check if already a manager
            existing = db.query(team_managers).filter(
                team_managers.c.team_id == team_id,
                team_managers.c.account_id == account_id
            ).first()

            if not existing:
                db.execute(
                    team_managers.insert().values(
                        team_id=team_id,
                        account_id=account_id
                    )
                )
                added_count += 1

        db.commit()

        logger.info(f"Added {added_count} managers to team {team_id}")

        return {"message": f"Added {added_count} managers to the team"}

    @staticmethod
    def remove_managers(
        db: Session,
        team_id: UUID,
        request: TeamMemberAction,
        current_user_id: UUID
    ) -> dict:
        """Remove managers from a team."""
        logger.info(f"Removing managers from team: {team_id}")

        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found"
            )

        # Only owner can remove managers
        if team.owner_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the team owner can remove managers"
            )

        # Remove managers
        result = db.execute(
            team_managers.delete().where(
                team_managers.c.team_id == team_id,
                team_managers.c.account_id.in_(request.account_ids)
            )
        )
        db.commit()

        logger.info(f"Removed {result.rowcount} managers from team {team_id}")

        return {"message": f"Removed {result.rowcount} managers from the team"}

    @staticmethod
    def transfer_ownership(
        db: Session,
        team_id: UUID,
        new_owner_id: UUID,
        current_user_id: UUID
    ) -> TeamResponse:
        """Transfer team ownership to another account."""
        logger.info(f"Transferring team {team_id} ownership to {new_owner_id}")

        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found"
            )

        # Only current owner can transfer ownership
        if team.owner_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the team owner can transfer ownership"
            )

        # Check if new owner exists
        new_owner = db.query(Account).filter(Account.id == new_owner_id).first()
        if not new_owner:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="New owner account not found"
            )

        team.owner_id = new_owner_id
        db.commit()
        db.refresh(team)

        logger.info(f"Successfully transferred team {team_id} to {new_owner_id}")

        return TeamResponse(
            id=team.id,
            name=team.name,
            avatar_url=team.avatar_url,
            owner_id=team.owner_id,
            created_at=team.created_at,
            updated_at=team.updated_at
        )

    @staticmethod
    def leave_team(db: Session, team_id: UUID, account_id: UUID) -> dict:
        """Leave a team (remove self from members/managers)."""
        logger.info(f"Account {account_id} leaving team {team_id}")

        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found"
            )

        # Owner cannot leave their own team
        if team.owner_id == account_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Team owner cannot leave. Transfer ownership first."
            )

        # Remove from members
        db.execute(
            team_members.delete().where(
                team_members.c.team_id == team_id,
                team_members.c.account_id == account_id
            )
        )

        # Remove from managers
        db.execute(
            team_managers.delete().where(
                team_managers.c.team_id == team_id,
                team_managers.c.account_id == account_id
            )
        )

        db.commit()

        logger.info(f"Account {account_id} left team {team_id}")

        return {"message": "Successfully left the team"}
