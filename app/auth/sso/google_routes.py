from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi_sso.sso.google import GoogleSSO
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schema import Google, GoogleToken, Token
from app.auth.sso.google_utils import refresh_access_token
from app.core.config import settings
from app.core.query_factory import create_entry, get_specific
from app.utils.security import generate_access_refresh_token
from app.db.deps import get_db
from app.modules.core.models import AuthMethod, User
from app.services import strings

router = APIRouter(prefix="/auth/google")


def get_google_sso() -> GoogleSSO:
    return GoogleSSO(
        settings.GOOGLE_CLIENT_ID,
        settings.GOOGLE_CLIENT_SECRET,
        redirect_uri=f"{settings.APP_BASE_URL}{settings.API_V1_STR}/auth/google/callback",
    )


@router.get("/login")
async def google_login(google_sso: GoogleSSO = Depends(get_google_sso)):
    """Initialize auth and redirect"""
    return await google_sso.get_login_redirect(
        params={"prompt": "consent", "access_type": "offline"}
    )


@router.get("/callback", response_model=GoogleToken)
async def google_callback(
    request: Request,
    google_sso: GoogleSSO = Depends(get_google_sso),
    db: AsyncSession = Depends(get_db),
):
    user = await google_sso.verify_and_process(request)

    access_token = google_sso.access_token
    refresh_token = google_sso.refresh_token

    check_user = await get_specific(
        db, User, [User.email == user.email], exception=False
    )

    if check_user:
        app_tokens = await generate_access_refresh_token(db, check_user)

        return GoogleToken(
            app=Token(
                access_token=app_tokens["access_token"],
                token_type="bearer",
                refresh_token=app_tokens["refresh_token"],
            ),
            google=Google(
                access_token=access_token,
                refresh_token=refresh_token,
            ),
        )

    if not settings.USERS_OPEN_REGISTRATION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=strings.CLOSED_REGISTRATION,
        )

    # to avoid duplicate username
    # - replace space with underscore and convert to lowercase
    # - check if username exists
    # - if exists, append google user id to username
    user.display_name = user.display_name.replace(" ", "_").lower()
    check_user = await get_specific(
        db, User, [User.username == user.display_name], exception=False
    )
    if check_user:
        user.display_name = f"{user.display_name}_{user.id}"

    user_data_in = {
        "username": user.display_name,
        "email": user.email,
        "is_active": True,
    }

    app_user = await create_entry(db, User, user_data_in)

    auth_data_in = {
        "user_id": app_user.id,
        "provider": "google",
        "provider_user_id": f"{user.id}",
        "provider_user_data": user.model_dump(),
    }

    await create_entry(db, AuthMethod, auth_data_in)

    app_tokens = await generate_access_refresh_token(db, app_user)

    return GoogleToken(
        app=Token(
            access_token=app_tokens["access_token"],
            token_type="bearer",
            refresh_token=app_tokens["refresh_token"],
        ),
        google=Google(
            access_token=access_token,
            refresh_token=refresh_token,
        ),
    )


@router.get("/refresh_access_token")
async def get_refresh_access_token(refresh_token: str):
    refreshed_access_token = await refresh_access_token(refresh_token)

    return Token(
        access_token=refreshed_access_token,
        token_type="bearer",
        refresh_token=refresh_token,
    )
