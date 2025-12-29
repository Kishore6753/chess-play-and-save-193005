import os
from typing import List, Optional

from dotenv import load_dotenv

# Load .env if present (not required). This is safe in all environments.
load_dotenv()


def _split_csv(value: Optional[str]) -> Optional[List[str]]:
    if value is None:
        return None
    parts = [p.strip() for p in value.split(",")]
    parts = [p for p in parts if p]
    return parts or None


class Settings:
    """App settings sourced from environment variables with safe defaults."""

    def __init__(self) -> None:
        # Default: local SQLite file under ./data/chess.db
        self.database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/chess.db")

        # Default CORS: allow common local dev origins, plus a regex for hosted preview URLs on port 3000.
        self.cors_origins: List[str] = _split_csv(os.getenv("CORS_ORIGINS")) or [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
        self.cors_origin_regex: str = os.getenv("CORS_ORIGIN_REGEX", r"^https://.*:3000$")


settings = Settings()
