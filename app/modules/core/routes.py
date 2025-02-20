from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi_pagination import add_pagination
from fastapi_pagination.bases import AbstractPage
from fastapi_pagination.ext.async_sqlalchemy import paginate
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.params_paginate import Page
from app.core.query_factory import (
    check_if_exists,
    create_entry,
    delete_by_id,
    get_all_paginate,
    get_specific_by_id,
    update_entry,
)
from app.core.schema import DefaultResponse
from app.utils.security import get_current_active_user
from app.db.deps import get_db
from app.modules.core.crud import get_user_permission, get_user_roles
from app.modules.core.models import Permission, Role, User
from app.modules.core.schema import (
    PermissionBase,
    PermissionCreate,
    PermissionUpdate,
    RoleBase,
    RoleCreate,
    RolePermissions,
    RoleUpdate,
    UserPermissionBase,
    UserRoleBase,
)

router = APIRouter(prefix="/core")


@router.get(
    "/roles",
    status_code=status.HTTP_200_OK,
    response_model=Page[RoleBase],
    description="Get all roles with pagination",
)
async def get_all_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Security(  # noqa
        get_current_active_user, scopes=["admin", "role:read"]
    ),
) -> AbstractPage:
    return await paginate(db, get_all_paginate(Role))


@router.get(
    "/roles/{role_id}",
    status_code=status.HTTP_200_OK,
    response_model=RoleBase,
    description="Get specific role by role_id",
)
async def get_specific_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Security(  # noqa
        get_current_active_user, scopes=["admin", "role:read"]
    ),
) -> RoleBase:
    return await get_specific_by_id(db, Role, role_id)


@router.post(
    "/roles",
    status_code=status.HTTP_200_OK,
    response_model=RoleBase,
    description="Create a role",
)
async def create_role(
    role: RoleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Security(  # noqa
        get_current_active_user, scopes=["admin", "role:create"]
    ),
) -> RoleBase:
    await check_if_exists(db, Role, [Role.name == role.name])
    return await create_entry(db, Role, role)


@router.put(
    "/roles/{role_id}",
    status_code=status.HTTP_200_OK,
    response_model=RoleBase,
    description="Update specific role by role_id",
)
async def update_specific_role(
    role_id: int,
    role: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Security(  # noqa
        get_current_active_user, scopes=["admin", "role:update"]
    ),
) -> RoleBase:
    await check_if_exists(db, Role, [Role.name == role.name])

    return await update_entry(db, Role, role_id, role)


@router.delete(
    "/roles/{role_id}",
    status_code=status.HTTP_200_OK,
    response_model=DefaultResponse,
    description="Delete specific role by role_id",
)
async def delete_specific_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Security(  # noqa
        get_current_active_user, scopes=["admin", "role:delete"]
    ),
) -> DefaultResponse:
    return await delete_by_id(db, Role, role_id)


@router.get(
    "/roles/user/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=UserRoleBase,
    description="Get specific user roles by user_id",
)
async def get_specific_user_roles(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Security(  # noqa
        get_current_active_user, scopes=["admin", "role:read"]
    ),
):
    return await get_user_roles(db, user_id)


@router.post(
    "/roles/{role_id}/user/{user_id}",
    status_code=status.HTTP_201_CREATED,
    response_model=UserRoleBase,
    description="Link role to a user given a role_id and user_id",
)
async def link_role_to_user(
    role_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Security(  # noqa
        get_current_active_user, scopes=["admin", "role:link"]
    ),
) -> UserRoleBase:
    user = await get_specific_by_id(db, User, user_id)
    role = await get_specific_by_id(db, Role, role_id)

    user.roles.append(role)

    await db.commit()
    await db.refresh(user)

    return await get_user_roles(db, user_id)


@router.get(
    "/roles/{role_id}/permissions",
    status_code=status.HTTP_200_OK,
    response_model=RolePermissions,
    description="Get specific permissions for a role given a role_id",
)
async def get_role_permission(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Security(  # noqa
        get_current_active_user, scopes=["admin", "role:read"]
    ),
) -> RolePermissions:
    role = await get_specific_by_id(db, Role, role_id)

    return RolePermissions(
        id=role.id,
        description=role.description,
        name=role.name,
        permissions=[permission for permission in role.permissions],
    )


