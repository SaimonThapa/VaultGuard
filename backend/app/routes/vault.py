"""Vault routes (thin). Health, recovery and key change arrive in later phases."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.controllers import health, vault
from app.db import get_db
from app.dependencies import CurrentSession, Unlocked, get_session, get_unlocked
from app.models.user import (
    ChangeMasterKeyIn,
    MasterKeyIn,
    OtpRequestIn,
    RecoverIn,
    ResetVaultIn,
    UnlockIn,
)

router = APIRouter(prefix="/api/vault", tags=["vault"])
DB = Annotated[Session, Depends(get_db)]
Session_ = Annotated[CurrentSession, Depends(get_session)]
Open = Annotated[Unlocked, Depends(get_unlocked)]


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/status")
def status(session: Session_):
    return vault.status(session.user, session.session_id)


@router.post("/setup", status_code=201)
def setup(data: MasterKeyIn, session: Session_, db: DB):
    recovery_key = vault.setup(db, session.user, session.session_id, data.master_key)
    return {"recovery_key": recovery_key}


@router.post("/unlock")
def unlock(data: UnlockIn, request: Request, session: Session_, db: DB):
    return vault.unlock(db, session.user, session.session_id, data.master_key, _ip(request))


@router.post("/lock", status_code=204)
def lock(session: Session_):
    vault.lock(session.session_id)
    return Response(status_code=204)


@router.post("/otp", status_code=202)
def request_otp(data: OtpRequestIn, session: Session_, db: DB):
    vault.request_otp(db, session.user, data.purpose)
    return {"message": "A code was sent to your email."}


@router.post("/recover")
def recover(data: RecoverIn, request: Request, session: Session_, db: DB):
    return vault.recover(
        db,
        session.user,
        session.session_id,
        data.code,
        data.recovery_key,
        data.new_master_key,
        _ip(request),
    )


@router.post("/change-master-key")
def change_master_key(data: ChangeMasterKeyIn, request: Request, unlocked: Open, db: DB):
    recovery_key = vault.change_master_key(db, unlocked, data.new_master_key, _ip(request))
    return {"recovery_key": recovery_key}


@router.post("/reset")
def reset(data: ResetVaultIn, request: Request, session: Session_, db: DB):
    recovery_key = vault.reset(
        db, session.user, session.session_id, data.code, data.new_master_key, _ip(request)
    )
    return {"recovery_key": recovery_key}


@router.get("/health")
def vault_health(request: Request, unlocked: Open, db: DB):
    return health.build_report(db, unlocked, _ip(request))
