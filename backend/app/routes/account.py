"""Account routes (thin). The activity log arrives with the rest of phase 6."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.controllers import account
from app.db import get_db
from app.dependencies import CurrentSession, get_session
from app.models.user import ChangePasswordIn

router = APIRouter(prefix="/api/account", tags=["account"])


@router.post("/change-password")
def change_password(
    data: ChangePasswordIn,
    request: Request,
    session: Annotated[CurrentSession, Depends(get_session)],
    db: Annotated[Session, Depends(get_db)],
):
    ip = request.client.host if request.client else None
    account.change_password(db, session, data, ip)
    return {"message": "Password updated. Other sessions were signed out."}


@router.get("/activity")
def activity(
    session: Annotated[CurrentSession, Depends(get_session)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    return account.activity(db, session.user.id, limit)
