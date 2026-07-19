"""
Main FastAPI application initialization.

This is the entry point for the backend server.
Configures middleware, routes, error handlers, and startup/shutdown events.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.gzip import GZipMiddleware

from app.api.routes import documents, embeddings
from app.cache.redis_client import redis_client
from app.config import ensure_directories, settings
from app.dependencies import AsyncSessionLocal, init_db
from app.models.schemas import ErrorResponse, HealthCheckResponse
from app.utils.errors import ApplicationException
from app.utils.logger import ErrorLogger, RequestLogger, setup_logging

logger = logging.getLogger(__name__)


# ==== STARTUP & SHUTDOWN EVENTS ====
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle.

    Startup:
    - Initialize directories
    - Setup logging
    - Initialize database
    - Connect to Redis
    - Load embedding model

    Shutdown:
    - Close database connections
    - Close Redis connection
    - Cleanup resources
    """

    # ==== STARTUP ====
    try:
        logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
        logger.info(f"Environment: {settings.ENVIRONMENT}")

        # Create necessary directories
        ensure_directories()
        logger.info("Directories initialized")

        # Initialize database
        await init_db()
        logger.info("Database initialized")

        # Connect to Redis
        await redis_client.connect()
        logger.info("Redis connected")

        # Test database connection
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        logger.info("Database connection verified")

        logger.info(f"{settings.APP_NAME} started successfully")

    except Exception as e:
        ErrorLogger.log_critical(f"Startup error: {str(e)}")
        raise

    yield  # Application runs here

    # ==== SHUTDOWN ====
    try:
        logger.info(f"Shutting down {settings.APP_NAME}")

        # Close Redis connection
        await redis_client.close()
        logger.info("Redis connection closed")

        logger.info(f"{settings.APP_NAME} stopped")

    except Exception as e:
        ErrorLogger.log_critical(f"Shutdown error: {str(e)}")


# ==== CREATE APP ====
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI Research Assistant - RAG System API",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
)


# ==== MIDDLEWARE ====

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZIP Compression (compress responses > 1KB)
app.add_middleware(GZipMiddleware, minimum_size=1000)


# ==== GLOBAL ERROR HANDLER ====


@app.exception_handler(ApplicationException)
async def application_exception_handler(request: Request, exc: ApplicationException):
    """Handle custom application exceptions."""
    ErrorLogger.log_error(
        error_type=exc.error_code,
        error_msg=exc.message,
        context={"path": request.url.path, "method": request.method},
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "detail": exc.message,
            "status_code": exc.status_code,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors."""
    error_details = [
        {"field": error["loc"][-1], "message": error["msg"]} for error in exc.errors()
    ]

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "details": error_details,
            "status_code": 422,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    ErrorLogger.log_critical(
        f"Unhandled exception: {str(exc)}",
        context={"path": request.url.path, "method": request.method},
    )

    # Don't expose internal errors in production
    message = (
        "Internal server error" if settings.ENVIRONMENT == "production" else str(exc)
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "detail": message,
            "status_code": 500,
        },
    )


# ==== REQUEST/RESPONSE MIDDLEWARE ====


@app.middleware("http")
async def add_request_tracking(request: Request, call_next):
    """
    Track request timing and logging.

    This middleware:
    - Measures request duration
    - Logs request/response
    - Adds timing headers
    """
    start_time = time.time()

    # Extract user ID if authenticated
    user_id = None
    if hasattr(request.state, "user_id"):
        user_id = request.state.user_id

    # Log incoming request
    RequestLogger.log_request(
        method=request.method,
        url=request.url.path,
        user_id=user_id,
    )

    # Process request
    response = await call_next(request)

    # Calculate response time
    process_time = time.time() - start_time
    process_time_ms = process_time * 1000

    # Log outgoing response
    RequestLogger.log_response(
        method=request.method,
        url=request.url.path,
        status_code=response.status_code,
        response_time_ms=process_time_ms,
        user_id=user_id,
    )

    # Add timing header
    response.headers["X-Process-Time"] = str(process_time_ms)

    return response


# ==== HEALTH CHECK ENDPOINT ====


@app.get("/api/health", response_model=HealthCheckResponse, tags=["System"])
async def health_check():
    """
    Health check endpoint.

    Returns:
        HealthCheckResponse with database and cache status
    """
    databases = {}

    # Check PostgreSQL
    try:
        async with AsyncSessionLocal() as db:
            await db.execute("SELECT 1")
        databases["postgresql"] = "connected"
    except Exception as e:
        databases["postgresql"] = f"error: {str(e)[:50]}"

    # Check Redis
    try:
        await redis_client.ping()
        databases["redis"] = "connected"
    except Exception as e:
        databases["redis"] = f"error: {str(e)[:50]}"

    # Check ChromaDB
    try:
        # Will be added in Phase 4
        databases["chromadb"] = "pending"
    except Exception as e:
        databases["chromadb"] = f"error: {str(e)[:50]}"

    return HealthCheckResponse(
        status="healthy"
        if all("connected" in v for v in databases.values())
        else "degraded",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        databases=databases,
    )


# ==== INFO ENDPOINT ====


@app.get("/api/info", tags=["System"])
async def get_info():
    """Get application information."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "embedding_model": settings.EMBEDDING_MODEL,
        "llm_provider": settings.LLM_PROVIDER,
    }


# ==== ROOT ENDPOINT ====


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/api/docs" if settings.DEBUG else "Documentation not available",
    }


# Note: Additional routes (auth, documents, chat, search) will be included in Phase 1
# via the router imports below (once they're created):
from app.api.routes import auth, chat, documents, search

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(search.router)

# ==== ROUTE IMPORTS ====
# Phase 2: Document routes
app.include_router(documents.router)

# Phase 3: Embedding routes
app.include_router(embeddings.router)

# Voice: Gemini transcription
from app.api.routes import voice

app.include_router(voice.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD and settings.ENVIRONMENT != "production",
        log_level=settings.LOG_LEVEL.lower(),
    )
