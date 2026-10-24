"""Request-scoped authentication, authorization and database dependencies."""
from typing import Annotated

from fastapi import Depends, Request

from ..core.errors import ApiError
from ..core.security import COOKIE_NAME
from ..db.session import Db, get_db
from ..services.auth import resolve_session


def current_user(request: Request, db: Db = Depends(get_db)) -> dict:
    user, renewed = resolve_session(db, request.cookies.get(COOKIE_NAME))
    if renewed:
        request.state.renew_session_token = request.cookies.get(COOKIE_NAME)
    return user


def require_admin(user: dict = Depends(current_user)) -> dict:
    if not user["is_admin"]:
        raise ApiError("دسترسی ندارید", 403)
    return user


DbDep = Annotated[Db, Depends(get_db)]
UserDep = Annotated[dict, Depends(current_user)]
AdminDep = Annotated[dict, Depends(require_admin)]
