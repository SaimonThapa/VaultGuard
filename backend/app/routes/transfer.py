"""Import / export routes (thin). Both need an unlocked vault."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.controllers import transfer
from app.db import get_db
from app.dependencies import Unlocked, get_unlocked
from app.models.user import UnlockIn

router = APIRouter(prefix="/api", tags=["transfer"])
DB = Annotated[Session, Depends(get_db)]
Open = Annotated[Unlocked, Depends(get_unlocked)]


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/import")
def import_passwords(
    request: Request,
    unlocked: Open,
    db: DB,
    file: Annotated[UploadFile, File()],
    master_key: Annotated[str | None, Form(max_length=256)] = None,
):
    raw = file.file.read(transfer.MAX_BYTES + 1)  # never read more than the cap plus one byte
    return transfer.import_file(db, unlocked, raw, master_key, _ip(request))


@router.post("/export")
def export_backup(data: UnlockIn, request: Request, unlocked: Open, db: DB):
    filename, body = transfer.export_backup(db, unlocked, data.master_key, _ip(request))
    return Response(
        body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
