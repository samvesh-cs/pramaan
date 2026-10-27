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
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# CORS Middleware
cors_origins = settings.cors_origin_list
for default_origin in [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]:
    if default_origin not in cors_origins:
        cors_origins.append(default_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _with_cors(request: Request, response: JSONResponse) -> JSONResponse:
    origin = request.headers.get("origin")
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
    return response


# Exception Handlers conforming strictly to API_CONTRACT.md §8
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # If detail is already formatted with code and message
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        resp = JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail},
        )
        return _with_cors(request, resp)
    resp = JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "HTTP_ERROR",
                "message": str(exc.detail),
                "details": None,
            }
        },
    )
    return _with_cors(request, resp)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    resp = JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT if hasattr(status, "HTTP_422_UNPROCESSABLE_CONTENT") else 422,
        content={
            "error": {
                "code": "VALIDATION_FAILED",
                "message": "Invalid request parameters or payload structure.",
                "details": exc.errors(),
            }
        },
    )
    return _with_cors(request, resp)


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    # Log exception internally but return clean message to client (no stack traces)
    if settings.DEBUG:
        print(f"[INTERNAL_ERROR]: {exc}")
    resp = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal server error occurred while processing the request.",
                "details": str(exc) if settings.DEBUG else None,
            }
        },
    )
    return _with_cors(request, resp)


# Health check
@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "category": "eoa", "version": "0.1.0"}


# Mount API Routes
app.include_router(api_router, prefix=settings.API_PREFIX)
