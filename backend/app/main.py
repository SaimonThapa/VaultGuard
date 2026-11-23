"""VaultGuard API entry point."""

import logging
import secrets
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models  # noqa: F401  (registers every table on Base.metadata)
from app.config import DEBUG, FRONTEND_ORIGIN
from app.db import Base, engine, get_db
from app.errors import error_response, register_error_handlers
from app.routes import account as account_routes
from app.routes import auth as auth_routes
from app.routes import entries as entries_routes
from app.routes import transfer as transfer_routes
from app.routes import vault as vault_routes

logger = logging.getLogger("vaultguard")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)  # no migrations: see architecture.md D10
    yield


app = FastAPI(
    title="VaultGuard API",
    debug=False,  # never let the framework render tracebacks; DEBUG only enables /docs
    lifespan=lifespan,
    # Interactive docs expose the full API surface, so they're only on in DEBUG.
    docs_url="/docs" if DEBUG else None,
    redoc_url=None,
    openapi_url="/openapi.json" if DEBUG else None,
)
register_error_handlers(app)
app.include_router(auth_routes.router)
app.include_router(account_routes.router)
app.include_router(vault_routes.router)
app.include_router(entries_routes.router)
app.include_router(transfer_routes.router)

# Only the React frontend may call the API from a browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}


@app.middleware("http")
async def harden_and_log(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Add security headers, never cache API responses, log method/path/status (no bodies), and
    turn any unexpected exception into a generic 500 (A02/A10)."""
    request_id = secrets.token_hex(4)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "unhandled error request_id=%s %s %s", request_id, request.method, request.url.path
        )
        response = error_response(500, "server_error", "Something went wrong.")
    response.headers.update(SECURITY_HEADERS)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    logger.info(
        "%s %s %s %.0fms id=%s",
        request.method,
        request.url.path,
        response.status_code,
        (time.perf_counter() - start) * 1000,
        request_id,
    )
    return response


@app.get("/api/health")
def health(db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    """Liveness check that also confirms the database is reachable."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "db": "ok"}
