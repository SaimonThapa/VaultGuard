"""Entry routes (thin). The list works while locked; everything else needs an unlocked vault."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.controllers import entries
from app.core import key_store
from app.db import get_db
from app.dependencies import CurrentSession, Unlocked, get_session, get_unlocked
from app.models.entry import EntryIn

router = APIRouter(prefix="/api/entries", tags=["entries"])
DB = Annotated[Session, Depends(get_db)]
Open = Annotated[Unlocked, Depends(get_unlocked)]


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("")
def list_entries(
    request: Request,
    session: Annotated[CurrentSession, Depends(get_session)],
    db: DB,
    q: Annotated[str, Query(max_length=100)] = "",
):
    vault = key_store.get(session.session_id)  # None while locked: secrets stay encrypted
    unlocked = Unlocked(session, vault) if vault else None
    return entries.list_entries(db, session.user.id, unlocked, q.strip(), _ip(request))


@router.post("", status_code=201)
def create(data: EntryIn, unlocked: Open, db: DB):
    return entries.create(db, unlocked, data)


@router.get("/{entry_id}")
def read(entry_id: UUID, request: Request, unlocked: Open, db: DB):
    return entries.read(db, unlocked, str(entry_id), _ip(request))


@router.put("/{entry_id}")
def update(entry_id: UUID, data: EntryIn, request: Request, unlocked: Open, db: DB):
    return entries.update(db, unlocked, str(entry_id), data, _ip(request))


@router.delete("/{entry_id}", status_code=204)
def delete(entry_id: UUID, unlocked: Open, db: DB):
    entries.delete(db, unlocked.user.id, str(entry_id))
    return Response(status_code=204)
