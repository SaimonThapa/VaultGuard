"""Auth routes: thin. They parse the request, call a controller, and set or clear the cookie."""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy.orm import Session

from app import config
from app.controllers import auth
from app.db import get_db
from app.models.user import (
    ForgotPasswordIn,
    LoginIn,
    ResendIn,
    ResetPasswordIn,
    SignupIn,
    VerifyEmailIn,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
COOKIE = "vg_refresh"
DB = Annotated[Session, Depends(get_db)]
RefreshCookie = Annotated[str | None, Cookie(alias=COOKIE)]


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _set_cookie(response: Response, token: str) -> None:
    # HttpOnly: JavaScript (so XSS) can't read it. Strict + narrow path: only auth calls send it.
    response.set_cookie(
        COOKIE,
        token,
        max_age=config.REFRESH_TOKEN_DAYS * 86400,
        httponly=True,
        samesite="strict",
        secure=config.COOKIE_SECURE,
        path="/api/auth",
    )


@router.post("/signup", status_code=201)
def signup(data: SignupIn, db: DB):
    auth.signup(db, data)
    return {"message": "Check your email for a verification code."}


@router.post("/verify-email")
def verify_email(data: VerifyEmailIn, request: Request, response: Response, db: DB):
    payload, refresh = auth.verify_email(db, data, _ip(request))
    _set_cookie(response, refresh)
    return payload


@router.post("/resend-verification", status_code=202)
def resend_verification(data: ResendIn, db: DB):
    auth.resend_verification(db, data.username)
    return {"message": "If the account exists and is unverified, a new code was sent."}


@router.post("/login")
def login(data: LoginIn, request: Request, response: Response, db: DB):
    payload, refresh = auth.login(db, data, _ip(request))
    _set_cookie(response, refresh)
    return payload


@router.post("/refresh")
def refresh(request: Request, response: Response, db: DB, vg_refresh: RefreshCookie = None):
    payload, new_token = auth.refresh(db, vg_refresh, _ip(request))
    _set_cookie(response, new_token)
    return payload


@router.post("/logout", status_code=204)
def logout(db: DB, vg_refresh: RefreshCookie = None):
    auth.logout(db, vg_refresh)
    response = Response(status_code=204)
    response.delete_cookie(COOKIE, path="/api/auth")
    return response


@router.post("/forgot-password", status_code=202)
def forgot_password(data: ForgotPasswordIn, db: DB):
    auth.forgot_password(db, data)
    return {"message": "If an account exists for that email, a code was sent."}


@router.post("/reset-password")
def reset_password(data: ResetPasswordIn, request: Request, db: DB):
    auth.reset_password(db, data, _ip(request))
    return {"message": "Password updated. Please log in."}
