from fastapi import FastAPI
from fastapi.routing import APIRouter
from app.core.config import settings

app = FastAPI(
    title="Bulk Certificate Generator",
    version="0.1.0",
    description="API for generating certificates in bulk"
)

# Root health check
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Versioned API Router
api_v1_router = APIRouter()
app.include_router(api_v1_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
