from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db
from app.routes import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure upload directory exists and database tables are initialized
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    try:
        await init_db()
    except Exception as e:
        print(f"[WARN] Database initialization warning (ensure DB server is reachable): {e}")
    yield
    # Shutdown logic if needed


app = FastAPI(
    title="AICTE Institutional Document Compliance Verification API",
    description="AI-powered preliminary institutional application validation and document compliance verification for AICTE EoA.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception Handlers conforming strictly to API_CONTRACT.md §8
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # If detail is already formatted with code and message
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail},
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "HTTP_ERROR",
                "message": str(exc.detail),
                "details": None,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT if hasattr(status, "HTTP_422_UNPROCESSABLE_CONTENT") else 422,
        content={
            "error": {
                "code": "VALIDATION_FAILED",
                "message": "Invalid request parameters or payload structure.",
                "details": exc.errors(),
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    # Log exception internally but return clean message to client (no stack traces)
    if settings.DEBUG:
        print(f"[INTERNAL_ERROR]: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal server error occurred while processing the request.",
                "details": None,
            }
        },
    )


# Health check
@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "category": "eoa", "version": "0.1.0"}


# Mount API Routes
app.include_router(api_router, prefix=settings.API_PREFIX)
