from fastapi import FastAPI
from fastapi.routing import APIRouter
from app.core.config import settings
from app.core.exceptions import setup_exception_handlers

app = FastAPI(
    title="Bulk Certificate Generator",
    version="0.1.0",
    description="API for generating certificates in bulk"
)

setup_exception_handlers(app)

# Root health check
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Versioned API Router
from app.api.v1 import jobs, retrieval, status as status_api
api_v1_router = APIRouter()
api_v1_router.include_router(jobs.router)
api_v1_router.include_router(retrieval.router)
api_v1_router.include_router(status_api.router)
app.include_router(api_v1_router, prefix="/api/v1")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
