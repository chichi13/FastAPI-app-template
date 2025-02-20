from fastapi import APIRouter, Depends, Security, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.query_factory import update_entry
from app.utils.security import get_current_active_user
from app.db.deps import get_db
from app.modules.core.models import Profile
from app.modules.users.schema import UserProfile, UserProfileBase, UserSchemaProfile

router = APIRouter(prefix="/users")


@router.get(
    "/current",
    status_code=status.HTTP_200_OK,
    response_model=UserSchemaProfile,
    description="Get current user with profile information",
)
def get_current_user(
    current_user: UserSchemaProfile = Security(get_current_active_user),
) -> UserSchemaProfile:
    return current_user


@router.put(
    "/current/profile",
    status_code=status.HTTP_200_OK,
    response_model=UserProfile,
    description="Update current user profile with new information",
)
async def update_current_profile(
    profile: UserProfileBase,
    db: AsyncSession = Depends(get_db),
    current_user: UserSchemaProfile = Security(get_current_active_user),
) -> UserSchemaProfile:
    return await update_entry(db, Profile, current_user.id, profile)
