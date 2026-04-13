"""
Application bootstrap — creates FastAPI app, registers middleware, routers, and startup hooks.
"""

import asyncio
import signal
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.core.database import engine
from src.models.base import Base
from src.schemas import ErrorResponse
from src.core.rate_limiter import RateLimitMiddleware
from src.core.logging import setup_logging, get_logger
from src.core.security import generate_trace_id
from src.core.idempotency import IdempotencyMiddleware

# ── Structured logging ──────────────────────────────────────────────────
setup_logging(environment=settings.environment)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle with graceful signal handling."""
    # ── Fail fast on production misconfiguration ──────────────────
    if settings.environment == "production":
        settings.validate_production()
        logger.info("Production configuration validated")

    # Startup: create tables if they don't exist (dev only — use Alembic in prod)
    if settings.environment == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized (dev mode)")

    # Test Redis connection
    from src.core.redis_client import get_redis
    await get_redis()

    # Set up graceful shutdown handlers
    loop = asyncio.get_event_loop()
    shutdown_event = asyncio.Event()

    def _signal_handler():
        logger.info("Received shutdown signal — draining connections")
        shutdown_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            signal.signal(sig, lambda s, f: _signal_handler())

    logger.info(
        "Credaly Scoring API started",
        environment=settings.environment,
        version=settings.app_version,
    )

    yield

    # Shutdown: wait for in-flight requests, then close pools
    logger.info("Shutting down — waiting for in-flight requests to complete")
    await asyncio.sleep(2)  # Grace period

    await engine.dispose()
    from src.core.redis_client import close_redis
    await close_redis()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Predictive Behavioral Credit & Insurance Platform — Scoring API",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware (order matters) ──────────────────────────────────────────

# 1. CORS — configurable, not wildcard in production
allowed_origins = settings.cors_allowed_origins.split(",") if settings.cors_allowed_origins else []
if not allowed_origins and settings.environment != "production":
    allowed_origins = ["*"]  # Dev default

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Rate limiting
app.add_middleware(RateLimitMiddleware)

# 3. Idempotency — prevents duplicate score requests on retry
app.add_middleware(IdempotencyMiddleware)


@app.middleware("http")
async def add_trace_id(request: Request, call_next):
    """Attach a unique trace_id to every request for debugging."""
    trace_id = request.headers.get("X-Trace-Id", f"trc_{uuid.uuid4().hex[:8]}")
    request.state.trace_id = trace_id

    # Add request context to structured logger
    import structlog
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        trace_id=trace_id,
        method=request.method,
        path=request.url.path,
    )

    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    return response


# ── Exception Handlers ──────────────────────────────────────────────────

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    logger.warning("Validation error", error=str(exc))
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            code="VALIDATION_ERROR",
            message=str(exc),
            trace_id=getattr(request.state, "trace_id", "unknown"),
            docs_url="https://docs.platform.com/errors/VALIDATION_ERROR",
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            code="INTERNAL_ERROR",
            message="An internal server error occurred.",
            trace_id=getattr(request.state, "trace_id", "unknown"),
            docs_url="https://docs.platform.com/errors/INTERNAL_ERROR",
        ).model_dump(),
    )


# ── Routers ────────────────────────────────────────────────────────────

prefix = settings.api_prefix

from src.api.score_router import router as score_router
from src.api.outcome_router import router as outcome_router
from src.api.consent_router import router as consent_router
from src.api.subject_router import router as subject_router
from src.api.webhook_router import router as webhook_router
from src.api.batch_score_router import router as batch_score_router
from src.api.review_router import router as review_router
from src.api.borrower_explanation_router import router as borrower_explanation_router
from src.api.api_key_router import router as api_key_router
from src.api.webhook_mgmt_router import router as webhook_mgmt_router

app.include_router(score_router, prefix=prefix, tags=["Scoring"])
app.include_router(outcome_router, prefix=prefix, tags=["Outcomes"])
app.include_router(consent_router, prefix=prefix, tags=["Consent"])
app.include_router(subject_router, prefix=prefix, tags=["Data Subject Rights"])
app.include_router(webhook_router, prefix=prefix, tags=["Webhooks"])
app.include_router(batch_score_router, prefix=prefix, tags=["Batch Scoring"])
app.include_router(review_router, prefix=prefix, tags=["Human Review"])
app.include_router(borrower_explanation_router, prefix=prefix, tags=["Borrower Explanation"])
app.include_router(api_key_router, prefix=prefix, tags=["API Key Management"])
app.include_router(webhook_mgmt_router, prefix=prefix, tags=["Webhook Management"])


# ── Health Check ────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/", tags=["Health"])
async def root():
    return {
        "message": "Credaly Scoring API",
        "docs": "/docs",
        "health": "/health",
    }
