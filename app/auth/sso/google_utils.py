from fastapi import HTTPException, status
from httpx import AsyncClient

from app.core.config import settings
from app.services import strings


async def get_access_token(code: str) -> str:
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": f"{settings.APP_BASE_URL}/api/v1/auth/google/callback",
        "grant_type": "authorization_code",
    }

    async with AsyncClient() as client:
        response = await client.post(token_url, data=token_data)
        response.raise_for_status()  # Utilisez raise_for_status pour une gestion d'erreur simplifiée
        token_info = response.json()
        return token_info.get("access_token")


async def get_user_info(access_token: str) -> dict:
    url = "https://www.googleapis.com/oauth2/v3/userinfo"
    headers = {"Authorization": f"Bearer {access_token}"}

    async with AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()


async def refresh_access_token(refresh_token: str) -> str:
    token_url = "https://www.googleapis.com/oauth2/v4/token"
    token_data = {
        "refresh_token": refresh_token,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "grant_type": "refresh_token",
    }

    async with AsyncClient() as client:
        response = await client.post(token_url, data=token_data)

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=strings.INVALID_REFRESH_TOKEN,
            )

        token_info = response.json()
        return token_info.get("access_token")
