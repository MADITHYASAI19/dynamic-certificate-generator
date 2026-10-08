from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi import FastAPI

class RequestTooLargeError(Exception):
    """Raised when the number of recipients exceeds the allowed limit."""
    def __init__(self, limit: int):
        self.limit = limit
        super().__init__(f"Maximum recipients per job is {limit}")

async def global_exception_handler(request: Request, exc: Exception):
    # Handle custom domain exceptions first
    if isinstance(exc, RequestTooLargeError):
        return JSONResponse(
            status_code=413,
            content={"error": {"code": "REQUEST_TOO_LARGE", "message": str(exc), "details": {"limit": exc.limit}}}
        )

    # Handle HTTPExceptions normally, but wrap in standard format
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "HTTP_ERROR", "message": exc.detail, "details": {}}}
        )

    # Handle all other unexpected exceptions
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred on the server",
                "details": {"exception": str(exc)}
            }
        }
    )

def setup_exception_handlers(app: FastAPI):
    app.add_exception_handler(RequestTooLargeError, global_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
    # Explicitly handle FastAPI's HTTPException
    from fastapi.exceptions import HTTPException as FastAPIHTTPException
    app.add_exception_handler(FastAPIHTTPException, global_exception_handler)
