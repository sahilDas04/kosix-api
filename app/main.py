import uvicorn
from fastapi import FastAPI
from app.core.config import settings
from app.routes.auth import router as auth_router
from app.routes.teams import router as teams_router

app = FastAPI(
    title="API",
    description="Authentication and Team Management API",
    version="1.0.0"
)

# Include routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(teams_router, prefix="/api/v1")


@app.get("/")
def home():
    return {"status": "online", "port": settings.PORT}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=True
    )
