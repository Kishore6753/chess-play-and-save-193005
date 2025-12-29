from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.db import init_db
from src.api.routes.games import router as games_router
from src.api.routes.users import router as users_router

openapi_tags = [
    {
        "name": "health",
        "description": "Health and service info endpoints.",
    },
    {
        "name": "users",
        "description": "User management (create and fetch users).",
    },
    {
        "name": "games",
        "description": "Chess game management (create games, play moves, save/load snapshots).",
    },
]

app = FastAPI(
    title="Chess Backend API",
    description=(
        "Backend service for a fullstack chess application. Provides user management, "
        "game creation, move validation (legal chess rules), persistence with SQLite, "
        "and explicit save/load via named snapshots."
    ),
    version="0.2.0",
    openapi_tags=openapi_tags,
)

# CORS: allow React frontend (port 3000) by default, plus hosted preview URLs on port 3000.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    """Initialize database tables on service startup."""
    init_db()


app.include_router(users_router)
app.include_router(games_router)


# PUBLIC_INTERFACE
@app.get(
    "/",
    tags=["health"],
    summary="Health check",
    description="Simple health check endpoint used by deployment and monitoring.",
    operation_id="health_check",
)
def health_check():
    """Return service health status."""
    return {"message": "Healthy"}
