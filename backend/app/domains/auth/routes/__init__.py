"""AUTH domain routers."""

from app.domains.auth.routes.auth import router as auth_router
from app.domains.auth.routes.password_reset import router as password_reset_router
from app.domains.auth.routes.portal import router as portal_admin_router
from app.domains.auth.routes.refresh_tokens import router as refresh_tokens_router
from app.domains.auth.routes.sso import router as sso_router
from app.domains.auth.routes.users import router as users_router

__all__ = [
    "auth_router", "users_router", "refresh_tokens_router", "sso_router",
    "portal_admin_router", "password_reset_router",
]
