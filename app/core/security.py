import uuid
from datetime import datetime, timedelta
from typing import Union

import bcrypt
from fastapi import Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from starlette import status

from app.auth.schema import TokenData
from app.core.config import settings
from app.core.logger import logger
from app.core.query_factory import check_if_exists
from app.db.deps import get_db
from app.modules.admin.crud import get_user_by_username
from app.modules.core.models import EmailVerification, User
from app.services import strings
from app.services.storage import storage

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
)


JWT_OPTIONS = {
    "verify_signature": True,
    "verify_aud": False,
    "verify_iat": True,
    "verify_exp": True,
    "verify_nbf": False,
    "verify_iss": True,
    "verify_sub": True,
    "verify_jti": True,
    "verify_at_hash": False,
    "require_aud": False,
    "require_iat": True,
    "require_exp": True,
    "require_nbf": False,
    "require_iss": True,
    "require_sub": True,
    "require_jti": True,
    "require_at_hash": False,
    "leeway": 0,
}


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    # This function take approximately 0.29 seconds to run because of the bcrypt
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


async def _get_user_scopes(db: AsyncSession, user: User) -> list:
    """
    Get user scopes from the database.
    """
    query = select(User).filter(User.id == user.id)
    user = await db.execute(query)
    result = user.scalars().first()

    user_scopes = [
        permission.scope for role in result.roles for permission in role.permissions
    ]

    logger.debug(f"User {result.username} has the following scopes: {user_scopes}")

    return user_scopes


async def check_user_auth(db: AsyncSession, username: str, password: str):
    """
    Check if user information (username, password) are valid
    """
    user = await get_user_by_username(db, username)

    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=strings.INCORRECT_USER_PASSWORD,
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not user:
        raise credentials_error
    if not verify_password(password, user.password):
        raise credentials_error

    logger.info(f"Authenticating user {username}")

    return user


def create_jwt_token(
    data: dict[str, Union[str, list[str]]],
    expires_delta: timedelta | None = None,
    type: str = "access_token",
):
    """
    Create a JWT token (access_token/refresh_token) for a specific user (sub).
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    iat = datetime.utcnow()
    iss = settings.PROJECT_NAME
    jti = str(uuid.uuid4())

    jwt_key = (
        settings.JWT_ACCESS_TOKEN_KEY
        if type == "access_token"
        else settings.JWT_REFRESH_TOKEN_KEY
    )

    to_encode.update({"exp": expire, "iat": iat, "iss": iss, "jti": jti, "type": type})
    encoded_jwt = jwt.encode(to_encode, jwt_key, algorithm=settings.ALGORITHM)

    logger.debug(f"Creating {type} for user {data['sub']}")

    return encoded_jwt


async def check_jwt(
    security_scopes: SecurityScopes = SecurityScopes(),
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme),
    type: str = Query(default="access_token", include_in_schema=False),
):
    """
    Check if the JWT is valid or not.
    """
    authenticate_value = "Bearer"
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=strings.COULD_NOT_VALIDATE_CREDENTIALS,
        headers={"WWW-Authenticate": authenticate_value},
    )

    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'

    try:
        jwt_key = (
            settings.JWT_ACCESS_TOKEN_KEY
            if type == "access_token"
            else settings.JWT_REFRESH_TOKEN_KEY
        )
        payload = jwt.decode(
            token,
            jwt_key,
            algorithms=[settings.ALGORITHM],
            options=JWT_OPTIONS,
        )

        jti: str = payload.get("jti")
        username: str = payload.get("sub")

        if username is None:
            raise credentials_exception

        token_scopes = payload.get("scopes", [])
        token_data = TokenData(username=username, scopes=token_scopes)
    except jwt.PyJWTError:
        raise credentials_exception

    user = await get_user_by_username(db, username=token_data.username)

    if user is None:
        raise credentials_exception

    if jti in storage:
        logger.debug(f"{jti} is in blacklist")
        raise credentials_exception

    if token_data.username is None:
        logger.debug("sub is None")
        raise credentials_exception

    if security_scopes.scopes:
        check_scope = any(
            scope in token_data.scopes for scope in security_scopes.scopes
        )
    else:
        # If no security scopes are defined, return True
        check_scope = True

    if not check_scope:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=strings.NOT_ENOUGH_PERMISSIONS,
            headers={"WWW-Authenticate": authenticate_value},
        )

    return user


def get_current_active_user(
    current_user: User = Depends(check_jwt),
) -> User:
    """
    Check the current logged-in user.
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=strings.COULD_NOT_VALIDATE_CREDENTIALS,
        )

    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=strings.INACTIVE_USER
        )

    return current_user


def validate_refresh_token(db: AsyncSession, token: str = Depends(oauth2_scheme)):
    """
    Check if a refresh token is valid or not.
    """
    return check_jwt(db=db, token=token, type="refresh_token")


def add_token_to_blacklist(token: str, type: str = "refresh_token") -> None:
    """
    Add a token to the blacklist (refresh_token, access_token).
    If REDIS_CONNECTION is True, use a redis connection, else use a local dict.
    """
    jwt_key = (
        settings.JWT_ACCESS_TOKEN_KEY
        if type == "access_token"
        else settings.JWT_REFRESH_TOKEN_KEY
    )
    payload = jwt.decode(
        token,
        jwt_key,
        algorithms=[settings.ALGORITHM],
        options=JWT_OPTIONS,
    )
    jti = payload.get("jti")
    exp = payload.get("exp")
    storage.set_key(jti, exp)
    logger.info(f"Adding {jti} (expiring {exp}) to blacklist")


async def generate_access_refresh_token(db: AsyncSession, user) -> dict[str, str]:
    """
    Return an access token and a refresh token for a specific user.
    """
    user_scopes = await _get_user_scopes(db, user)

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_jwt_token(
        data={"sub": user.username, "scopes": user_scopes},
        expires_delta=access_token_expires,
    )

    refresh_token_expires = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    refresh_token = create_jwt_token(
        data={"sub": user.username},
        expires_delta=refresh_token_expires,
        type="refresh_token",
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


async def generate_email_token(db: AsyncSession = Depends(get_db)) -> str:
    uuid_token = str(uuid.uuid4())
    await check_if_exists(
        db, EmailVerification, [EmailVerification.token == uuid_token]  # noqa
    )
    return uuid_token
