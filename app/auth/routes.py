from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schema import Message, RefreshToken, Token
from app.core.config import settings
from app.core.mail import render_template, send_email
from app.core.query_factory import check_if_exists, create_entry, get_specific
from app.utils.security import (
    add_token_to_blacklist,
    check_user_auth,
    generate_access_refresh_token,
    generate_email_token,
    get_password_hash,
    validate_refresh_token,
)
from app.db.deps import get_db
from app.modules.core.models import EmailVerification, Profile, User
from app.modules.users.schema import UserCreate, UserSchema
from app.services import strings

router = APIRouter(prefix="/auth")


@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    response_model=UserSchema,
    description="Create an account",
)
async def signup(
    user: UserCreate, request: Request, db: AsyncSession = Depends(get_db)
) -> UserSchema:
    if not settings.USERS_OPEN_REGISTRATION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=strings.CLOSED_REGISTRATION,
        )
    await check_if_exists(db, User, [User.username == user.username])
    await check_if_exists(db, User, [User.email == user.email])

    data_in = {
        "username": user.username,
        "email": user.email,
        "password": get_password_hash(user.password),
        "is_active": False,
    }
    expires_at = datetime.utcnow() + timedelta(hours=settings.EMAIL_TOKEN_EXPIRE_HOURS)

    verification_token = await generate_email_token(db)

    user = await create_entry(db, User, data_in)
    await create_entry(
        db,
        EmailVerification,
        {"token": verification_token, "user_id": user.id, "expires_at": expires_at},
    )
    await create_entry(db, Profile, {"user_id": user.id})

    verification_url = request.url_for("verify_email", token=verification_token)
    context = {"username": user.username, "verification_url": verification_url}
    html_content = render_template("mail/verify_email.jinja", context)
    send_email(
        "Verify your email",
        [{"email": user.email, "name": user.username}],
        html_content,
    )

    return user


@router.post(
    "/login",
    status_code=status.HTTP_201_CREATED,
    response_model=Token,
    description="Get an access/refresh token",
)
async def login(
    db: AsyncSession = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
) -> dict:
    user = await check_user_auth(db, form_data.username, form_data.password)
    return await generate_access_refresh_token(db, user)


@router.post(
    "/refresh_access_token",
    status_code=status.HTTP_201_CREATED,
    response_model=Token,
    description="Refresh an access token using a refresh token",
)
async def refresh_access_token(
    db: AsyncSession = Depends(get_db), token: RefreshToken = Depends()
) -> dict:
    user = await validate_refresh_token(db, token=token.refresh_token)

    tokens = await generate_access_refresh_token(db, user)

    add_token_to_blacklist(token.refresh_token)

    return tokens


@router.post("/logout", status_code=status.HTTP_200_OK, response_model=Message)
async def logout() -> dict:
    # Remove access_token/refresh_token from the frontend
    return {"msg": strings.LOGGED_OUT}


@router.get(
    "/verify_email/{token}",
    status_code=status.HTTP_200_OK,
    response_model=Message,
    description="Verify an email",
)
async def verify_email(token: str, db: AsyncSession = Depends(get_db)) -> dict:
    email_verification = await get_specific(
        db, EmailVerification, [EmailVerification.token == token]  # noqa
    )

    user = await get_specific(db, User, [User.id == email_verification.user_id])

    if email_verification.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=strings.TOKEN_EXPIRED
        )

    user.is_active = True
    await db.delete(email_verification)
    await db.commit()

    return {"msg": strings.EMAIL_VERIFIED}


@router.get(
    "/resend_verification_email/{email}",
    status_code=status.HTTP_200_OK,
    response_model=Message,
    description="Resend a verification email",
)
async def resend_verification_email(
    email: str, request: Request, db: AsyncSession = Depends(get_db)
) -> dict:
    user = await get_specific(db, User, [User.email == email])

    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=strings.EMAIL_ALREADY_VERIFIED,
        )

    email_verification = await get_specific(
        db, EmailVerification, [EmailVerification.user_id == user.id]  # noqa
    )

    expires_at = datetime.utcnow() + timedelta(hours=settings.EMAIL_TOKEN_EXPIRE_HOURS)

    verification_token = await generate_email_token(db)

    email_verification.token = verification_token
    email_verification.expires_at = expires_at

    await db.commit()

    verification_url = request.url_for("verify_email", token=verification_token)
    context = {"username": user.username, "verification_url": verification_url}
    html_content = render_template("mail/verify_email.jinja", context)
    send_email(
        "Verify your email",
        [{"email": user.email, "name": user.username}],
        html_content,
    )

    return {"msg": strings.EMAIL_SENT}
