"""VaultGuard API entry point."""

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import DEBUG, FRONTEND_ORIGIN
from app.db import get_db

app = FastAPI(
    title="VaultGuard API",
    debug=DEBUG,
    # Interactive docs expose the full API surface, so they're only on in DEBUG.
    docs_url="/docs" if DEBUG else None,
    redoc_url=None,
    openapi_url="/openapi.json" if DEBUG else None,
)

# Only the React frontend may call the API from a browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health")
def health(db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    """Liveness check that also confirms the database is reachable."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "db": "ok"}