@router.delete(
    "/roles/{role_id}/user/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=DefaultResponse,
    description="Unlink a role from a user given a role_id and user_id",
)
async def unlink_role_from_user(
    role_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Security(  # noqa
        get_current_active_user, scopes=["admin", "role:link"]
    ),
) -> DefaultResponse:
    user = await get_specific_by_id(db, User, user_id)
    role = await get_specific_by_id(db, Role, role_id)

    # Check if user has the role
    if role not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User doesn't have this role",
        )

    user.roles.remove(role)
    await db.commit()

    return DefaultResponse(status=True, msg="Role unlinked from user")


@router.post(
    "/roles/{role_id}/permission/{permission_id}",
    status_code=status.HTTP_200_OK,
    response_model=RolePermissions,
    description="Link role to a permission given a role_id and permission_id",
)
async def link_role_to_permission(
    role_id: int,
    permission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Security(  # noqa
        get_current_active_user, scopes=["admin", "permission:link"]
    ),
) -> RolePermissions:
    role = await get_specific_by_id(db, Role, role_id)
    permission = await get_specific_by_id(db, Permission, permission_id)

    role.permissions.append(permission)

    await db.commit()
    await db.refresh(role)

    return RolePermissions(
        id=role.id,
        description=role.description,
        name=role.name,
        permissions=[permission for permission in role.permissions],
    )


@router.delete(
    "/roles/{role_id}/permission/{permission_id}",
    status_code=status.HTTP_200_OK,
    response_model=DefaultResponse,
    description="Unlink a role from a permission given a role_id and permission_id",
)
async def unlink_role_from_permission(
    role_id: int,
    permission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Security(  # noqa
        get_current_active_user, scopes=["admin", "permission:link"]
    ),
) -> DefaultResponse:
    role = await get_specific_by_id(db, Role, role_id)
    permission = await get_specific_by_id(db, Permission, permission_id)

    # Check if role has the permission
    if permission not in role.permissions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role doesn't have this permission",
        )

    role.permissions.remove(permission)
    await db.commit()

    return DefaultResponse(status=True, msg="Permission unlinked to role")


@router.get(
    "/permissions",
    status_code=status.HTTP_200_OK,
    response_model=Page[PermissionBase],
    description="Get all permissions with pagination",
)
async def get_all_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Security(  # noqa
        get_current_active_user, scopes=["admin", "permission:read"]
    ),
) -> AbstractPage:
    return await paginate(db, get_all_paginate(Permission))


@router.get(
    "/permissions/{permission_id}",
    status_code=status.HTTP_200_OK,
    response_model=PermissionBase,
    description="Get specific permission by permission_id",
)
async def get_specific_permission(
    permission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Security(  # noqa
        get_current_active_user, scopes=["admin", "permission:read"]
    ),
) -> PermissionBase:
    return await get_specific_by_id(db, Permission, permission_id)


@router.post(
    "/permissions",
    status_code=status.HTTP_201_CREATED,
    response_model=PermissionBase,
    description="Create permission with a scope name and description",
)
async def create_permission(
    permission: PermissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Security(  # noqa
        get_current_active_user, scopes=["admin", "permission:create"]
    ),
) -> PermissionBase:
    await check_if_exists(db, Permission, [Permission.scope == permission.scope])
    return await create_entry(db, Permission, permission)


@router.put(
    "/permissions/{permission_id}",
    status_code=status.HTTP_200_OK,
    response_model=PermissionBase,
    description="Update specific permission by permission_id",
)
async def update_specific_permission(
    permission_id: int,
    permission: PermissionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Security(  # noqa
        get_current_active_user, scopes=["admin", "permission:update"]
    ),
) -> PermissionBase:
    await check_if_exists(db, Permission, [Permission.scope == permission.scope])

    return await update_entry(db, Permission, permission_id, permission)


@router.delete(
    "/permissions/{permission_id}",
    status_code=status.HTTP_200_OK,
    response_model=DefaultResponse,
    description="Delete specific permission by permission_id",
)
async def delete_specific_permission(
    permission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Security(  # noqa
        get_current_active_user, scopes=["admin", "permission:delete"]
    ),
) -> DefaultResponse:
    return await delete_by_id(db, Permission, permission_id)


@router.get(
    "/permissions/user/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=UserPermissionBase,
    description="Get specific user permissions by user_id",
)
async def get_specific_user_permission(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Security(  # noqa
        get_current_active_user, scopes=["admin", "permission:read"]
    ),
):
    user_permission = await get_user_permission(db, user_id)

    return user_permission


add_pagination(router)
