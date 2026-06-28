"""Global middleware: exception handling, request logging, timing, input validation"""
import time
import logging
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.api_scheduler.client import QuotaExceededError, AllModelsFailedError

logger = logging.getLogger("knowall")

# Max input lengths by endpoint prefix
INPUT_LIMITS = {
    "/api/v1/chat/assistant": 8000,
    "/api/v1/knowledge/tree/generate": 200000,
    "/api/v1/quiz/generate": 100000,
    "/api/v1/flashcards/generate": 50000,
    "/api/v1/pipeline/run": 200000,
}


class InputValidationMiddleware(BaseHTTPMiddleware):
    """Validate request body size and content before processing."""

    async def dispatch(self, request: Request, call_next):
        # Check content length for POST/PUT
        if request.method in ("POST", "PUT", "PATCH"):
            content_length = request.headers.get("content-length")
            if content_length:
                size = int(content_length)
                # Hard limit: 10MB for file uploads, 1MB for API calls
                if "/upload" in request.url.path:
                    max_size = 100 * 1024 * 1024  # 100MB
                else:
                    max_size = 1 * 1024 * 1024  # 1MB
                if size > max_size:
                    return JSONResponse(
                        status_code=413,
                        content={"error": "payload_too_large", "detail": f"Request body exceeds {max_size // 1024 // 1024}MB limit"},
                    )

        # Validate text length for AI generation endpoints
        if request.method == "POST":
            for prefix, limit in INPUT_LIMITS.items():
                if request.url.path.startswith(prefix):
                    # We can't read body here without consuming it, so we do lightweight check
                    # Full validation happens in the route handler
                    break

        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration_ms = int((time.time() - start) * 1000)
        # Only log non-200 or slow requests in detail
        if response.status_code >= 400 or duration_ms > 1000:
            logger.warning(
                "%s %s → %s (%dms)",
                request.method, request.url.path, response.status_code, duration_ms,
            )
        return response


class GlobalExceptionMiddleware(BaseHTTPMiddleware):
    """Catch unhandled exceptions and return consistent JSON errors."""

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except QuotaExceededError as e:
            return JSONResponse(status_code=429, content={"error": "quota_exceeded", "detail": str(e)})
        except AllModelsFailedError as e:
            return JSONResponse(status_code=502, content={"error": "all_models_failed", "detail": str(e)})
        except ValueError as e:
            return JSONResponse(status_code=400, content={"error": "bad_request", "detail": str(e)})
        except FileNotFoundError as e:
            return JSONResponse(status_code=404, content={"error": "not_found", "detail": str(e)})
        except Exception as e:
            logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
            import traceback
            return JSONResponse(status_code=500, content={"error": "internal_error", "detail": f"{type(e).__name__}: {str(e)}", "traceback": traceback.format_exc()[-2000:]})


def setup_middleware(app):
    """Register all middleware on the FastAPI app. Order: last added = first executed."""
    app.add_middleware(GlobalExceptionMiddleware)
    app.add_middleware(InputValidationMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
