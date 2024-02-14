from fastapi import APIRouter

from app.auth.routes import router as auth_router
from app.auth.sso.google_routes import router as google_sso_router
from app.modules.admin.routes import router as admin_router
from app.modules.core.routes import router as core_router
from app.modules.system.routes import router as system_router
from app.modules.users.routes import router as users_router

api_router = APIRouter()


api_router.include_router(admin_router, tags=["Admin"])
api_router.include_router(users_router, tags=["Users"])
api_router.include_router(core_router, tags=["Core"])
api_router.include_router(auth_router, tags=["Auth"])
api_router.include_router(google_sso_router, tags=["Google SSO"])
api_router.include_router(system_router, tags=["System"])
