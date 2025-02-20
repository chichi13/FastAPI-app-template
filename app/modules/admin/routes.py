from fastapi import APIRouter, Depends, Security, status
from fastapi_pagination import add_pagination
from fastapi_pagination.bases import AbstractPage
from fastapi_pagination.ext.async_sqlalchemy import paginate
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.params_paginate import Page
from app.core.query_factory import (
    delete_by_id,
    get_all_paginate,
    get_specific_by_id,
    update_entry,
)
from app.core.schema import DefaultResponse
from app.utils.security import get_current_active_user
from app.db.deps import get_db
from app.modules.core.models import Profile, User
from app.modules.users.schema import (
    UserProfile,
    UserProfileBase,
    UserSchema,
    UserSchemaProfile,
)

router = APIRouter(prefix="/admin")


@router.get(
    "/users",
    status_code=status.HTTP_200_OK,
    response_model=Page[UserSchema],
    description="Get all users with pagination",
)
async def get_all_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Security(get_current_active_user, scopes=["admin"]),  # noqa
) -> AbstractPage:
    return await paginate(db, get_all_paginate(User))


@router.get(
    "/users/{user_id}",
    response_model=UserSchemaProfile,
    status_code=status.HTTP_200_OK,
    description="Get specific user by user_id",
)
async def get_specific_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserSchemaProfile = Security(  # noqa
        get_current_active_user, scopes=["admin"]
    ),
):
    return await get_specific_by_id(db, User, user_id)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=DefaultResponse,
    description="Delete specific user by user_id",
)
async def delete_specific_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Security(get_current_active_user, scopes=["admin"]),  # noqa
):
    return await delete_by_id(db, User, user_id)


@router.put(
    "/users/{user_id}/profile",
    status_code=status.HTTP_200_OK,
    response_model=UserProfile,
    description="Update specific user profile",
)
async def update_specific_profile(
    user_id: int,
    profile: UserProfileBase,
    db: AsyncSession = Depends(get_db),
    current_user: UserSchemaProfile = Security(  # noqa
        get_current_active_user, scopes=["admin"]
    ),
) -> UserSchemaProfile:
    return await update_entry(db, Profile, user_id, profile)


add_pagination(router)
