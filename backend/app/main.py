import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.api.routers.engine import router as engine_router
from app.api.routers.products import router as products_router
from app.api.routers.submissions import router as submissions_router
from app.api.routers.documents import router as documents_router
from app.api.routers.auth import router as auth_router

app = FastAPI(
    title="Assurance System API",
    description="Backend API for adaptive insurance submissions.",
    version="1.0.0",
)

# Handle CORS for local React development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(engine_router)
app.include_router(products_router)
app.include_router(submissions_router)
app.include_router(documents_router)

class HealthCheck(BaseModel):
    status: str
    service: str

@app.get("/health", response_model=HealthCheck, tags=["System"])
def health_check():
    """
    Basic health check endpoint ensuring backend is reachable.
    """
    return HealthCheck(status="ok", service="AssuranceBackend")

